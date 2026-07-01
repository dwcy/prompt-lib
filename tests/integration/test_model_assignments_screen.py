"""Mount-and-render smoke tests for ModelAssignmentsScreen (shadow-bug guard)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal.app import CabalApp
from cabal.views.model_assignments import ModelAssignmentsScreen, ModelPickerScreen
from textual.widgets import DataTable


def _fixture_global(tmp_path: Path) -> Path:
    root = tmp_path / "global"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "sample.md").write_text(
        "---\nname: sample\nmodel: opus\n---\n\nBody.\n", encoding="utf-8"
    )
    return root


@pytest.mark.asyncio
async def test_model_assignments_screen_mounts_and_lists_rows(tmp_path: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(
            ModelAssignmentsScreen(_fixture_global(tmp_path), tmp_path / "empty")
        )
        await pilot.pause()

        assert isinstance(app.screen, ModelAssignmentsScreen)
        table = app.screen.query_one("#ma-table", DataTable)
        assert table.row_count == 1
        assert [str(c) for c in table.get_row_at(0)][:3] == [
            "agent",
            "sample",
            "opus → Opus 4.8",
        ]


@pytest.mark.asyncio
async def test_enter_opens_the_model_picker(tmp_path: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(
            ModelAssignmentsScreen(_fixture_global(tmp_path), tmp_path / "empty")
        )
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ModelPickerScreen)
