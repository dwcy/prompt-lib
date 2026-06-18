# -*- coding: utf-8 -*-
"""Smoke tests for Codex setup screens."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable

from cabal.app import CabalApp
from cabal.views.codex_conversion import CodexConversionScreen
from cabal.views.codex_local import CodexLocalScreen
from cabal.views.codex_update import CodexUpdateScreen


@pytest.mark.asyncio
async def test_codex_update_screen_mounts():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = CodexUpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#codex-preview", DataTable).row_count > 0


@pytest.mark.asyncio
async def test_codex_local_screen_mounts(tmp_path):
    app = CabalApp()
    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = CodexLocalScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#codex-loc-preview", DataTable).row_count > 0


@pytest.mark.asyncio
async def test_codex_conversion_screen_mounts():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = CodexConversionScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#codex-conv-table", DataTable).row_count > 0
