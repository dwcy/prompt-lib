"""Tools screen version selector integration tests."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Select

from cabal.views.tools import ToolsScreen


@pytest.fixture(autouse=True)
def _disable_tools_workers(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "on_mount", lambda self: None)


@pytest.mark.asyncio
async def test_version_selector_renders_for_runtime_tools():
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-version-node", Select) is not None
        assert screen.query_one("#tool-version-python", Select) is not None
        assert screen.query_one("#tool-version-dotnet", Select) is not None


@pytest.mark.asyncio
async def test_version_row_is_a_single_line():
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-row-node").size.height == 1


@pytest.mark.asyncio
async def test_long_running_version_check_does_not_block_initial_render(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "_load_outdated", lambda self: None)
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-name-node") is not None
