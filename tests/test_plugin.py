import pytest

from auditkit.plugin import CheckResult, Finding


def test_finding_acepta_severidad_valida():
    f = Finding(severity="high", title="x")
    assert f.severity == "high"


def test_finding_rechaza_severidad_invalida():
    with pytest.raises(ValueError):
        Finding(severity="catastrofico", title="x")


def test_check_result_por_defecto_sin_hallazgos():
    result = CheckResult(check_name="demo", summary="ok")
    assert result.findings == []
    assert result.error is None
