from pathlib import Path

from repo_health.plugin import CheckResult
from repo_health.runner import discover_checks, run_checks


def test_discover_checks_encuentra_los_incorporados():
    checks = discover_checks()
    for name in ("secrets", "dead_files", "git_hotspots", "stale_deps"):
        assert name in checks, f"falta el check incorporado {name!r}"


def test_run_checks_only_filtra(tmp_path: Path):
    results = run_checks(tmp_path, only={"secrets"})
    assert [r.check_name for r in results] == ["secrets"]


def test_run_checks_skip_excluye(tmp_path: Path):
    results = run_checks(tmp_path, skip={"secrets", "dead_files", "git_hotspots", "stale_deps"})
    assert results == []


class _BoomCheck:
    name = "boom"
    description = "siempre falla"

    def run(self, repo_path: Path) -> CheckResult:
        raise RuntimeError("kaboom")


def test_run_checks_aisla_un_check_que_falla(tmp_path: Path, monkeypatch):
    import repo_health.runner as runner_mod

    monkeypatch.setattr(runner_mod, "discover_checks", lambda: {"boom": _BoomCheck})
    results = run_checks(tmp_path)
    assert len(results) == 1
    assert results[0].error is not None
    assert "kaboom" in results[0].summary
