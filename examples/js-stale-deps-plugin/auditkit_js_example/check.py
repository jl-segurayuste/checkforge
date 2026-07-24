"""Ejemplo de plugin de terceros para auditkit: puerto a JavaScript del
check `stale_deps` incorporado (dependencias de `package.json` declaradas
sin usar, o usadas sin declarar).

Pensado como plantilla para escribir un plugin real: la única diferencia
con un check incorporado es que este vive en su propio paquete instalable
(`auditkit-js-example`) con su propia entrada de entry point -- ver
`pyproject.toml` en la raíz de este directorio. `auditkit` nunca
importa este módulo directamente; lo descubre en tiempo de ejecución.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from auditkit.plugin import CheckResult, Finding

_JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

# require('pkg'), import x from 'pkg', import 'pkg', import('pkg'), export ... from 'pkg'
_IMPORT_RE = re.compile(
    r"""(?x)
    (?:require\(\s*|from\s+|import\(\s*)
    ['"]([^'"]+)['"]
    """
)

# Paquetes de Node incorporados -- nunca son una dependencia sin declarar.
_NODE_BUILTINS = {
    "assert", "buffer", "child_process", "cluster", "crypto", "dgram", "dns",
    "events", "fs", "http", "https", "net", "os", "path", "querystring",
    "readline", "stream", "string_decoder", "timers", "tls", "url", "util",
    "vm", "zlib", "process", "module", "perf_hooks", "worker_threads",
}


def _package_name(specifier: str) -> str | None:
    """Extrae el nombre del paquete npm de un especificador de import.

    Devuelve None para imports relativos (no son una dependencia npm).
    """
    if specifier.startswith((".", "/")):
        return None
    if specifier in _NODE_BUILTINS or specifier.startswith("node:"):
        return None
    parts = specifier.split("/")
    if specifier.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else specifier
    return parts[0]


def _tracked_js_files(repo_path: Path) -> list[Path] | None:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=repo_path, capture_output=True, text=True,
            check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return [
        repo_path / line for line in out.stdout.splitlines()
        if line and Path(line).suffix in _JS_EXTENSIONS
    ]


def _declared_dependencies(repo_path: Path) -> set[str] | None:
    """None si no hay `package.json` (no aplica); set() si lo hay pero
    declara cero dependencias -- son casos distintos, el segundo sigue
    debiendo comprobar si el código usa paquetes sin declarar ninguno.
    """
    pkg_json = repo_path / "package.json"
    if not pkg_json.is_file():
        return None
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return None
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        names.update(data.get(key, {}).keys())
    return names


class JsStaleDepsCheck:
    name = "js_stale_deps"
    description = "Dependencias de package.json declaradas sin usar, o usadas sin declarar (ejemplo de plugin)."

    def run(self, repo_path: Path) -> CheckResult:
        declared = _declared_dependencies(repo_path)
        if declared is None:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no se encontró package.json (o no es JSON válido).",
            )

        js_files = _tracked_js_files(repo_path)
        if js_files is None:
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no es un repositorio git.",
                error="not_a_git_repo",
            )

        used: set[str] = set()
        for file_path in js_files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in _IMPORT_RE.finditer(text):
                pkg = _package_name(match.group(1))
                if pkg:
                    used.add(pkg)

        findings: list[Finding] = []
        for package in sorted(declared):
            if package not in used:
                findings.append(Finding(
                    severity="low",
                    title=f"Dependencia declarada pero no importada en ningún fichero: {package}",
                    detail="Heurística -- puede usarse vía script de npm, CLI, o config, no solo import/require.",
                ))
        for package in sorted(used - declared):
            findings.append(Finding(
                severity="info",
                title=f"Import de un paquete sin declarar en package.json: {package}",
                detail="Puede ser una dependencia transitiva usada directamente por accidente -- revisar.",
            ))

        summary = f"{len(declared)} dependencia(s) declarada(s), {len(js_files)} fichero(s) JS/TS analizados, {len(findings)} hallazgo(s)."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
