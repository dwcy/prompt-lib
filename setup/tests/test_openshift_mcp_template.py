# -*- coding: utf-8 -*-
"""MCP template visibility test — openshift template loads and surfaces as an un-registered 'template' scope."""

from __future__ import annotations

from cabal import mcp_ops
from cabal._paths import GLOBAL_DIR

OPENSHIFT_NAME = "openshift"
TEMPLATE_SCOPE = "template"


def test_openshift_template_definition_loads():
    templates = mcp_ops._load_mcp_templates()

    openshift = templates[OPENSHIFT_NAME]

    assert openshift["command"] == "pnpm"
    assert openshift["args"] == ["dlx", "kubernetes-mcp-server@latest"]
    assert openshift["env_required"] == []
    assert openshift["default_enabled"] is False


def test_openshift_unregistered_template_tagged_template_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_ops, "_claude_mcp_list", lambda *a, **k: [])
    monkeypatch.setattr(mcp_ops, "claude_plugin_list", lambda *a, **k: [])
    monkeypatch.setattr(mcp_ops, "_claude_dot_json", lambda *a, **k: {})

    servers = mcp_ops.enumerate_mcp_servers(project_dir=tmp_path)

    assert TEMPLATE_SCOPE in servers[OPENSHIFT_NAME]["scopes"]


def test_openshift_absent_from_plugin_manifest():
    import json

    manifest = json.loads((GLOBAL_DIR / ".mcp.json").read_text(encoding="utf-8"))

    assert OPENSHIFT_NAME not in manifest["mcpServers"]
