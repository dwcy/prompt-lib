# -*- coding: utf-8 -*-
"""HomeScreen and start view keep README out of the old subtitle row."""

from __future__ import annotations

import pytest
from textual.css.query import NoMatches

from cabal.app import CabalApp
from cabal.banner import SUBTITLE_STYLE, SUBTITLE_TEXT
from cabal.views.home import HomeScreen
from cabal.views.readme import ReadmeScreen
from cabal.widgets.logo import CabalLogo, render_cabal_logo


@pytest.fixture(autouse=True)
def _stub_home_background_probes(monkeypatch):
    """Keep HomeScreen smoke tests from starting real host/network probes."""
    from cabal.views import home
    from cabal.widgets import dashboard_panel, okf_panel, update_panel
    from cabal.codex_setup import diff_apply as codex_diff_apply

    monkeypatch.setattr(home, "has_deploy_drift", lambda: False)
    monkeypatch.setattr(codex_diff_apply, "has_codex_deploy_drift", lambda: False)
    monkeypatch.setattr(dashboard_panel.DashboardPanel, "on_mount", lambda self: None)
    monkeypatch.setattr(
        okf_panel.OkfPanel, "on_mount", lambda self: None, raising=False
    )
    monkeypatch.setattr(update_panel.UpdatePanel, "on_mount", lambda self: None)


@pytest.mark.asyncio
async def test_home_logo_owns_subtitle_and_has_no_old_readme_link_or_button():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = HomeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        banner = screen.query_one("#banner", CabalLogo)
        assert banner.show_subtitle is True
        assert SUBTITLE_TEXT in render_cabal_logo(120).plain
        assert SUBTITLE_STYLE == "italic bold #FF55A5"
        assert "Local Agent Control Panel" not in SUBTITLE_TEXT
        with pytest.raises(NoMatches):
            screen.query_one("#subtitle")
        with pytest.raises(NoMatches):
            screen.query_one("#readme-link")
        with pytest.raises(NoMatches):
            screen.query_one("#btn-readme")


@pytest.mark.asyncio
async def test_home_logo_sits_tightly_above_dashboard_panel():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = HomeScreen()
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()

        banner = screen.query_one("#banner", CabalLogo)
        dashboard = screen.query_one("#dashboard")
        banner_region = screen.find_widget(banner).region
        dashboard_region = screen.find_widget(dashboard).region

        assert banner.styles.padding.bottom == 0
        assert dashboard_region.y == banner_region.bottom


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
async def test_start_view_has_no_old_readme_link_but_action_still_opens_readme():
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        gate = app.screen

        banner = gate.query_one("#banner", CabalLogo)
        assert banner.show_subtitle is True
        assert SUBTITLE_TEXT in render_cabal_logo(120).plain
        assert SUBTITLE_STYLE == "italic bold #FF55A5"
        assert "Local Agent Control Panel" not in SUBTITLE_TEXT
        with pytest.raises(NoMatches):
            gate.query_one("#subtitle")
        with pytest.raises(NoMatches):
            gate.query_one("#readme-link")

        gate.action_readme()
        await pilot.pause()

        assert isinstance(app.screen, ReadmeScreen)


@pytest.mark.asyncio
async def test_start_logo_sits_tightly_above_overview_panel():
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        gate = app.screen

        banner = gate.query_one("#banner", CabalLogo)
        overview = gate.query_one("#env-summary")
        banner_region = gate.find_widget(banner).region
        overview_region = gate.find_widget(overview).region

        assert banner.styles.padding.bottom == 0
        assert overview_region.y == banner_region.bottom
