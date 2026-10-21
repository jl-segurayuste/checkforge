from pathlib import Path

from checkforge.checks.readme_drift import ReadmeDriftCheck
from tests.conftest import commit_all


def _write_pyproject(repo: Path, requires_python: str = ">=3.11", scripts: dict | None = None) -> None:
    scripts_block = ""
    if scripts:
        lines = "\n".join(f'{k} = "{v}"' for k, v in scripts.items())
        scripts_block = f"\n[project.scripts]\n{lines}\n"
    (repo / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "0.1"\n'
        f'requires-python = "{requires_python}"\n'
        f"{scripts_block}"
    )


def test_sin_pyproject_no_aplica(git_repo: Path):
    (git_repo / "README.md").write_text("hola\n")
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    assert result.findings == []
    assert "No aplica" in result.summary


def test_sin_readme_no_aplica(git_repo: Path):
    _write_pyproject(git_repo)
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    assert result.findings == []
    assert "No aplica" in result.summary


def test_version_desactualizada_en_readme_se_marca(git_repo: Path):
    _write_pyproject(git_repo, requires_python=">=3.12")
    (git_repo / "README.md").write_text("Requiere Python 3.8 o superior.\n")
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("Python 3.8" in t and "3.12" in t for t in titles)


def test_version_consistente_no_se_marca(git_repo: Path):
    _write_pyproject(git_repo, requires_python=">=3.11")
    (git_repo / "README.md").write_text("Requiere Python 3.11 o superior.\n")
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    assert result.findings == []


def test_comando_sin_documentar_se_marca(git_repo: Path):
    _write_pyproject(git_repo, scripts={"mi-cli": "mipaquete.cli:main"})
    (git_repo / "README.md").write_text("Este proyecto hace cosas.\n")
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("mi-cli" in t for t in titles)


def test_comando_documentado_no_se_marca(git_repo: Path):
    _write_pyproject(git_repo, scripts={"mi-cli": "mipaquete.cli:main"})
    (git_repo / "README.md").write_text("Uso: `mi-cli --help`\n")
    commit_all(git_repo)
    result = ReadmeDriftCheck().run(git_repo)
    assert result.findings == []


def test_version_en_un_ejemplo_no_es_un_requisito(tmp_path):
    """Falso positivo real (staleif): "workaround para python 3.7" en un ejemplo de salida."""
    from checkforge.checks.readme_drift import ReadmeDriftCheck
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.11"\n')
    (tmp_path / "README.md").write_text(
        "Encuentra workarounds viejos.\n\n```\nAñadido por alguien: \"workaround para python 3.7\"\n```\n\n"
        "Lo escribió alguien para python 3.8 en su día.\n")
    assert ReadmeDriftCheck().run(tmp_path).findings == []
    (tmp_path / "README.md").write_text("## Requisitos\n\nPython 3.9 o superior.\n\nTambién vale python >= 3.8.\n")
    titles = [f.title for f in ReadmeDriftCheck().run(tmp_path).findings]
    assert any("3.9" in t for t in titles) and any("3.8" in t for t in titles)
