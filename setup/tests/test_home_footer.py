# -*- coding: utf-8 -*-
"""HomeScreen footer trim — removed shortcuts are gone, palette hidden, kept ones work."""

from __future__ import annotations

import pytest
from textual.containers import Vertical
from textual.widgets import Footer, Static

from cabal.app import CabalApp
from cabal.views.home import HomeScreen
from cabal.views.project_gate import ProjectGateScreen


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
async def test_readme_is_link_only_no_shortcut():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = await _home(app)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()

        assert app.screen is screen


@pytest.mark.asyncio
async def test_command_palette_hidden_from_footer():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = await _home(app)
        await pilot.pause()

        assert screen.query_one(Footer).show_command_palette is False


@pytest.mark.asyncio
async def test_escape_returns_to_start_view():
    app = CabalApp()

    async with app.run_test() as pilot:
        await _home(app)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ProjectGateScreen)


def test_home_bindings_are_escape_and_refresh_only():
    keys = {b.key for b in HomeScreen.BINDINGS}

    assert keys == {"escape", "ctrl+s", "ctrl+d"}


@pytest.mark.asyncio
async def test_codex_settings_are_in_their_own_panel():
    app = CabalApp()

    async with app.run_test() as pilot:
        screen = await _home(app)
        await pilot.pause()

        codex_panel = screen.query_one("#codex-settings-panel", Vertical)
        claude_panel = screen.query_one("#claude-settings-panel", Vertical)
        okf_panel = screen.query_one("#okf-analytics-panel", Vertical)

        assert screen.query_one("#btn-op-codex-update").parent.parent is codex_panel
        assert screen.query_one("#btn-op-codex-local").parent.parent is codex_panel
        assert screen.query_one("#btn-op-codex-conversion").parent.parent is codex_panel
        assert screen.query_one("#btn-op-update").parent.parent is claude_panel
        assert screen.query_one("#btn-op-knowledge").parent.parent is okf_panel
        assert screen.query_one("#okf-summary").parent is okf_panel

        assert "~/.claude" in str(
            screen.query_one("#claude-settings-title", Static).render()
        )
        assert "~/.codex" in str(
            screen.query_one("#codex-settings-title", Static).render()
        )
        assert "OKF Analytics" in str(
            screen.query_one("#okf-analytics-title", Static).render()
        )
        assert "Open Knowledge Format" in str(
            screen.query_one("#okf-analytics-desc", Static).render()
        )
