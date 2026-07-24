"""CLI: `checkforge analyze <ruta>`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .plugin import SEVERITIES
from .report import Report
from .runner import discover_checks, run_checks

_SEVERITY_RANK = {sev: i for i, sev in enumerate(SEVERITIES)}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="checkforge",
        description="Agregador de auditorías de repositorios (dependencias, secretos, "
        "código muerto, hotspots de git...) en un único informe.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analiza un repositorio")
    analyze.add_argument("path", nargs="?", default=".", help="Ruta al repositorio (por defecto: .)")
    analyze.add_argument(
        "--only", metavar="CHECK", action="append", default=None,
        help="Ejecutar solo este check (repetible)",
    )
    analyze.add_argument(
        "--skip", metavar="CHECK", action="append", default=None,
        help="Excluir este check (repetible)",
    )
    analyze.add_argument("--json", action="store_true", help="Salida en JSON en vez de consola")
    analyze.add_argument(
        "--fail-on", metavar="SEVERITY", choices=SEVERITIES, default=None,
        help="Salir con código != 0 si hay algún hallazgo de esta severidad o mayor",
    )

    sub.add_parser("list-checks", help="Lista los checks instalados (propios y de terceros)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-checks":
        checks = discover_checks()
        if not checks:
            print("No hay ningún check instalado.")
            return 0
        for name, cls in sorted(checks.items()):
            desc = getattr(cls, "description", "")
            print(f"{name}: {desc}")
        return 0

    # analyze
    repo_path = Path(args.path).resolve()
    if not repo_path.is_dir():
        print(f"error: {repo_path} no es un directorio", file=sys.stderr)
        return 2

    only = set(args.only) if args.only else None
    skip = set(args.skip) if args.skip else None
    results = run_checks(repo_path, only=only, skip=skip)
    report = Report(repo_path=str(repo_path), results=results)

    if args.json:
        print(report.to_json())
    else:
        print(report.to_console())

    if args.fail_on is not None:
        threshold = _SEVERITY_RANK[args.fail_on]
        for result in results:
            for finding in result.findings:
                if _SEVERITY_RANK.get(finding.severity, 0) >= threshold:
                    return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
