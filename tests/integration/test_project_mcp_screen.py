"""Integration tests for project-scope MCP file primitives (T076).

Exercises read_project_mcp / _write_project_mcp / _template_to_project_entry in
cabal.mcp_ops directly — no Textual driver, no async pilot. The screen's
DOM-coupled paths (_apply_servers, action_toggle) are covered by source-inspection
smoke checks since they require a mounted app.
"""

from __future__ import annotations

import inspect
import json
import pathlib

import pytest

import cabal.mcp_ops as mcp_ops
from cabal.views.project_mcp import ProjectMcpScreen


def test_write_project_mcp_creates_file_with_correct_shape(tmp_project_dir):
    entries = {"foo": {"command": "echo", "args": ["hi"], "env": {}}}

    mcp_ops._write_project_mcp(tmp_project_dir, entries)

    mcp_path = tmp_project_dir / ".mcp.json"
    assert mcp_path.exists()
    payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    assert payload == {"mcpServers": entries}


def test_write_project_mcp_round_trip_via_enumerate(tmp_project_dir, monkeypatch):
    monkeypatch.setattr(mcp_ops, "_claude_dot_json", lambda: {})
    monkeypatch.setattr(mcp_ops, "_claude_mcp_list", lambda: [])
    monkeypatch.setattr(mcp_ops, "_load_mcp_templates", lambda: {})
    monkeypatch.setattr(mcp_ops, "claude_plugin_list", lambda available=False: [])
    monkeypatch.chdir(tmp_project_dir)

    mcp_ops._write_project_mcp(
        tmp_project_dir, {"foo": {"command": "echo", "args": ["hi"], "env": {}}}
    )

    agg = mcp_ops.enumerate_mcp_servers()
    assert "foo" in agg
    assert "project" in agg["foo"]["scopes"]


def test_write_project_mcp_cleans_temp_files(tmp_project_dir):
    mcp_ops._write_project_mcp(
        tmp_project_dir, {"x": {"command": "y", "args": [], "env": {}}}
    )

    leftovers = list(tmp_project_dir.glob(".mcp.*.tmp"))
    assert leftovers == []


def test_write_project_mcp_invalid_json_payload_raises(tmp_project_dir):
    bad = {"bad": {"command": "x", "args": [pathlib.Path("/x")], "env": {}}}

    with pytest.raises(TypeError):
        mcp_ops._write_project_mcp(tmp_project_dir, bad)


@pytest.mark.parametrize("cmd", ["npx", "pnpm", "bunx"])
def test_template_to_entry_windows_wraps_pnpm_npx_bunx(monkeypatch, cmd):
    monkeypatch.setattr("cabal.mcp_ops.platform.system", lambda: "Windows")

    entry = mcp_ops._template_to_project_entry(
        {"command": cmd, "args": ["-y", "@upstash/context7-mcp"], "env_required": []}
    )

    assert entry == {
        "command": "cmd",
        "args": ["/s", "/c", f"{cmd} -y @upstash/context7-mcp"],
        "env": {},
    }


def test_template_to_entry_non_windows_passes_through(monkeypatch):
    monkeypatch.setattr("cabal.mcp_ops.platform.system", lambda: "Linux")

    entry = mcp_ops._template_to_project_entry(
        {"command": "npx", "args": ["-y", "@upstash/context7-mcp"], "env_required": []}
    )

    assert entry["command"] == "npx"
    assert entry["args"] == ["-y", "@upstash/context7-mcp"]


def test_template_to_entry_env_uses_placeholders(monkeypatch):
    monkeypatch.setattr("cabal.mcp_ops.platform.system", lambda: "Linux")

    entry = mcp_ops._template_to_project_entry(
        {"command": "x", "args": [], "env_required": ["FOO_TOKEN", "BAR_TOKEN"]}
    )

    assert entry["env"] == {"FOO_TOKEN": "${FOO_TOKEN}", "BAR_TOKEN": "${BAR_TOKEN}"}


def test_read_project_mcp_returns_empty_on_missing_file(tmp_project_dir):
    assert mcp_ops.read_project_mcp(tmp_project_dir) == {}


def test_read_project_mcp_returns_empty_on_corrupt_json(tmp_project_dir):
    (tmp_project_dir / ".mcp.json").write_text("garbage {", encoding="utf-8")

    assert mcp_ops.read_project_mcp(tmp_project_dir) == {}


def test_apply_servers_source_has_readonly_branch_and_scope_check():
    src = inspect.getsource(ProjectMcpScreen._apply_servers)

    assert "(read-only)" in src
    assert "is_plugin" in src
    assert '"project" in scopes' in src
    assert '"template" in scopes' in src
