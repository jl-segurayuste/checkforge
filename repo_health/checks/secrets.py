"""Detecta secretos y datos privados probables antes de un `git push`.

Va más allá de un simple grep de "password=": reconoce formatos de token
de proveedores reales (así evita en gran parte los falsos positivos de un
regex genérico de "secret\\s*=") y, por separado, señala datos que no son
técnicamente un secreto pero tampoco deberían acabar en un repo público
(IPs privadas, bloques de clave privada) con severidad más baja, porque
suelen necesitar revisión humana para distinguir un placeholder de un
dato real -- ver la lección de `feedback_no_confidential_data_in_repos`
en el historial de auditorías que motivó esta herramienta.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..plugin import CheckResult, Finding

# Tamaño máximo de fichero a inspeccionar -- evita atascarse con binarios
# grandes que hayan colado un .gitignore incompleto.
_MAX_FILE_SIZE = 2 * 1024 * 1024

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".so", ".dylib", ".dll",
    ".exe", ".bin", ".pyc", ".class", ".jar", ".sqlite", ".sqlite3", ".db",
}


@dataclass
class _Pattern:
    name: str
    regex: re.Pattern[str]
    severity: str


# Formatos de token de proveedores reales -- alta confianza, alta severidad.
_HIGH_CONFIDENCE_PATTERNS: list[_Pattern] = [
    _Pattern("Clave privada (PEM)", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "high"),
    _Pattern("AWS Access Key ID", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "high"),
    _Pattern("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "high"),
    _Pattern("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "high"),
    _Pattern("Clave de API estilo OpenAI/Stripe", re.compile(r"\b(sk|pk)_(live|test)_[A-Za-z0-9]{16,}\b"), "high"),
    _Pattern("Token de Slack webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"), "high"),
    _Pattern("JWT (aspecto de)", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "medium"),
]

# Asignaciones genéricas tipo "password = '...'" -- mucho más ruidosas
# (placeholders, ejemplos de documentación), severidad media.
_GENERIC_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key)\b
    \s*[:=]\s*
    ['"]([^'"\s]{8,})['"]
    """
)
_GENERIC_PLACEHOLDER_VALUES = {
    "changeme", "change_me", "your_key_here", "your-key-here", "xxx", "todo",
    "example", "placeholder", "secret", "password", "test", "fake", "dummy",
}

_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3})\b"
)


def _tracked_files(repo_path: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=repo_path, capture_output=True, text=True,
            check=True, timeout=30,
        )
        return [repo_path / line for line in out.stdout.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # No es un repo git (o no hay `git`) -- recorrer el arbol con exclusiones basicas.
        skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
        return [
            p for p in repo_path.rglob("*")
            if p.is_file() and not any(part in skip_dirs for part in p.parts)
        ]


def _looks_like_placeholder(value: str) -> bool:
    return value.lower() in _GENERIC_PLACEHOLDER_VALUES


class SecretsCheck:
    name = "secrets"
    description = "Busca secretos probables (claves, tokens) e IPs privadas antes de publicar."

    def run(self, repo_path: Path) -> CheckResult:
        findings: list[Finding] = []
        files_scanned = 0

        for file_path in _tracked_files(repo_path):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() in _BINARY_EXTENSIONS:
                continue
            try:
                if file_path.stat().st_size > _MAX_FILE_SIZE:
                    continue
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            files_scanned += 1
            rel = str(file_path.relative_to(repo_path))

            for lineno, line in enumerate(text.splitlines(), start=1):
                for pattern in _HIGH_CONFIDENCE_PATTERNS:
                    if pattern.regex.search(line):
                        findings.append(Finding(
                            severity=pattern.severity,
                            title=f"Posible secreto: {pattern.name}",
                            detail="Revisar y revocar si es real antes de publicar.",
                            path=rel, line=lineno,
                        ))

                for match in _GENERIC_ASSIGNMENT.finditer(line):
                    value = match.group(2)
                    if _looks_like_placeholder(value):
                        continue
                    findings.append(Finding(
                        severity="medium",
                        title=f"Asignación con aspecto de secreto ({match.group(1)})",
                        detail="Puede ser un placeholder de ejemplo -- revisar el valor real.",
                        path=rel, line=lineno,
                    ))

                for ip_match in _PRIVATE_IP.finditer(line):
                    findings.append(Finding(
                        severity="info",
                        title=f"IP privada en el código: {ip_match.group(0)}",
                        detail="Puede ser un ejemplo genérico o una IP real de tu infraestructura -- revisar.",
                        path=rel, line=lineno,
                    ))

        summary = f"{files_scanned} fichero(s) analizados, {len(findings)} hallazgo(s)."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
