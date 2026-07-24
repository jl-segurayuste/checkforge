"""Métricas basadas en el historial de git: hotspots de cambio, ramas
obsoletas, ficheros enormes en el repo.

Todo se calcula con un puñado de invocaciones a `git` (sin librerías
externas) -- si el directorio no es un repo git, el check lo señala como
no aplicable en vez de fallar.
"""
from __future__ import annotations

import subprocess
import time
from collections import Counter
from pathlib import Path

from ..plugin import CheckResult, Finding

_STALE_BRANCH_DAYS = 180
_TOP_HOTSPOTS = 10
_LARGE_FILE_BYTES = 1 * 1024 * 1024


def _git(repo_path: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=repo_path, capture_output=True, text=True,
            check=True, timeout=60,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _is_git_repo(repo_path: Path) -> bool:
    return _git(repo_path, "rev-parse", "--is-inside-work-tree") is not None


def _churn_hotspots(repo_path: Path) -> list[Finding]:
    log = _git(repo_path, "log", "--pretty=format:__COMMIT__", "--name-only")
    if not log:
        return []
    counts: Counter[str] = Counter()
    for line in log.splitlines():
        if line and line != "__COMMIT__":
            counts[line] += 1
    findings: list[Finding] = []
    for path, count in counts.most_common(_TOP_HOTSPOTS):
        if count < 5:  # no merece la pena senalar ficheros con pocos cambios
            continue
        findings.append(Finding(
            severity="info",
            title=f"Hotspot de cambios: {count} commits lo tocan",
            detail="Cambia con mucha frecuencia -- candidato a revisar cobertura de tests y complejidad.",
            path=path,
        ))
    return findings


def _stale_branches(repo_path: Path) -> list[Finding]:
    out = _git(
        repo_path, "for-each-ref", "--format=%(refname:short)|%(committerdate:unix)",
        "refs/heads", "refs/remotes",
    )
    if not out:
        return []
    now = time.time()
    findings: list[Finding] = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, _, ts = line.partition("|")
        if not ts.strip().isdigit():
            continue
        age_days = (now - int(ts)) / 86400
        if name.endswith("/HEAD"):
            continue
        if age_days > _STALE_BRANCH_DAYS:
            findings.append(Finding(
                severity="info",
                title=f"Rama sin commits desde hace {int(age_days)} días: {name}",
                detail="Candidata a borrar si ya no está en uso.",
            ))
    return findings


def _large_tracked_files(repo_path: Path) -> list[Finding]:
    out = _git(repo_path, "ls-files")
    if out is None:
        return []
    findings: list[Finding] = []
    for rel in out.splitlines():
        if not rel:
            continue
        full = repo_path / rel
        try:
            size = full.stat().st_size
        except OSError:
            continue
        if size > _LARGE_FILE_BYTES:
            findings.append(Finding(
                severity="low",
                title=f"Fichero grande en el repo: {size / (1024 * 1024):.1f} MB",
                detail="Considera Git LFS o excluirlo si es un artefacto generado/binario.",
                path=rel,
            ))
    return findings


class GitHotspotsCheck:
    name = "git_hotspots"
    description = "Hotspots de cambio, ramas obsoletas y ficheros enormes según el historial de git."

    def run(self, repo_path: Path) -> CheckResult:
        if not _is_git_repo(repo_path):
            return CheckResult(
                check_name=self.name,
                summary="No aplica: no es un repositorio git.",
                error="not_a_git_repo",
            )

        findings = [
            *_churn_hotspots(repo_path),
            *_stale_branches(repo_path),
            *_large_tracked_files(repo_path),
        ]
        summary = f"{len(findings)} hallazgo(s) sobre el historial de git."
        return CheckResult(check_name=self.name, summary=summary, findings=findings)
