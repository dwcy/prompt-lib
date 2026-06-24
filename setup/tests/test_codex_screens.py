# -*- coding: utf-8 -*-
"""Smoke tests for Codex setup screens."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.widgets import Checkbox, DataTable

from cabal.app import CabalApp
from cabal.codex_setup import conversion
from cabal.views.codex_conversion import CodexConversionScreen
from cabal.views.codex_local import CodexLocalScreen
from cabal.views.codex_update import CodexUpdateScreen
from cabal.widgets.file_viewer import FileViewerModal


def _row_key(value: str):
    return SimpleNamespace(row_key=SimpleNamespace(value=value))


def _selected_event(value: str, row: int = 0):
    return SimpleNamespace(row_key=SimpleNamespace(value=value), cursor_row=row)


@pytest.mark.asyncio
async def test_codex_update_screen_mounts():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = CodexUpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#codex-preview", DataTable).row_count > 0


@pytest.mark.asyncio
async def test_codex_update_screen_toggles_and_views_file(monkeypatch):
    app = CabalApp()
    pushed: list[object] = []

    async with app.run_test() as pilot:
        screen = CodexUpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()

        child_key = screen._child_keys["skills"][0]
        assert screen._use[child_key] is True

        screen.on_data_table_row_selected(_selected_event("skills"))
        assert all(not screen._use[key] for key in screen._child_keys["skills"])

        table = screen.query_one("#codex-preview", DataTable)
        monkeypatch.setattr(
            table,
            "coordinate_to_cell_key",
            lambda _coord: _row_key(child_key),
        )
        monkeypatch.setattr(
            app,
            "push_screen",
            lambda modal, *_, **__: pushed.append(modal),
        )

        screen.action_view_file()

    assert isinstance(pushed[0], FileViewerModal)


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
async def test_codex_local_screen_toggles_and_views_skill(tmp_path, monkeypatch):
    app = CabalApp()
    pushed: list[object] = []

    async with app.run_test() as pilot:
        app.selected_project = tmp_path
        screen = CodexLocalScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#codex-loc-skills", Checkbox).value = True
        screen._refresh()
        child_key = screen._child_keys["skills"][0]
        assert screen._use[child_key] is True

        screen.on_data_table_row_selected(_selected_event("action::skills"))
        assert all(not screen._use[key] for key in screen._child_keys["skills"])

        table = screen.query_one("#codex-loc-preview", DataTable)
        monkeypatch.setattr(
            table,
            "coordinate_to_cell_key",
            lambda _coord: _row_key(child_key),
        )
        monkeypatch.setattr(
            app,
            "push_screen",
            lambda modal, *_, **__: pushed.append(modal),
        )

        screen.action_view_file()

    assert isinstance(pushed[0], FileViewerModal)


@pytest.mark.asyncio
async def test_codex_conversion_screen_mounts():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = CodexConversionScreen()
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#codex-conv-table", DataTable).row_count > 0


@pytest.mark.asyncio
async def test_codex_conversion_view_skipped_file_includes_reason(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    codex = root / "global" / "codex"
    source = root / "global" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}", encoding="utf-8")
    codex.mkdir(parents=True)
    (codex / "conversion-manifest.json").write_text(
        """
{
  "version": 1,
  "entries": [
    {
      "source": "global/settings.json",
      "output": null,
      "kind": "unsupported",
      "status": "unsupported",
      "reason": "Claude settings are not Codex config."
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(conversion, "RESOURCE_ROOT", root)
    monkeypatch.setattr(conversion, "CODEX_SOURCE_DIR", codex)

    app = CabalApp()
    pushed: list[object] = []

    async with app.run_test() as pilot:
        screen = CodexConversionScreen()
        await app.push_screen(screen)
        await pilot.pause()

        table = screen.query_one("#codex-conv-table", DataTable)
        monkeypatch.setattr(
            table,
            "coordinate_to_cell_key",
            lambda _coord: _row_key("0"),
        )
        monkeypatch.setattr(
            app,
            "push_screen",
            lambda modal, *_, **__: pushed.append(modal),
        )

        screen.action_view_file()

    assert isinstance(pushed[0], FileViewerModal)
    assert "Claude settings are not Codex config." in pushed[0]._new_text
