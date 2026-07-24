from pathlib import Path

from auditkit.checks.git_hotspots import GitHotspotsCheck
from tests.conftest import commit_all


def test_repo_no_git_devuelve_error(tmp_path: Path):
    result = GitHotspotsCheck().run(tmp_path)
    assert result.error == "not_a_git_repo"


def test_hotspot_de_churn_se_detecta(git_repo: Path):
    target = git_repo / "caliente.py"
    for i in range(6):
        target.write_text(f"version {i}\n")
        commit_all(git_repo, f"cambio {i}")
    result = GitHotspotsCheck().run(git_repo)
    titles = [f.title for f in result.findings if f.path == "caliente.py"]
    assert any("Hotspot de cambios" in t for t in titles)


def test_fichero_con_pocos_cambios_no_es_hotspot(git_repo: Path):
    (git_repo / "tranquilo.py").write_text("x = 1\n")
    commit_all(git_repo, "unico commit")
    result = GitHotspotsCheck().run(git_repo)
    titles = [f.title for f in result.findings if f.path == "tranquilo.py"]
    assert titles == []


def test_fichero_grande_se_marca(git_repo: Path):
    big = git_repo / "grande.bin"
    big.write_bytes(b"0" * (2 * 1024 * 1024))
    commit_all(git_repo)
    result = GitHotspotsCheck().run(git_repo)
    hits = [f for f in result.findings if f.path == "grande.bin"]
    assert len(hits) == 1
    assert hits[0].severity == "low"


def test_repo_vacio_no_falla(git_repo: Path):
    result = GitHotspotsCheck().run(git_repo)
    assert result.error is None
