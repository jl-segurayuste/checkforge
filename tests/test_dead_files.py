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


def test_from_paquete_import_submodulo_cuenta(git_repo: Path):
    """Falso positivo real (composeready, pushward): `from .checks import gpu` y `from pkg import mod`."""
    (git_repo / "app" / "checks").mkdir(parents=True)
    for f in ("app/__init__.py", "app/checks/__init__.py"):
        (git_repo / f).write_text("")
    (git_repo / "app" / "checks" / "gpu.py").write_text("def check(): pass\n")
    (git_repo / "app" / "hook.py").write_text("def install(): pass\n")
    (git_repo / "app" / "cli.py").write_text("from .checks import gpu\nfrom app import hook\n")
    (git_repo / "pyproject.toml").write_text('[project]\nname = "app"\n[project.scripts]\napp = "app.cli:main"\n')
    commit_all(git_repo)
    paths = [f.path for f in DeadFilesCheck().run(git_repo).findings]
    assert "app/checks/gpu.py" not in paths and "app/hook.py" not in paths
    assert "app/cli.py" not in paths                     # punto de entrada de [project.scripts]


def test_import_relativo_de_dos_niveles(git_repo: Path):
    (git_repo / "a" / "b").mkdir(parents=True)
    for f in ("a/__init__.py", "a/b/__init__.py"):
        (git_repo / f).write_text("")
    (git_repo / "a" / "util.py").write_text("X = 1\n")
    (git_repo / "a" / "b" / "mod.py").write_text("from ..util import X\n")
    (git_repo / "main.py").write_text("import a.b.mod\n")
    commit_all(git_repo)
    paths = [f.path for f in DeadFilesCheck().run(git_repo).findings]
    assert "a/util.py" not in paths and "a/b/mod.py" not in paths


def test_python_m_y_directorios_de_ansible(git_repo: Path):
    """`python -m pkg.hashpw` en el README y los módulos de `library/` (los carga Ansible)."""
    (git_repo / "pkg").mkdir()
    (git_repo / "pkg" / "__init__.py").write_text("")
    (git_repo / "pkg" / "hashpw.py").write_text("print('hash')\n")
    (git_repo / "roles" / "ad" / "library").mkdir(parents=True)
    (git_repo / "roles" / "ad" / "library" / "win_user.py").write_text("def main(): pass\n")
    (git_repo / "README.md").write_text("Genera el hash con `python -m pkg.hashpw`.\n")
    (git_repo / "suelto.py").write_text("x = 1\n")
    commit_all(git_repo)
    paths = [f.path for f in DeadFilesCheck().run(git_repo).findings]
    assert "pkg/hashpw.py" not in paths and "roles/ad/library/win_user.py" not in paths
    assert "suelto.py" in paths                          # el resto se sigue detectando


def test_scripts_y_tests_fuera_de_tests_no_se_marcan(git_repo: Path):
    """Falsos positivos reales: e2e/test_panel.py y network-tools/ip-diagnostics.py."""
    (git_repo / "e2e").mkdir()
    (git_repo / "e2e" / "test_panel.py").write_text("def test_x(): pass\n")
    (git_repo / "tools").mkdir()
    (git_repo / "tools" / "ip-diagnostics.py").write_text("print('x')\n")
    (git_repo / "tools" / "backup.py").write_text("#!/usr/bin/env python3\nprint('x')\n")
    (git_repo / "tools" / "modulo.py").write_text("X = 1\n")
    commit_all(git_repo)
    paths = [f.path for f in DeadFilesCheck().run(git_repo).findings]
    assert paths == ["tools/modulo.py"]
