# -*- coding: utf-8 -*-
"""HomeScreen README is a pressable link in the banner row, not a bottom button."""

from __future__ import annotations

import pytest
from textual.css.query import NoMatches
from textual.widgets import Static

from cabal.app import CabalApp
from cabal.views.home import HomeScreen
from cabal.views.readme import ReadmeScreen


@pytest.mark.asyncio
async def test_readme_is_a_link_and_button_is_gone():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = HomeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#readme-link", Static) is not None
        with pytest.raises(NoMatches):
            screen.query_one("#btn-readme")


@pytest.mark.asyncio
async def test_readme_action_opens_readme_screen():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = HomeScreen()
        await app.push_screen(screen)
        await pilot.pause()
        screen.action_readme()
        await pilot.pause()

        assert isinstance(app.screen, ReadmeScreen)
