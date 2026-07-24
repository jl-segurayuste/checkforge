import json
from pathlib import Path

from repo_health_js_example.check import JsStaleDepsCheck
from tests.conftest import commit_all


def _write_pkg_json(repo: Path, deps: dict, dev_deps: dict | None = None) -> None:
    (repo / "package.json").write_text(json.dumps({
        "name": "demo",
        "version": "1.0.0",
        "dependencies": deps,
        "devDependencies": dev_deps or {},
    }))


def test_sin_package_json_no_aplica(git_repo: Path):
    (git_repo / "index.js").write_text("console.log('hola')\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    assert result.error is None
    assert result.findings == []
    assert "No aplica" in result.summary


def test_dependencia_no_usada_se_marca(git_repo: Path):
    _write_pkg_json(git_repo, {"lodash": "^4.17.0", "express": "^4.18.0"})
    (git_repo / "server.js").write_text("const express = require('express');\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("lodash" in t and "no importada" in t for t in titles)
    assert not any("express" in t and "no importada" in t for t in titles)


def test_import_es6_tambien_cuenta(git_repo: Path):
    _write_pkg_json(git_repo, {"react": "^18.0.0"})
    (git_repo / "app.jsx").write_text("import React from 'react';\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    assert result.findings == []


def test_scoped_package_se_reconoce(git_repo: Path):
    _write_pkg_json(git_repo, {"@testing-library/react": "^14.0.0"})
    (git_repo / "app.test.tsx").write_text("import { render } from '@testing-library/react';\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    assert result.findings == []


def test_import_relativo_no_cuenta_como_paquete(git_repo: Path):
    _write_pkg_json(git_repo, {"lodash": "^4.17.0"})
    (git_repo / "utils.js").write_text("module.exports = {};\n")
    (git_repo / "main.js").write_text("const utils = require('./utils');\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    titles = [f.title for f in result.findings]
    assert any("lodash" in t for t in titles)  # sigue sin usarse -> se marca
    assert not any("utils" in t for t in titles)  # import relativo, no es un paquete


def test_import_sin_declarar_se_marca_info(git_repo: Path):
    _write_pkg_json(git_repo, {})
    (git_repo / "main.js").write_text("const axios = require('axios');\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    info = [f for f in result.findings if f.severity == "info"]
    assert any("axios" in f.title for f in info)


def test_builtin_de_node_no_se_marca(git_repo: Path):
    _write_pkg_json(git_repo, {})
    (git_repo / "main.js").write_text("const fs = require('fs');\nconst path = require('path');\n")
    commit_all(git_repo)
    result = JsStaleDepsCheck().run(git_repo)
    assert result.findings == []
