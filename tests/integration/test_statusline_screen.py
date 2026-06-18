"""Smoke tests for StatuslineScreen — segment reorder / toggle / row + save.

Mounts through Textual's compose() pipeline (catches framework-shadow bugs) and
isolates the user config file so the real ~/.claude is never touched. Segments
live in two grouped tables (#sl-table-1 / #sl-table-2) backed by screen._rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import DataTable

from cabal import statusline_config
from cabal.app import CabalApp
from cabal.views.statusline import StatuslineScreen


@pytest.fixture
def tmp_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / ".claude" / "statusline-config.json"
    monkeypatch.setattr(statusline_config, "USER_CONFIG_PATH", cfg)
    return cfg


def test_load_layout_has_metadata():
    layout = statusline_config.load_layout()

    assert all("label" in s and "description" in s and "row" in s for s in layout)


@pytest.mark.asyncio
async def test_screen_mounts_and_builds_rows(tmp_user_config):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        total = sum(
            screen.query_one(f"#sl-table-{r}", DataTable).row_count for r in (1, 2)
        )

        assert total == len(statusline_config.load_layout())


@pytest.mark.asyncio
async def test_row_selection_toggles_enabled(tmp_user_config):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        table = screen.query_one("#sl-table-1", DataTable)
        seg = screen._rows[1][0]
        before = seg["enabled"]
        screen.on_data_table_row_selected(_FakeRowSelected(table, seg["key"], 0))
        await pilot.pause()

        assert screen._rows[1][0]["enabled"] is (not before)


@pytest.mark.asyncio
async def test_move_down_reorders(tmp_user_config):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        first, second = screen._rows[1][0]["key"], screen._rows[1][1]["key"]
        # Filling table 2 on mount leaves its RowHighlighted as the last event,
        # so _active_row ends at 2 — pin it back as a user highlighting table 1 would.
        screen._active_row = 1
        screen.query_one("#sl-table-1", DataTable).move_cursor(row=0)
        screen.action_move_down()
        await pilot.pause()

        assert (screen._rows[1][0]["key"], screen._rows[1][1]["key"]) == (
            second,
            first,
        )


@pytest.mark.asyncio
async def test_save_writes_user_config(tmp_user_config: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        screen._rows[1][0]["enabled"] = False
        screen.action_save()
        await pilot.pause()

        written = json.loads(tmp_user_config.read_text(encoding="utf-8"))

    assert written["segments"][0]["enabled"] is False


class _FakeRowSelected:
    """Minimal stand-in for DataTable.RowSelected (data_table + row_key.value + cursor_row)."""

    def __init__(self, data_table: DataTable, key: str, cursor_row: int) -> None:
        self.data_table = data_table
        self.row_key = type("RowKey", (), {"value": key})()
        self.cursor_row = cursor_row
