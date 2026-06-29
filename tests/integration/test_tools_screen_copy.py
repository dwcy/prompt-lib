"""Tools screen selected-text copy tests."""

from __future__ import annotations

import pytest
from textual.widgets import Static

import cabal.app as app_module
from cabal.app import CabalApp
from cabal.views import project_gate
from cabal.views.tools import ToolsScreen


@pytest.fixture(autouse=True)
def _disable_tools_workers(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "on_mount", lambda self: None)


@pytest.mark.asyncio
async def test_tool_name_carries_description_tooltip(monkeypatch):
    monkeypatch.setattr(project_gate, "load_recents", lambda: [])
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await app.push_screen(ToolsScreen())
        await pilot.pause()
        name = app.screen.query_one("#tool-name-git", Static)

        assert name.tooltip is not None
        assert "version control" in name.tooltip.lower()


@pytest.mark.asyncio
async def test_read_more_button_comes_after_install(monkeypatch):
    monkeypatch.setattr(project_gate, "load_recents", lambda: [])
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await app.push_screen(ToolsScreen())
        await pilot.pause()
        row = app.screen.query_one("#tool-row-git")
        ids = [child.id for child in row.children]

        assert ids.index("tool-install-git") < ids.index("tool-source-git")


@pytest.mark.asyncio
async def test_tools_screen_copies_install_error_text(monkeypatch):
    monkeypatch.setattr(project_gate, "load_recents", lambda: [])
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    copied: list[str] = []
    monkeypatch.setattr(app_module, "write_clipboard", lambda text: copied.append(text))
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await app.push_screen(ToolsScreen())
        await pilot.pause()
        status = app.screen.query_one("#tools-status", Static)
        status.update("Install failed: port 6379 is already in use")
        status.text_select_all()
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert "port 6379" in app._clipboard
        assert "Install failed" in copied[0]
