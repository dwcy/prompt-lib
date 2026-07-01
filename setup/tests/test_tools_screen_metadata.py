# -*- coding: utf-8 -*-
"""Tools screen metadata rendering tests."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Select, Static

import cabal.views.tools as tools_view
from cabal.views.tools import ToolsScreen


@pytest.fixture(autouse=True)
def _disable_tools_workers(monkeypatch):
    monkeypatch.setattr(ToolsScreen, "on_mount", lambda self: None)


@pytest.mark.asyncio
async def test_tools_screen_renders_descriptions():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        name = screen.query_one("#tool-name-git", Static)
        assert "version control" in str(name.tooltip).lower()


@pytest.mark.asyncio
async def test_tools_screen_renders_read_more_actions():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        source = screen.query_one("#tool-source-zed", Button)
        assert str(source.label) == "Read more"
        assert source.disabled is False


@pytest.mark.asyncio
async def test_read_more_uses_source_url(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(tools_view.webbrowser, "open", lambda url: opened.append(url))
    app = App()

    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()
        button = screen.query_one("#tool-source-zed", Button)
        screen.on_button_pressed(type("Pressed", (), {"button": button})())
        await pilot.pause()

        assert opened == ["https://zed.dev/"]
        assert "https://zed.dev/" in str(
            screen.query_one("#tools-status", Static).content
        )


@pytest.mark.asyncio
async def test_source_required_row_disables_install_button():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        install = screen.query_one("#tool-install-hermes-agent", Button)
        source = screen.query_one("#tool-source-hermes-agent", Button)
        assert install.disabled is True
        assert source.disabled is True
        assert str(source.label) == "Source req"


@pytest.mark.asyncio
async def test_version_selector_renders_for_runtime_tools():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#tool-version-node", Select) is not None
