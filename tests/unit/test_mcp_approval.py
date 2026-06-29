"""Unit tests for project-scoped MCP approval in cabal.mcp_ops + view logic.

Covers the non-interactive equivalent of Claude Code's startup trust prompt:
writing enabledMcpjsonServers / disabledMcpjsonServers under the project key in
~/.claude.json, and the UI's pending-state surfacing and button availability.
"""

from __future__ import annotations

import json
from pathlib import Path

import cabal.mcp_ops as m
from cabal.mcp_view_logic import action_button_states, server_row_cells


def _home(monkeypatch, tmp_path: Path, initial: dict | None = None) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    if initial is not None:
        (home / ".claude.json").write_text(json.dumps(initial), encoding="utf-8")
    monkeypatch.setattr(m.Path, "home", staticmethod(lambda: home))
    return home


def _read(home: Path) -> dict:
    return json.loads((home / ".claude.json").read_text(encoding="utf-8"))


def test_approve_adds_name_under_posix_project_key(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path, {"projects": {}})
    project = tmp_path / "repo"

    ok, _ = m.approve_project_mcp("playwright", project)

    proj = _read(home)["projects"][project.resolve().as_posix()]
    assert ok is True
    assert proj["enabledMcpjsonServers"] == ["playwright"]


def test_approve_removes_name_from_disabled_list(monkeypatch, tmp_path):
    project = tmp_path / "repo"
    key = project.resolve().as_posix()
    home = _home(
        monkeypatch,
        tmp_path,
        {"projects": {key: {"disabledMcpjsonServers": ["playwright", "other"]}}},
    )

    m.approve_project_mcp("playwright", project)

    proj = _read(home)["projects"][key]
    assert proj["enabledMcpjsonServers"] == ["playwright"]
    assert proj["disabledMcpjsonServers"] == ["other"]


def test_clear_approval_drops_name_from_both_lists(monkeypatch, tmp_path):
    project = tmp_path / "repo"
    key = project.resolve().as_posix()
    home = _home(
        monkeypatch,
        tmp_path,
        {"projects": {key: {"enabledMcpjsonServers": ["playwright", "keep"]}}},
    )

    m._clear_project_mcp_approval("playwright", project)

    proj = _read(home)["projects"][key]
    assert proj["enabledMcpjsonServers"] == ["keep"]


def test_pending_project_server_enables_activate_local(tmp_path):
    info = {
        "is_plugin": False,
        "scopes": ["project"],
        "pending": True,
        "definitions": {},
    }

    activate_global, activate_local, disable, _ = action_button_states(info, tmp_path)

    assert activate_local is True


def test_connected_project_server_does_not_offer_activate_local(tmp_path):
    info = {
        "is_plugin": False,
        "scopes": ["project"],
        "pending": False,
        "definitions": {},
    }

    _, activate_local, _, _ = action_button_states(info, tmp_path)

    assert activate_local is False


def test_pending_status_cell_is_distinct_from_not_connected():
    info = {
        "is_plugin": False,
        "active": False,
        "pending": True,
        "scopes": ["project"],
        "command_line": "cmd /s /c pnpm dlx x",
    }

    _, status, _, _ = server_row_cells(info)

    assert "pending approval" in status
