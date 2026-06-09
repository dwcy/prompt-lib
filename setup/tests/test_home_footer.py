# -*- coding: utf-8 -*-
"""HomeScreen footer trim — removed shortcuts are gone, palette hidden, kept ones work."""

from __future__ import annotations

import pytest
from textual.widgets import Footer

from cabal.app import CabalApp
from cabal.views.home import HomeScreen
from cabal.views.readme import ReadmeScreen


async def _home(app):
    screen = HomeScreen()
    await app.push_screen(screen)
    return screen


@pytest.mark.asyncio
async def test_removed_shortcut_does_not_navigate():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = await _home(app)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        assert app.screen is screen


@pytest.mark.asyncio
async def test_kept_readme_shortcut_still_opens_readme():
    app = CabalApp()

    async with app.run_test() as pilot:
        await _home(app)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()

        assert isinstance(app.screen, ReadmeScreen)


@pytest.mark.asyncio
async def test_command_palette_hidden_from_footer():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = await _home(app)
        await pilot.pause()

        assert screen.query_one(Footer).show_command_palette is False


@pytest.mark.asyncio
async def test_removed_binding_keys_are_absent():
    keys = {b.key for b in HomeScreen.BINDINGS}

    assert keys == {"r", "g", "i", "ctrl+s"}
