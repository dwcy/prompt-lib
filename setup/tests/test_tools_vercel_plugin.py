# -*- coding: utf-8 -*-
"""Smoke test — Vercel Plugin row renders in the ToolsScreen AI CLIs group."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Static

from cabal.tools import ENV_INSTALLERS, ENV_TOOL_GROUPS, _installer_for
from cabal.views.tools import ToolsScreen


def test_vercel_plugin_registered():
    assert _installer_for("vercel-plugin") is not None
    ai_clis = dict(ENV_TOOL_GROUPS)["AI CLIs"]
    assert "vercel-plugin" in ai_clis
    assert "skills" in ai_clis  # stays alongside the Vercel Skills CLI


@pytest.mark.asyncio
async def test_tools_screen_renders_vercel_plugin_row():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()
        assert screen.query_one("#tool-install-vercel-plugin", Button) is not None


@pytest.mark.asyncio
async def test_tools_screen_renders_uv_recommended_badge():
    app = App()
    async with app.run_test() as pilot:
        screen = ToolsScreen()
        await app.push_screen(screen)
        await pilot.pause()
        label = screen.query_one("#tool-name-uv", Static)
        assert "[recommended]" in str(label.render())
