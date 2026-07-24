import json

from checkforge.plugin import CheckResult, Finding
from checkforge.report import Report


def _report() -> Report:
    return Report(
        repo_path="/tmp/demo",
        results=[
            CheckResult(
                check_name="secrets",
                summary="2 hallazgos",
                findings=[
                    Finding(severity="high", title="clave privada", path="a.py", line=3),
                    Finding(severity="info", title="ip privada", path="b.py"),
                ],
            ),
            CheckResult(check_name="broken", summary="fallo", error="boom"),
        ],
    )


def test_total_findings_cuenta_bien():
    assert _report().total_findings == 2


def test_counts_by_severity():
    counts = _report().counts_by_severity
    assert counts["high"] == 1
    assert counts["info"] == 1
    assert counts["medium"] == 0


def test_failed_checks():
    failed = _report().failed_checks
    assert len(failed) == 1
    assert failed[0].check_name == "broken"


def test_to_json_es_json_valido_y_completo():
    data = json.loads(_report().to_json())
    assert data["total_findings"] == 2
    assert data["repo_path"] == "/tmp/demo"
    assert len(data["checks"]) == 2


def test_to_console_incluye_hallazgos_y_resumen():
    text = _report().to_console()
    assert "clave privada" in text
    assert "a.py:3" in text
    assert "[HIGH" in text
    assert "Total: 2 hallazgo" in text
    assert "1 check(s) no se pudieron ejecutar" in text
