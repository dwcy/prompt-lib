"""Mount test: per-row refresh animates a spinner in the row's Status cell.

Proves the spinner renders in the DataTable Status cell (not a full-table overlay)
by blocking the single-row worker so the spinner state is observable mid-flight.
"""

from __future__ import annotations

import threading

import pytest
from textual.widgets import DataTable

import cabal.views.mcp as mcp_view
from cabal.app import CabalApp
from cabal.views.mcp import McpScreen


def _server(active: bool, scopes: list[str]) -> dict:
    return {
        "is_plugin": False,
        "active": active,
        "pending": False,
        "scopes": scopes,
        "command_line": "pnpm dlx x",
        "env_required": [],
        "definitions": {"template": {}},
        "plugin_id": None,
        "plugin_enabled": None,
        "plugin_scope": None,
    }


@pytest.mark.asyncio
async def test_status_cell_shows_spinner_then_resolves(monkeypatch):
    monkeypatch.setattr(
        mcp_view,
        "enumerate_mcp_servers",
        lambda project_dir=None: {"context7": _server(False, ["template"])},
    )

    release = threading.Event()

    def slow_one(name, project_dir=None):
        release.wait(timeout=5)
        return _server(True, ["user"])

    monkeypatch.setattr(mcp_view, "enumerate_one_server", slow_one)

    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(McpScreen())
        await pilot.pause()

        screen = app.screen
        tbl = screen.query_one("#mcp-table", DataTable)
        status_col = screen._cols[2]

        screen._refresh_row("context7")
        await pilot.pause(0.15)

        mid = str(tbl.get_cell("context7", status_col))
        assert any(frame in mid for frame in McpScreen._SPINNER_FRAMES)
        assert "checking" in mid
        assert tbl.loading is False  # NOT the full-table overlay

        release.set()
        await pilot.pause(0.25)

        resolved = str(tbl.get_cell("context7", status_col))
        assert "connected" in resolved.lower()
