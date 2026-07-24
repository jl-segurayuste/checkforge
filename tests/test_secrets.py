from pathlib import Path

from checkforge.checks.secrets import SecretsCheck
from tests.conftest import commit_all


def _findings_by_title_prefix(result, prefix: str):
    return [f for f in result.findings if f.title.startswith(prefix)]


def test_detecta_clave_privada_pem(git_repo: Path):
    (git_repo / "key.pem").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----\n"
    )
    commit_all(git_repo)
    result = SecretsCheck().run(git_repo)
    hits = _findings_by_title_prefix(result, "Posible secreto: Clave privada")
    assert len(hits) == 1
    assert hits[0].severity == "high"


def test_detecta_token_de_github(git_repo: Path):
    (git_repo / "config.py").write_text('TOKEN = "ghp_' + "a" * 36 + '"\n')
    commit_all(git_repo)
    result = SecretsCheck().run(git_repo)
    hits = _findings_by_title_prefix(result, "Posible secreto: GitHub token")
    assert len(hits) == 1


def test_asignacion_generica_no_placeholder_se_marca(git_repo: Path):
    (git_repo / "settings.py").write_text('password = "correcthorsebatterystaple"\n')
    commit_all(git_repo)
    result = SecretsCheck().run(git_repo)
    hits = _findings_by_title_prefix(result, "Asignación con aspecto de secreto")
    assert len(hits) == 1


def test_asignacion_generica_placeholder_no_se_marca(git_repo: Path):
    (git_repo / "settings.py").write_text('password = "changeme"\n')
    commit_all(git_repo)
    result = SecretsCheck().run(git_repo)
    hits = _findings_by_title_prefix(result, "Asignación con aspecto de secreto")
    assert hits == []


def test_ip_privada_se_marca_como_info(git_repo: Path):
    (git_repo / "notes.md").write_text("El servidor está en 192.168.1.100\n")
    commit_all(git_repo)
    result = SecretsCheck().run(git_repo)
    hits = _findings_by_title_prefix(result, "IP privada")
    assert len(hits) == 1
    assert hits[0].severity == "info"


def test_ficheros_no_trackeados_por_git_se_ignoran(git_repo: Path):
    (git_repo / "untracked.py").write_text('TOKEN = "ghp_' + "b" * 36 + '"\n')
    # No se hace commit_all -- el fichero queda sin trackear.
    result = SecretsCheck().run(git_repo)
    assert result.findings == []
