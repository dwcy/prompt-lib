"""Smoke tests for LocalScreen (regression guard for the GITIGNORE_BY_TEMPLATE NameError).

LocalScreen._refresh() is triggered by checkbox changes; the previous bug only
surfaced when a user toggled the gitignore checkbox. The mount-and-refresh
smoke catches the import-shadow gap without depending on the user's actions.
"""

from __future__ import annotations

import pytest

from cabal.app import CabalApp
from cabal.views.local import LocalScreen


@pytest.mark.asyncio
async def test_local_screen_mounts_and_refresh_does_not_nameerror(tmp_project_dir):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = LocalScreen()
        app.push_screen(screen)
        await pilot.pause()

        screen._refresh()
        await pilot.pause()

        assert isinstance(app.screen, LocalScreen)


def test_gitignore_by_template_is_importable_in_local_module():
    from cabal.views import local as local_module

    assert isinstance(local_module.GITIGNORE_BY_TEMPLATE, dict)
    assert "python" in local_module.GITIGNORE_BY_TEMPLATE


@pytest.mark.asyncio
async def test_scaffold_children_are_selectable(tmp_project_dir):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = LocalScreen()
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets import Input

        screen.query_one("#loc-path", Input).value = str(tmp_project_dir)
        screen._refresh()
        await pilot.pause()

        scaffold_keys = screen._child_keys["scaffold"]
        first = scaffold_keys[0]
        screen.on_data_table_row_selected(_FakeRowSelected(first, 1))
        await pilot.pause()

        assert screen._use[first] is False


@pytest.mark.asyncio
async def test_parent_row_bulk_toggles_scaffold(tmp_project_dir):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = LocalScreen()
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets import Input

        screen.query_one("#loc-path", Input).value = str(tmp_project_dir)
        screen._refresh()
        await pilot.pause()

        screen.on_data_table_row_selected(_FakeRowSelected("action::scaffold", 0))
        await pilot.pause()

        assert all(screen._use[k] is False for k in screen._child_keys["scaffold"])


class _FakeRowSelected:
    """Minimal stand-in for DataTable.RowSelected (row_key.value + cursor_row)."""

    def __init__(self, key: str, cursor_row: int) -> None:
        self.row_key = type("RowKey", (), {"value": key})()
        self.cursor_row = cursor_row
