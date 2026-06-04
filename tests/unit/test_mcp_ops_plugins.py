"""Unit tests for plugin handling in cabal.mcp_ops.

Covers `claude_plugin_list` parsing, `claude_plugin_set_enabled` command shape,
and the plugin-server merge in `enumerate_mcp_servers` (incl. disabled plugins,
which are absent from `claude mcp list`).
"""

from __future__ import annotations

import json

import cabal.mcp_ops as m


def test_claude_plugin_list_valid_json_returns_list(monkeypatch):
    payload = [{"id": "azure@official", "enabled": True, "scope": "project"}]
    monkeypatch.setattr(
        m, "_run_claude_cli", lambda *a, **k: (0, json.dumps(payload), "")
    )

    result = m.claude_plugin_list()

    assert result == payload


def test_claude_plugin_list_nonzero_exit_returns_empty(monkeypatch):
    monkeypatch.setattr(m, "_run_claude_cli", lambda *a, **k: (1, "", "boom"))

    assert m.claude_plugin_list() == []


def test_claude_plugin_list_json_with_leading_noise_recovers_array(monkeypatch):
    noisy = "Checking…\n" + json.dumps([{"id": "x@y"}]) + "\n"
    monkeypatch.setattr(m, "_run_claude_cli", lambda *a, **k: (0, noisy, ""))

    assert m.claude_plugin_list() == [{"id": "x@y"}]


def test_claude_plugin_set_enabled_disable_passes_subcommand_and_scope(monkeypatch):
    captured = {}

    def fake_run(args, timeout=30):
        captured["args"] = args
        return 0, "Disabled", ""

    monkeypatch.setattr(m, "_run_claude_cli", fake_run)

    ok, _ = m.claude_plugin_set_enabled(
        "azure@official", enabled=False, scope="project"
    )

    assert ok is True
    assert captured["args"] == ["plugin", "disable", "azure@official", "-s", "project"]


def test_claude_plugin_set_enabled_enable_passes_enable_subcommand(monkeypatch):
    captured = {}

    def fake_run(args, timeout=30):
        captured["args"] = args
        return 0, "Enabled", ""

    monkeypatch.setattr(m, "_run_claude_cli", fake_run)

    m.claude_plugin_set_enabled("foo@mkt", enabled=True)

    assert captured["args"] == ["plugin", "enable", "foo@mkt"]


def _stub_enumerate_sources(monkeypatch, plugins, mcp_list=None):
    monkeypatch.setattr(m, "_claude_dot_json", lambda: {})
    monkeypatch.setattr(m, "_load_mcp_templates", lambda: {})
    monkeypatch.setattr(m, "_claude_mcp_list", lambda: mcp_list or [])
    monkeypatch.setattr(m, "claude_plugin_list", lambda available=False: plugins)


def test_enumerate_mcp_servers_disabled_plugin_server_still_listed(monkeypatch):
    plugins = [
        {
            "id": "foo@mkt",
            "enabled": False,
            "scope": "user",
            "mcpServers": {"bar": {"type": "http", "url": "https://example/mcp"}},
        }
    ]
    _stub_enumerate_sources(monkeypatch, plugins)

    entry = m.enumerate_mcp_servers()["plugin:foo:bar"]

    assert entry["plugin_enabled"] is False
    assert entry["plugin_id"] == "foo@mkt"
    assert entry["plugin_scope"] == "user"
    assert entry["command_line"] == "https://example/mcp"
    assert entry["is_plugin"] is True


def test_enumerate_mcp_servers_enabled_connected_plugin_marked_active(monkeypatch):
    plugins = [
        {
            "id": "azure@official",
            "enabled": True,
            "scope": "project",
            "mcpServers": {"azure": {"command": "npx", "args": ["-y", "@azure/mcp"]}},
        }
    ]
    mcp_list = [
        {
            "name": "plugin:azure:azure",
            "command_line": "npx -y @azure/mcp",
            "connected": True,
            "status_text": "Connected",
        }
    ]
    _stub_enumerate_sources(monkeypatch, plugins, mcp_list)

    entry = m.enumerate_mcp_servers()["plugin:azure:azure"]

    assert entry["active"] is True
    assert entry["plugin_enabled"] is True
    assert entry["plugin_id"] == "azure@official"
