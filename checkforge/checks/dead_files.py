"""Ficheros Python que ningún otro fichero del repo importa.

Heurística estática basada en `import`/`from ... import` (con `ast`, así
que resuelve los imports relativos y `from paquete import submodulo`), sin
ejecutar código. También cuentan como uso los puntos de entrada de
`[project.scripts]`, los `python -m modulo` que aparezcan en el repo y los
directorios que Ansible carga por convención (`library/`, `module_utils/`). **Solo Python por ahora** (el soporte a otros lenguajes es el
caso de uso ideal para un plugin de terceros -- ver `plugin.py`). Como
toda heurística estática, puede haber falsos positivos (import dinámico,
entry points, ficheros cargados por un framework por convención) -- por
eso la severidad es baja y el mensaje lo deja claro.
"""
from __future__ import annotations

import ast
import re
import subprocess
import tomllib
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
# Directorios cuyos .py carga una herramienta por convención, no un import (en cualquier nivel)
_CONVENTION_DIRS = {"library", "module_utils", "filter_plugins", "lookup_plugins", "callback_plugins"}
_PYTHON_M = re.compile(r"python[\d.]*\s+-m\s+([A-Za-z_][\w.]*)")
_TEXT_SUFFIXES = {".md", ".rst", ".txt", ".py", ".sh", ".toml", ".yml", ".yaml", ".cfg", ".ini", ".service", ""}


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


def _is_script(file_path: Path) -> bool:
    """Un .py con guion en el nombre no se puede importar; con shebang se ejecuta directamente."""
    if "-" in file_path.stem:
        return True
    try:
        with file_path.open("rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def _is_special(repo_path: Path, file_path: Path) -> bool:
    rel = file_path.relative_to(repo_path)
    if file_path.name in _SPECIAL_NAMES or _is_script(file_path):
        return True
    if file_path.name.startswith("test_") or file_path.name.endswith("_test.py"):   # tests fuera de tests/
        return True
    if _CONVENTION_DIRS & set(rel.parts[:-1]):
        return True
    return any(str(rel).startswith(prefix) for prefix in _SPECIAL_DIR_PREFIXES)


def _with_prefixes(names: set[str], dotted: str) -> None:
    """Añade "a.b.c" y sus prefijos ("a", "a.b"): importar un submódulo usa sus paquetes."""
    segs = [s for s in dotted.split(".") if s]
    for i in range(1, len(segs) + 1):
        names.add(".".join(segs[:i]))


def _package_of(repo_path: Path, file_path: Path) -> list[str]:
    """Paquete al que pertenece el fichero (base de sus imports relativos)."""
    return list(file_path.relative_to(repo_path).parts[:-1])


def _imports_from_source(repo_path: Path, file_path: Path, text: str) -> set[str]:
    """Nombres de módulo que importa el fichero, con los relativos ya resueltos."""
    names: set[str] = set()
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        for match in _IMPORT_RE.finditer(text):      # Python que no parsea: la heurística de siempre
            for token in (match.group(1) or match.group(2) or "").split(","):
                _with_prefixes(names, token.strip().lstrip("."))
        return names
    package = _package_of(repo_path, file_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _with_prefixes(names, alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - (node.level - 1)] if node.level > 1 else package
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            _with_prefixes(names, module)
            for alias in node.names:            # "from paquete import submodulo"
                if alias.name != "*":
                    _with_prefixes(names, f"{module}.{alias.name}" if module else alias.name)
                    names.add(alias.name)
    return names


def _entry_point_modules(repo_path: Path) -> set[str]:
    names: set[str] = set()
    pyproject = repo_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            project = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore")).get("project", {})
        except tomllib.TOMLDecodeError:
            project = {}
        groups = [project.get("scripts", {}), project.get("gui-scripts", {}), *project.get("entry-points", {}).values()]
        for group in groups:
            for target in group.values():
                _with_prefixes(names, str(target).split(":")[0].strip())
    return names


def _python_m_modules(repo_path: Path, tracked: list[str]) -> set[str]:
    names: set[str] = set()
    for rel in tracked:
        path = repo_path / rel
        if path.suffix not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in _PYTHON_M.finditer(text):
            _with_prefixes(names, match.group(1).rstrip("."))
    return names


def _tracked_files(repo_path: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=repo_path, capture_output=True, text=True,
                             check=True, timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [line for line in out.stdout.splitlines() if line]


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

        imported_names = _entry_point_modules(repo_path) | _python_m_modules(repo_path, _tracked_files(repo_path))
        for file_path in py_files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            imported_names |= _imports_from_source(repo_path, file_path, text)

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
