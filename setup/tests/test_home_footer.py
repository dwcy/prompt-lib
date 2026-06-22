# -*- coding: utf-8 -*-
"""HomeScreen footer trim — removed shortcuts are gone, palette hidden, kept ones work."""

from __future__ import annotations

import pytest
from textual.widgets import Footer

from cabal.app import CabalApp
from cabal.views.home import HomeScreen
from cabal.views.project_gate import ProjectGateScreen


@pytest.fixture(autouse=True)
def _stub_home_background_probes(monkeypatch):
    """Keep HomeScreen smoke tests from starting real host/network probes."""
    from cabal.views import home
    from cabal.widgets import env_panel, update_panel
    from cabal.codex_setup import diff_apply as codex_diff_apply

    monkeypatch.setattr(home, "has_deploy_drift", lambda: False)
    monkeypatch.setattr(codex_diff_apply, "has_codex_deploy_drift", lambda: False)
    monkeypatch.setattr(env_panel.EnvPanel, "on_mount", lambda self: None)
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
