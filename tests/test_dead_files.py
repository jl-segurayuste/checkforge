from pathlib import Path

from checkforge.checks.dead_files import DeadFilesCheck
from tests.conftest import commit_all


def test_fichero_no_importado_se_marca(git_repo: Path):
    (git_repo / "huerfano.py").write_text("def f():\n    pass\n")
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    result = DeadFilesCheck().run(git_repo)
    paths = [f.path for f in result.findings]
    assert "huerfano.py" in paths
    # main.py no es importado por nadie tampoco, pero no es su culpa --
    # ambos son "hoja"; lo importante es que huerfano SI sale.


def test_fichero_importado_no_se_marca(git_repo: Path):
    (git_repo / "usado.py").write_text("VALOR = 1\n")
    (git_repo / "main.py").write_text("import usado\nprint(usado.VALOR)\n")
    commit_all(git_repo)
    result = DeadFilesCheck().run(git_repo)
    paths = [f.path for f in result.findings]
    assert "usado.py" not in paths


def test_from_import_tambien_cuenta(git_repo: Path):
    (git_repo / "pkg").mkdir()
    (git_repo / "pkg" / "__init__.py").write_text("")
    (git_repo / "pkg" / "helpers.py").write_text("def h(): pass\n")
    (git_repo / "main.py").write_text("from pkg.helpers import h\nh()\n")
    commit_all(git_repo)
    result = DeadFilesCheck().run(git_repo)
    paths = [f.path for f in result.findings]
    assert "pkg/helpers.py" not in paths


def test_init_y_tests_se_excluyen_siempre(git_repo: Path):
    (git_repo / "pkg").mkdir()
    (git_repo / "pkg" / "__init__.py").write_text("")
    (git_repo / "tests").mkdir()
    (git_repo / "tests" / "test_algo.py").write_text("def test_x(): assert True\n")
    commit_all(git_repo)
    result = DeadFilesCheck().run(git_repo)
    paths = [f.path for f in result.findings]
    assert "pkg/__init__.py" not in paths
    assert "tests/test_algo.py" not in paths


def test_repo_no_git_devuelve_error(tmp_path: Path):
    result = DeadFilesCheck().run(tmp_path)
    assert result.error == "not_a_git_repo"


def test_repo_sin_python_no_falla(git_repo: Path):
    (git_repo / "README.md").write_text("hola\n")
    commit_all(git_repo)
    result = DeadFilesCheck().run(git_repo)
    assert result.error is None
    assert result.findings == []
