# -*- coding: utf-8 -*-
"""HomeScreen README is a pressable link in the banner row, not a bottom button."""

from __future__ import annotations

import pytest
from textual.css.query import NoMatches
from textual.widgets import Static

from cabal.app import CabalApp
from cabal.views.home import HomeScreen
from cabal.views.readme import ReadmeScreen


@pytest.fixture(autouse=True)
def _stub_home_background_probes(monkeypatch):
    """Keep HomeScreen smoke tests from starting real host/network probes."""
    from cabal.views import home
    from cabal.widgets import dashboard_panel, okf_panel, update_panel
    from cabal.codex_setup import diff_apply as codex_diff_apply

    monkeypatch.setattr(home, "has_deploy_drift", lambda: False)
    monkeypatch.setattr(codex_diff_apply, "has_codex_deploy_drift", lambda: False)
    monkeypatch.setattr(dashboard_panel.DashboardPanel, "on_mount", lambda self: None)
    monkeypatch.setattr(okf_panel.OkfPanel, "on_mount", lambda self: None)
    monkeypatch.setattr(update_panel.UpdatePanel, "on_mount", lambda self: None)


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


@pytest.mark.asyncio
async def test_start_view_has_readme_link_that_opens_readme():
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        gate = app.screen

        assert gate.query_one("#readme-link", Static) is not None

        gate.action_readme()
        await pilot.pause()

        assert isinstance(app.screen, ReadmeScreen)
