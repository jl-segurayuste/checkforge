from pathlib import Path

from repo_health.checks.readme_drift import ReadmeDriftCheck
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
