"""Descubre los checks instalados (propios y de terceros) y los ejecuta.

Descubrimiento vía entry points (`auditkit.checks`) -- funciona igual
para un check incorporado en este paquete que para uno instalado desde un
paquete de terceros. Un check que falle con una excepción no tira abajo la
ejecución entera: se recoge como `CheckResult(error=...)` y se sigue con
el resto (un plugin de la comunidad no debería poder romper la ejecución
completa por un bug suyo).
"""
from __future__ import annotations

import traceback
from importlib.metadata import entry_points
from pathlib import Path

from .plugin import Check, CheckResult

ENTRY_POINT_GROUP = "auditkit.checks"


def discover_checks() -> dict[str, type[Check]]:
    """Devuelve {nombre: clase} de todos los checks instalados."""
    found: dict[str, type[Check]] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        found[ep.name] = ep.load()
    return found


def run_checks(
    repo_path: Path,
    *,
    only: set[str] | None = None,
    skip: set[str] | None = None,
) -> list[CheckResult]:
    """Ejecuta los checks aplicables sobre `repo_path`.

    `only`: si se da, solo ejecuta esos nombres de check.
    `skip`: nombres a excluir (se aplica después de `only`).
    """
    checks = discover_checks()
    names = set(checks) if only is None else (set(checks) & only)
    if skip:
        names -= skip

    results: list[CheckResult] = []
    for name in sorted(names):
        check_cls = checks[name]
        try:
            check = check_cls()
            result = check.run(repo_path)
        except Exception as exc:  # noqa: BLE001 -- un plugin de terceros puede fallar de cualquier forma
            result = CheckResult(
                check_name=name,
                summary=f"El check falló al ejecutarse: {exc}",
                error=traceback.format_exc(),
            )
        results.append(result)
    return results
