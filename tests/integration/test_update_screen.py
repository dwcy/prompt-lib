"""Smoke tests for UpdateScreen — parent/child selectable component tree.

Mount through Textual's compose() pipeline so framework-shadow bugs surface, and
exercise the row-selection toggles (per-file children + bulk parent toggle) that
replaced the per-component checkboxes.
"""

from __future__ import annotations

import pytest

from cabal.app import CabalApp
from cabal.components import COMPONENTS
from cabal.views.update import UpdateScreen


def _first_dir_component():
    return next(
        (
            c
            for c in COMPONENTS
            if c.type == "dir" and c.src_path.exists() and c.list_files()
        ),
        None,
    )


@pytest.mark.asyncio
async def test_dir_components_expand_into_child_rows():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = UpdateScreen()
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets import DataTable

        table = screen.query_one("#preview", DataTable)

        assert table.row_count > len(COMPONENTS)


@pytest.mark.asyncio
async def test_child_row_toggles_single_file():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = UpdateScreen()
        app.push_screen(screen)
        await pilot.pause()

        c = _first_dir_component()
        assert c is not None
        child_key = screen._child_keys[c.key][0]
        before = screen._use[child_key]
        screen.on_data_table_row_selected(_FakeRowSelected(child_key, 1))
        await pilot.pause()

        assert screen._use[child_key] is (not before)


@pytest.mark.asyncio
async def test_parent_row_bulk_toggles_all_children():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = UpdateScreen()
        app.push_screen(screen)
        await pilot.pause()

        c = _first_dir_component()
        assert c is not None
        screen.on_data_table_row_selected(_FakeRowSelected(c.key, 0))
        await pilot.pause()

        assert all(screen._use[k] is False for k in screen._child_keys[c.key])


@pytest.mark.asyncio
async def test_file_component_toggles_directly():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = UpdateScreen()
        app.push_screen(screen)
        await pilot.pause()

        f = next(c for c in COMPONENTS if c.type == "file" and c.src_path.exists())
        before = screen._use[f.key]
        screen.on_data_table_row_selected(_FakeRowSelected(f.key, 0))
        await pilot.pause()

        assert screen._use[f.key] is (not before)


class _FakeRowSelected:
    """Minimal stand-in for DataTable.RowSelected (row_key.value + cursor_row)."""

    def __init__(self, key: str, cursor_row: int) -> None:
        self.row_key = type("RowKey", (), {"value": key})()
        self.cursor_row = cursor_row
