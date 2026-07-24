"""Ficheros Python que ningún otro fichero del repo importa.

Heurística estática basada en `import`/`from ... import`, sin ejecutar
código. **Solo Python por ahora** (el soporte a otros lenguajes es el
caso de uso ideal para un plugin de terceros -- ver `plugin.py`). Como
toda heurística estática, puede haber falsos positivos (import dinámico,
entry points, ficheros cargados por un framework por convención) -- por
eso la severidad es baja y el mensaje lo deja claro.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..plugin import CheckResult, Finding

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+(?:\s*,\s*[.\w]+)*))",
    re.MULTILINE,
)

# Ficheros que un import no referenciaria nunca pero que sí "se usan":
# puntos de entrada, convenciones de framework/test-runner, config.
_SPECIAL_NAMES = {
    "setup.py", "conftest.py", "manage.py", "__init__.py", "__main__.py",
}
_SPECIAL_DIR_PREFIXES = ("tests/", "test/", "scripts/", "bin/", "examples/", "docs/")


def _tracked_py_files(repo_path: Path) -> list[Path] | None:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=repo_path, capture_output=True,
            text=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return [repo_path / line for line in out.stdout.splitlines() if line]


def _module_candidates(repo_path: Path, file_path: Path) -> set[str]:
    """Nombres por los que se podría importar `file_path` desde el repo."""
    rel = file_path.relative_to(repo_path)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    if not parts:
        return set()
    dotted = ".".join(parts)
    candidates = {dotted, parts[-1]}
    return candidates


def _is_special(repo_path: Path, file_path: Path) -> bool:
    rel = str(file_path.relative_to(repo_path))
    if file_path.name in _SPECIAL_NAMES:
        return True
    return any(rel.startswith(prefix) for prefix in _SPECIAL_DIR_PREFIXES)


class DeadFilesCheck:
    name = "dead_files"
    description = "Ficheros Python que ningún otro fichero del repo importa (heurística)."

    def run(self, repo_path: Path) -> CheckResult:
        py_files = _tracked_py_files(repo_path)
        if py_files is None:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no es un repositorio git.",
                error="not_a_git_repo",
            )
        if not py_files:
            return CheckResult(check_name=self.name, summary="No hay ficheros .py en el repo.")

        imported_names: set[str] = set()
        for file_path in py_files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in _IMPORT_RE.finditer(text):
                raw = match.group(1) or match.group(2) or ""
                for token in raw.split(","):
                    token = token.strip().lstrip(".")
                    if not token:
                        continue
                    # Anade tanto el nombre completo como cada prefijo de paquete
                    # ("a.b.c" tambien cuenta como referencia a "a" y "a.b").
                    segs = token.split(".")
                    for i in range(1, len(segs) + 1):
                        imported_names.add(".".join(segs[:i]))

        findings: list[Finding] = []
        for file_path in py_files:
            if _is_special(repo_path, file_path):
                continue
            candidates = _module_candidates(repo_path, file_path)
            if candidates & imported_names:
                continue
            findings.append(Finding(
                severity="low",
                title="Fichero Python no importado por ningún otro fichero del repo",
                detail="Heurística estática (sin ejecutar código) -- puede ser un falso "
                "positivo si se carga dinámicamente o es un punto de entrada.",
                path=str(file_path.relative_to(repo_path)),
            ))

        summary = f"{len(py_files)} fichero(s) .py analizados, {len(findings)} posible(s) huérfano(s)."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
