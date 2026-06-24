# -*- coding: utf-8 -*-
"""ToolsScreen enrichment — rows matching a TOOLS entry show a description + Read more."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Static

import cabal.views.tools as tools_view
from cabal.views.tools import ToolsScreen

HEADROOM_REPO = "https://github.com/chopratejas/headroom"


@pytest.mark.asyncio
async def test_headroom_row_shows_description():
    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(ToolsScreen())
        await pilot.pause()

        desc = app.screen.query_one("#tool-desc-headroom", Static)

        assert "Compresses tool outputs" in str(desc.render())


@pytest.mark.asyncio
async def test_headroom_row_has_readmore_button():
    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(ToolsScreen())
        await pilot.pause()

        button = app.screen.query_one("#tool-readmore-headroom", Button)

        assert button is not None


@pytest.mark.asyncio
async def test_readmore_opens_source_link(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(tools_view.webbrowser, "open", lambda url: opened.append(url))

    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(ToolsScreen())
        await pilot.pause()

        app.screen.query_one("#tool-readmore-headroom", Button).press()
        await pilot.pause()

        assert opened == [HEADROOM_REPO]
