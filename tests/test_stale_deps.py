from pathlib import Path

from checkforge.checks.stale_deps import StaleDepsCheck
from tests.conftest import commit_all


def test_sin_requirements_ni_pyproject_no_aplica(git_repo: Path):
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    assert result.error is None
    assert result.findings == []
    assert "No aplica" in result.summary


def test_requirements_txt_vacio_sigue_detectando_imports_sin_declarar(git_repo: Path):
    # requirements.txt EXISTE pero no declara nada -- no es lo mismo que
    # "no existe": debe seguir comprobando imports de terceros sin declarar.
    (git_repo / "requirements.txt").write_text("")
    (git_repo / "main.py").write_text("import requests\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    assert result.error is None
    info_titles = [f.title for f in result.findings if f.severity == "info"]
    assert any("requests" in t for t in info_titles)


def test_dependencia_declarada_no_usada_se_marca(git_repo: Path):
    (git_repo / "requirements.txt").write_text("requests==2.31.0\nclick>=8\n")
    (git_repo / "main.py").write_text("import click\nclick.echo('hola')\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("requests" in t and "no importada" in t for t in titles)
    assert not any("click" in t and "no importada" in t for t in titles)


def test_mapeo_paquete_a_import_pyyaml(git_repo: Path):
    (git_repo / "requirements.txt").write_text("pyyaml==6.0\n")
    (git_repo / "main.py").write_text("import yaml\nyaml.safe_load('a: 1')\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert not any("pyyaml" in t for t in titles)


def test_pyproject_toml_se_lee(git_repo: Path):
    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1"\n'
        'dependencies = ["requests==2.31.0"]\n'
    )
    (git_repo / "main.py").write_text("print('hola')\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("requests" in t for t in titles)


def test_import_sin_declarar_se_marca_como_info(git_repo: Path):
    (git_repo / "requirements.txt").write_text("click>=8\n")
    (git_repo / "main.py").write_text("import click\nimport arrow\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    info_titles = [f.title for f in result.findings if f.severity == "info"]
    assert any("arrow" in t for t in info_titles)


def test_paquete_propio_del_repo_no_se_marca_como_sin_declarar(git_repo: Path):
    (git_repo / "requirements.txt").write_text("click>=8\n")
    (git_repo / "mipaquete").mkdir()
    (git_repo / "mipaquete" / "__init__.py").write_text("")
    (git_repo / "main.py").write_text("import click\nimport mipaquete\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    info_titles = [f.title for f in result.findings if f.severity == "info"]
    assert not any("mipaquete" in t for t in info_titles)


def test_modulos_de_stdlib_no_se_marcan_como_sin_declarar(git_repo: Path):
    (git_repo / "requirements.txt").write_text("click>=8\n")
    (git_repo / "main.py").write_text("import click\nimport json\nimport os\n")
    commit_all(git_repo)
    result = StaleDepsCheck().run(git_repo)
    info_titles = [f.title for f in result.findings if f.severity == "info"]
    assert not any("json" in t or "os" in t for t in info_titles)


def test_herramientas_y_dependencias_implicitas_no_se_marcan(git_repo):
    """Falsos positivos reales: ruff/pytest en el extra dev, y python-multipart/itsdangerous/httpx con FastAPI."""
    from checkforge.checks.stale_deps import StaleDepsCheck
    from tests.conftest import commit_all
    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi", "python-multipart", "itsdangerous", "requests"]\n'
        '[project.optional-dependencies]\ndev = ["ruff", "pytest", "pytest-playwright", "httpx"]\n')
    (git_repo / "app.py").write_text("from fastapi import FastAPI\n")
    commit_all(git_repo)
    titles = [f.title for f in StaleDepsCheck().run(git_repo).findings]
    assert titles == ["Dependencia declarada pero no importada en ningún fichero: requests"]


def test_modulos_locales_de_subdirectorios_no_se_marcan(git_repo: Path):
    """pytest mete tests/ en el path: `from conftest import x` no es una dependencia."""
    (git_repo / "requirements.txt").write_text("click>=8\n")
    (git_repo / "tests").mkdir()
    (git_repo / "tests" / "conftest.py").write_text("x = 1\n")
    (git_repo / "tests" / "test_a.py").write_text("import click\nfrom conftest import x\n")
    (git_repo / "src" / "mipkg").mkdir(parents=True)
    (git_repo / "src" / "mipkg" / "__init__.py").write_text("")
    (git_repo / "app.py").write_text("import mipkg\n")
    commit_all(git_repo)
    info_titles = [f.title for f in StaleDepsCheck().run(git_repo).findings if f.severity == "info"]
    assert not any("conftest" in t or "mipkg" in t for t in info_titles)


def test_entorno_virtual_sin_versionar_no_oculta_dependencias(git_repo: Path):
    (git_repo / "requirements.txt").write_text("click>=8\n")
    (git_repo / "env" / "lib" / "requests").mkdir(parents=True)
    (git_repo / "env" / "lib" / "requests" / "__init__.py").write_text("")
    (git_repo / "env" / "lib" / "requests.py").write_text("")
    (git_repo / ".gitignore").write_text("env/\n")
    (git_repo / "main.py").write_text("import click\nimport requests\n")
    commit_all(git_repo)
    info_titles = [f.title for f in StaleDepsCheck().run(git_repo).findings if f.severity == "info"]
    assert any("requests" in t for t in info_titles)
