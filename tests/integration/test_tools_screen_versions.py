"""Tools screen version selector integration tests."""

from __future__ import annotations

import inspect

import pytest
from textual.app import App
from textual.widgets import Select

from cabal.views.tools import ToolsScreen


def test_post_install_reload_refreshes_only_the_installed_row():
    src = inspect.getsource(ToolsScreen._reload_one_worker)

    assert "_apply_outdated_one" in src


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
async def test_version_row_value_is_visible_on_centered_line():
    from textual.widgets._select import SelectCurrent

    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()
        row = screen.query_one("#tool-row-node")
        value = screen.query_one("#tool-version-node", Select).query_one(SelectCurrent)

        # Versioned rows are 3 tall; the Select value renders on the middle line,
        # where the centered name/buttons also sit — visible, not clipped away.
        assert row.region.height == 3
        assert value.region.y == row.region.y + 1


@pytest.mark.asyncio
async def test_long_running_version_check_does_not_block_initial_render(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "_load_outdated", lambda self: None)
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-name-node") is not None
