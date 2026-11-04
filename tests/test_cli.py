import json
from pathlib import Path

from checkforge.cli import main
from tests.conftest import commit_all


def test_list_checks(capsys):
    rc = main(["list-checks"])
    out = capsys.readouterr().out
    assert rc == 0
    for name in ("secrets", "dead_files", "git_hotspots", "stale_deps"):
        assert name in out


def test_analyze_ruta_invalida(capsys):
    rc = main(["analyze", "/no/existe/de/verdad"])
    assert rc == 2


def test_analyze_consola(git_repo: Path, capsys):
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    rc = main(["analyze", str(git_repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "checkforge" in out
    assert "Total:" in out


def test_analyze_json(git_repo: Path, capsys):
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    rc = main(["analyze", str(git_repo), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert "checks" in data


def test_analyze_only_filtra(git_repo: Path, capsys):
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    rc = main(["analyze", str(git_repo), "--only", "secrets", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert [c["check_name"] for c in data["checks"]] == ["secrets"]
    assert rc == 0


def test_fail_on_devuelve_1_si_hay_hallazgo_al_nivel_o_por_encima(git_repo: Path, capsys):
    (git_repo / "key.pem").write_text("-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n")
    commit_all(git_repo)
    rc = main(["analyze", str(git_repo), "--only", "secrets", "--fail-on", "high"])
    capsys.readouterr()
    assert rc == 1


def test_fail_on_devuelve_0_si_no_hay_hallazgos_al_nivel(git_repo: Path, capsys):
    (git_repo / "README.md").write_text("nada sensible aqui\n")
    commit_all(git_repo)
    rc = main(["analyze", str(git_repo), "--only", "secrets", "--fail-on", "high"])
    capsys.readouterr()
    assert rc == 0


def test_check_desconocido_sale_2(tmp_path, capsys):
    from checkforge.cli import main

    assert main(["analyze", str(tmp_path), "--only", "no_existe"]) == 2
    assert "no_existe" in capsys.readouterr().err


def test_check_que_revienta_sale_2(tmp_path, monkeypatch, capsys):
    from checkforge import cli
    from checkforge.plugin import CheckResult

    monkeypatch.setattr(cli, "run_checks", lambda *a, **k: [
        CheckResult(check_name="roto", summary="El check falló", error="Traceback..."),
    ])
    assert cli.main(["analyze", str(tmp_path)]) == 2
    assert "roto" in capsys.readouterr().err


def test_carpeta_sin_git_no_es_fallo(tmp_path):
    from checkforge.cli import main

    assert main(["analyze", str(tmp_path), "--only", "dead_files"]) == 0
