"""Agrega los CheckResult de una ejecución y los presenta: consola o JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .plugin import SEVERITIES, CheckResult

_SEVERITY_ORDER = {sev: i for i, sev in enumerate(reversed(SEVERITIES))}  # high primero


@dataclass
class Report:
    repo_path: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.results)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        counts = dict.fromkeys(SEVERITIES, 0)
        for r in self.results:
            for f in r.findings:
                counts[f.severity] += 1
        return counts

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [r for r in self.results if r.error is not None]

    def to_json(self) -> str:
        payload = {
            "repo_path": self.repo_path,
            "total_findings": self.total_findings,
            "counts_by_severity": self.counts_by_severity,
            "checks": [r.model_dump() for r in self.results],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def to_console(self) -> str:
        lines: list[str] = [f"auditkit — {self.repo_path}", ""]

        for result in self.results:
            lines.append(f"── {result.check_name} " + "─" * max(0, 40 - len(result.check_name)))
            if result.error is not None:
                lines.append(f"  aviso: el check falló ({result.summary})")
                lines.append("")
                continue
            lines.append(f"  {result.summary}")
            findings_sorted = sorted(
                result.findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 0)
            )
            for f in findings_sorted:
                label = f"[{f.severity.upper():<6}]"
                loc = f" ({f.path})" if f.path else ""
                if f.line is not None:
                    loc = f" ({f.path}:{f.line})" if f.path else f" (línea {f.line})"
                lines.append(f"  {label} {f.title}{loc}")
                if f.detail:
                    lines.append(f"           {f.detail}")
            lines.append("")

        counts = self.counts_by_severity
        summary_parts = [f"{counts[s]} {s}" for s in reversed(SEVERITIES) if counts[s]]
        summary = ", ".join(summary_parts) if summary_parts else "sin hallazgos"
        lines.append(f"Total: {self.total_findings} hallazgo(s) — {summary}")
        if self.failed_checks:
            names = ", ".join(r.check_name for r in self.failed_checks)
            lines.append(f"aviso: {len(self.failed_checks)} check(s) no se pudieron ejecutar: {names}")
        return "\n".join(lines)
