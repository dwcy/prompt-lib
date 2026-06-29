# -*- coding: utf-8 -*-
"""MCP template visibility test — headroom template loads and surfaces as an un-registered 'template' scope."""

from __future__ import annotations

from pathlib import Path

from cabal import mcp_ops

HEADROOM_NAME = "headroom"
TEMPLATE_SCOPE = "template"


def test_headroom_template_definition_loads():
    templates = mcp_ops._load_mcp_templates()

    headroom = templates[HEADROOM_NAME]

    assert headroom["command"] == "headroom"
    assert headroom["args"] == ["mcp", "serve"]
    assert headroom["env_required"] == []
    assert headroom["default_enabled"] is False


def test_headroom_unregistered_template_tagged_template_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_ops, "_claude_mcp_list", lambda *a, **k: [])
    monkeypatch.setattr(mcp_ops, "claude_plugin_list", lambda *a, **k: [])
    monkeypatch.setattr(mcp_ops, "_claude_dot_json", lambda *a, **k: {})

    servers = mcp_ops.enumerate_mcp_servers(project_dir=tmp_path)

    assert TEMPLATE_SCOPE in servers[HEADROOM_NAME]["scopes"]
