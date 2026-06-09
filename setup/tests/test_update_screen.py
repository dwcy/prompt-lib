# -*- coding: utf-8 -*-
"""Smoke tests for UpdateScreen — 3-column layout (no numeric count columns)."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import DataTable

from cabal.views.update import UpdateScreen


@pytest.mark.asyncio
async def test_preview_table_has_three_columns():
    app = App()

    async with app.run_test() as pilot:
        screen = UpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()
        table = screen.query_one("#preview", DataTable)

        assert len(table.columns) == 3


@pytest.mark.asyncio
async def test_preview_table_renders_rows():
    app = App()

    async with app.run_test() as pilot:
        screen = UpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()
        table = screen.query_one("#preview", DataTable)

        assert table.row_count > 0
