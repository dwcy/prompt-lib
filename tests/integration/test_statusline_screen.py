"""Smoke tests for StatuslineScreen — segment reorder / toggle / row + save.

Mounts through Textual's compose() pipeline (catches framework-shadow bugs) and
isolates the user config file so the real ~/.claude is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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

        from textual.widgets import DataTable

        table = screen.query_one("#sl-table", DataTable)

        assert table.row_count == len(screen._layout)


@pytest.mark.asyncio
async def test_row_selection_toggles_enabled(tmp_user_config):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        key = screen._layout[0]["key"]
        before = screen._layout[0]["enabled"]
        screen.on_data_table_row_selected(_FakeRowSelected(key, 0))
        await pilot.pause()

        assert screen._layout[0]["enabled"] is (not before)


@pytest.mark.asyncio
async def test_move_down_reorders(tmp_user_config):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        first, second = screen._layout[0]["key"], screen._layout[1]["key"]
        screen.query_one("#sl-table").move_cursor(row=0)
        screen.action_move_down()
        await pilot.pause()

        assert (screen._layout[0]["key"], screen._layout[1]["key"]) == (second, first)


@pytest.mark.asyncio
async def test_save_writes_user_config(tmp_user_config: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = StatuslineScreen()
        app.push_screen(screen)
        await pilot.pause()

        screen._layout[0]["enabled"] = False
        screen.action_save()
        await pilot.pause()

        written = json.loads(tmp_user_config.read_text(encoding="utf-8"))

    assert written["segments"][0]["enabled"] is False


class _FakeRowSelected:
    def __init__(self, key: str, cursor_row: int) -> None:
        self.row_key = type("RowKey", (), {"value": key})()
        self.cursor_row = cursor_row
