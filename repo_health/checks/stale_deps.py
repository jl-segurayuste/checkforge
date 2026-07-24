"""Dependencias Python declaradas pero nunca importadas, e imports sin declarar.

Todo estático y sin red (no consulta a PyPI en esta versión -- comprobar
versiones desactualizadas de verdad necesitaría red, y este check está
pensado para poder correr offline/en CI de forma fiable; queda como
posible plugin aparte el día que se quiera esa comprobación).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

from ..plugin import CheckResult, Finding

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][\w]*)|import\s+([A-Za-z_][\w]*))",
    re.MULTILINE,
)

# Casos donde el nombre del paquete (PyPI) y el nombre que se importa
# difieren -- las discrepancias mas comunes, no exhaustivo a proposito.
_PACKAGE_TO_IMPORT = {
    "pyyaml": "yaml",
    "beautifulsoup4": "bs4",
    "pillow": "PIL",
    "python-dotenv": "dotenv",
    "scikit-learn": "sklearn",
    "opencv-python": "cv2",
    "python-dateutil": "dateutil",
    "pyjwt": "jwt",
    "protobuf": "google",
    "grpcio": "grpc",
}

_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def _parse_requirements_txt(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-e", "-r", "--")):
            continue
        match = _REQ_LINE.match(line)
        if match:
            names.add(match.group(1).lower())
    return names


def _parse_pyproject_toml(path: Path) -> set[str]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        return set()
    names: set[str] = set()
    project = data.get("project", {})
    for dep in project.get("dependencies", []):
        match = _REQ_LINE.match(dep)
        if match:
            names.add(match.group(1).lower())
    for extra_deps in project.get("optional-dependencies", {}).values():
        for dep in extra_deps:
            match = _REQ_LINE.match(dep)
            if match:
                names.add(match.group(1).lower())
    return names


def _declared_dependencies(repo_path: Path) -> set[str]:
    names: set[str] = set()
    req = repo_path / "requirements.txt"
    if req.is_file():
        names |= _parse_requirements_txt(req)
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        names |= _parse_pyproject_toml(pyproject)
    return names


def _to_import_name(package_name: str) -> str:
    mapped = _PACKAGE_TO_IMPORT.get(package_name.lower())
    if mapped:
        return mapped
    return package_name.replace("-", "_")


def _local_package_names(repo_path: Path) -> set[str]:
    """Nombres de nivel superior que son del propio repo, no de PyPI.

    Un paquete propio del repo (`import miproyecto`) no es una dependencia
    sin declarar -- es el propio código que se está analizando. Se detecta
    por convención: cualquier directorio de primer nivel con `__init__.py`,
    más los ficheros .py sueltos en la raíz.
    """
    names: set[str] = set()
    for entry in repo_path.iterdir():
        if entry.is_dir() and (entry / "__init__.py").is_file():
            names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)
    return names


def _used_imports(repo_path: Path) -> set[str] | None:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=repo_path, capture_output=True,
            text=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    used: set[str] = set()
    for rel in out.stdout.splitlines():
        if not rel:
            continue
        try:
            text = (repo_path / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _IMPORT_RE.finditer(text):
            name = match.group(1) or match.group(2)
            if name:
                used.add(name.split(".")[0])
    return used


class StaleDepsCheck:
    name = "stale_deps"
    description = "Dependencias Python declaradas sin usar, o usadas sin declarar (requirements.txt/pyproject.toml)."

    def run(self, repo_path: Path) -> CheckResult:
        declared = _declared_dependencies(repo_path)
        if not declared:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no se encontró requirements.txt ni [project.dependencies] en pyproject.toml.",
            )

        used = _used_imports(repo_path)
        if used is None:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no es un repositorio git.",
                error="not_a_git_repo",
            )

        findings: list[Finding] = []
        for package in sorted(declared):
            import_name = _to_import_name(package)
            if import_name not in used:
                findings.append(Finding(
                    severity="low",
                    title=f"Dependencia declarada pero no importada en ningún fichero: {package}",
                    detail="Heurística -- puede usarse indirectamente (plugin, entry point, CLI de terceros).",
                ))

        declared_import_names = {_to_import_name(p) for p in declared}
        local_names = _local_package_names(repo_path)
        for name in sorted(used - declared_import_names - _STDLIB - local_names):
            findings.append(Finding(
                severity="info",
                title=f"Import de terceros sin declarar en requirements/pyproject: {name}",
                detail="Puede ser un módulo local o una dependencia transitiva -- revisar.",
            ))

        summary = f"{len(declared)} dependencia(s) declarada(s), {len(findings)} hallazgo(s)."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
