# -*- coding: utf-8 -*-
"""Registration smoke test — okf-rag is wired into mcp-templates.json and the cabal console scripts."""

from __future__ import annotations

import tomllib
from pathlib import Path

from cabal import mcp_ops

OKF_RAG_KEY = "okf-rag"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_okf_rag_template_definition_loads():
    templates = mcp_ops._load_mcp_templates()

    okf_rag = templates[OKF_RAG_KEY]

    assert okf_rag["command"] == "cabal-okf-rag"
    assert okf_rag["args"] == []


def test_okf_rag_template_is_opt_in():
    templates = mcp_ops._load_mcp_templates()

    assert templates[OKF_RAG_KEY]["default_enabled"] is False


def test_okf_rag_console_script_points_at_server_main():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["cabal-okf-rag"] == "cabal.okf.mcp_server:main"
