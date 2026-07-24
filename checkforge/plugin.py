"""Contrato que debe cumplir cualquier check, propio o de terceros.

El núcleo no distingue entre los checks incorporados y los de un plugin
externo: ambos se descubren y ejecutan exactamente igual (ver `runner.py`).
Un check de terceros solo necesita publicar su propio paquete instalable
con una entrada en el grupo de entry points `checkforge.checks` — no hace
falta tocar este repositorio para añadir uno nuevo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

Severity = str  # "info" | "low" | "medium" | "high" -- str simple a proposito,
# un plugin de terceros no deberia depender de un enum interno nuestro.

SEVERITIES: tuple[Severity, ...] = ("info", "low", "medium", "high")


class Finding(BaseModel):
    """Un hallazgo concreto de un check."""

    severity: Severity
    title: str
    detail: str = ""
    path: str | None = None
    line: int | None = None

    def model_post_init(self, context: object, /) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(
                f"severity {self.severity!r} no es una de {SEVERITIES}"
            )


class CheckResult(BaseModel):
    """Resultado de ejecutar un check contra un repo."""

    check_name: str
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    # Si el check no pudo completarse (no aplica a este repo, herramienta
    # externa que falta, etc.) -- no es lo mismo que "sin hallazgos".
    error: str | None = None


@runtime_checkable
class Check(Protocol):
    """Un check independiente. Instanciable sin argumentos."""

    name: str
    description: str

    def run(self, repo_path: Path) -> CheckResult: ...
