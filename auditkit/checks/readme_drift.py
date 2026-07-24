"""Compara lo que dice el README con la realidad del proyecto.

Deliberadamente NO ejecuta nada del repo analizado (ni el propio CLI que
declare, ni ningún script) -- es puramente estático, comparando texto
contra `pyproject.toml`. Ejecutar el código de un repo ajeno solo para
"comprobar el README" sería una superficie de ataque real para una
herramienta que la gente corre contra repos que no controla.

Dos comprobaciones, ambas de bajo riesgo de falso positivo porque solo
disparan ante una discrepancia concreta y verificable:
1. La versión mínima de Python que pide `pyproject.toml`
   (`requires-python`) frente a versiones de Python mencionadas en el
   README que ya no cumplirían ese mínimo.
2. Comandos declarados en `[project.scripts]` que el README no menciona
   ni una sola vez -- un CLI sin documentar.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from ..plugin import CheckResult, Finding

_README_NAMES = ("README.md", "README.rst", "README.txt", "README")
_PY_VERSION_IN_README = re.compile(r"\bpython\s*(?:>=|==|~=)?\s*(\d+)\.(\d+)\b", re.IGNORECASE)
_MIN_VERSION_SPEC = re.compile(r">=\s*(\d+)\.(\d+)")


def _find_readme(repo_path: Path) -> Path | None:
    for name in _README_NAMES:
        candidate = repo_path / name
        if candidate.is_file():
            return candidate
    return None


def _load_pyproject(repo_path: Path) -> dict | None:
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        return tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        return None


def _min_python_version(requires_python: str) -> tuple[int, int] | None:
    match = _MIN_VERSION_SPEC.search(requires_python)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


class ReadmeDriftCheck:
    name = "readme_drift"
    description = "Compara la versión de Python y los comandos de CLI del README contra pyproject.toml (sin ejecutar nada)."

    def run(self, repo_path: Path) -> CheckResult:
        data = _load_pyproject(repo_path)
        if data is None:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no hay pyproject.toml (o no es TOML válido).",
            )
        readme_path = _find_readme(repo_path)
        if readme_path is None:
            return CheckResult(check_name=self.name, summary="No aplica: no hay README.")

        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        project = data.get("project", {})
        findings: list[Finding] = []

        requires_python = project.get("requires-python", "")
        min_version = _min_python_version(requires_python)
        if min_version is not None:
            for match in _PY_VERSION_IN_README.finditer(readme_text):
                mentioned = (int(match.group(1)), int(match.group(2)))
                if mentioned[0] == 3 and mentioned < min_version:
                    findings.append(Finding(
                        severity="medium",
                        title=(
                            f"El README menciona Python {mentioned[0]}.{mentioned[1]}, pero "
                            f"pyproject.toml pide requires-python {requires_python}"
                        ),
                        detail="El README puede haberse quedado desactualizado tras subir el mínimo.",
                        path=readme_path.name,
                    ))

        scripts = project.get("scripts", {})
        for command in sorted(scripts):
            if not re.search(rf"\b{re.escape(command)}\b", readme_text):
                findings.append(Finding(
                    severity="low",
                    title=f"Comando de CLI declarado pero no documentado en el README: {command}",
                    detail="Definido en [project.scripts] de pyproject.toml, no aparece ni una vez en el README.",
                ))

        summary = f"{len(findings)} hallazgo(s) al comparar el README con pyproject.toml."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
