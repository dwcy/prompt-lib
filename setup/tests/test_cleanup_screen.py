# -*- coding: utf-8 -*-
"""Mount-and-render smoke tests for CleanupScreen, CleanupConfirmModal, CleanupRestoreScreen."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, DataTable, OptionList, Static

from cabal.cleanup_service import BackupInfo, CleanupResult, ExtraFile, RestoreResult
from cabal.views.cleanup import CleanupScreen
from cabal.views.cleanup_restore import CleanupRestoreScreen
from cabal.views.update import UpdateScreen
from cabal.widgets.cleanup_confirm_modal import CleanupConfirmModal


def _extras(root: Path) -> list[ExtraFile]:
    return [
        ExtraFile(
            component_key="skills",
            component_label="skills/",
            rel=Path("dead.md"),
            path=root / "skills" / "dead.md",
            classification="stale",
            reason="Flat skills/*.md",
        ),
        ExtraFile(
            component_key="skills",
            component_label="skills/",
            rel=Path("mine/notes.txt"),
            path=root / "skills" / "mine" / "notes.txt",
            classification="unknown",
            reason="Not from this repo",
        ),
    ]


@pytest.fixture
def extras(tmp_path) -> list[ExtraFile]:
    return _extras(tmp_path)


@pytest.fixture
def stub_extras(extras, monkeypatch) -> list[ExtraFile]:
    monkeypatch.setattr("cabal.views.cleanup.collect_extras", lambda: extras)
    return extras


async def _mounted_cleanup_screen(app: App, pilot) -> CleanupScreen:
    screen = CleanupScreen()
    await app.push_screen(screen)
    await pilot.pause()
    return screen


@pytest.mark.asyncio
async def test_cleanup_screen_renders_group_header_and_file_rows(stub_extras):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        table = screen.query_one("#cln-table", DataTable)
        rows = [str(table.get_row_at(i)) for i in range(table.row_count)]

    assert table.row_count == 3
    assert "skills/" in rows[0]
    assert "dead.md" in rows[1]
    assert "mine/notes.txt" in rows[2]


@pytest.mark.asyncio
async def test_cleanup_screen_selects_stale_rows_by_default_only(stub_extras):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        summary = str(screen.query_one("#cln-summary", Static).render())

    assert "Selected: 1" in summary
    assert "stale 1" in summary and "unknown 1" in summary


@pytest.mark.asyncio
async def test_cleanup_screen_enter_toggles_a_row_selection(stub_extras):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        await pilot.press("down", "enter")
        await pilot.pause()
        summary = str(screen.query_one("#cln-summary", Static).render())

    assert "Selected: 0" in summary


@pytest.mark.asyncio
async def test_cleanup_screen_renders_empty_state_when_nothing_to_clean(monkeypatch):
    monkeypatch.setattr("cabal.views.cleanup.collect_extras", lambda: [])
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        table = screen.query_one("#cln-table", DataTable)
        rows = [str(table.get_row_at(i)) for i in range(table.row_count)]

    assert table.row_count == 1
    assert "Nothing to clean up" in rows[0]


@pytest.mark.asyncio
async def test_clean_action_opens_confirm_modal_listing_selected_files(stub_extras):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        screen.action_clean()
        await pilot.pause()
        modal = app.screen
        body = "\n".join(str(w.render()) for w in modal.query(Static))

    assert isinstance(modal, CleanupConfirmModal)
    assert "dead.md" in body
    assert "mine/notes.txt" not in body


@pytest.mark.asyncio
async def test_clean_action_with_no_selection_never_opens_modal(extras, monkeypatch):
    unknown_only = [ex for ex in extras if ex.classification == "unknown"]
    monkeypatch.setattr("cabal.views.cleanup.collect_extras", lambda: unknown_only)
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)

        screen.action_clean()
        await pilot.pause()

        assert app.screen is screen


@pytest.mark.asyncio
async def test_confirming_the_modal_runs_backup_on_selected_paths_only(
    stub_extras, monkeypatch
):
    calls: list[list[Path]] = []
    monkeypatch.setattr(
        "cabal.views.cleanup.backup_and_remove",
        lambda paths: calls.append(list(paths)) or CleanupResult(),
    )
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)
        screen.action_clean()
        await pilot.pause()

        modal = app.screen
        modal.on_button_pressed(Button.Pressed(modal.query_one("#ccm-confirm", Button)))
        await pilot.pause()

    assert calls == [[stub_extras[0].path]]


@pytest.mark.asyncio
async def test_cancelling_the_modal_never_runs_backup(stub_extras, monkeypatch):
    calls: list[list[Path]] = []
    monkeypatch.setattr(
        "cabal.views.cleanup.backup_and_remove",
        lambda paths: calls.append(list(paths)) or CleanupResult(),
    )
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_cleanup_screen(app, pilot)
        screen.action_clean()
        await pilot.pause()

        modal = app.screen
        modal.on_button_pressed(Button.Pressed(modal.query_one("#ccm-cancel", Button)))
        await pilot.pause()

    assert calls == []


@pytest.mark.asyncio
async def test_confirm_modal_dismisses_true_on_confirm(extras):
    results: list[bool | None] = []
    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(CleanupConfirmModal(extras), results.append)
        await pilot.pause()

        modal = app.screen
        modal.on_button_pressed(Button.Pressed(modal.query_one("#ccm-confirm", Button)))
        await pilot.pause()

    assert results == [True]


@pytest.mark.asyncio
async def test_confirm_modal_dismisses_false_on_escape(extras):
    results: list[bool | None] = []
    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(CleanupConfirmModal(extras), results.append)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

    assert results == [False]


@pytest.mark.asyncio
async def test_confirm_modal_lists_every_file_with_its_classification(extras):
    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(CleanupConfirmModal(extras))
        await pilot.pause()

        body = "\n".join(str(w.render()) for w in app.screen.query(Static))

    assert "dead.md" in body
    assert "mine/notes.txt" in body
    assert "2" in body


@pytest.mark.asyncio
async def test_restore_screen_renders_empty_state_without_backups(monkeypatch):
    monkeypatch.setattr("cabal.views.cleanup_restore.list_cleanup_backups", lambda: [])
    app = App()
    async with app.run_test() as pilot:
        screen = CleanupRestoreScreen()
        await app.push_screen(screen)
        await pilot.pause()

        body = "\n".join(str(w.render()) for w in screen.query(Static))

    assert "No cleanup backups found" in body


@pytest.mark.asyncio
async def test_restore_screen_lists_backups_and_restores_the_highlighted_one(
    tmp_path, monkeypatch
):
    backup = BackupInfo(
        path=tmp_path / "20260101-101010",
        timestamp="20260101-101010",
        entry_count=2,
        total_bytes=64,
    )
    monkeypatch.setattr(
        "cabal.views.cleanup_restore.list_cleanup_backups", lambda: [backup]
    )
    calls: list[Path] = []
    monkeypatch.setattr(
        "cabal.views.cleanup_restore.restore_cleanup",
        lambda path: (
            calls.append(path)
            or RestoreResult(backup_dir=path, restored=[tmp_path / "a.md"])
        ),
    )
    app = App()
    async with app.run_test() as pilot:
        screen = CleanupRestoreScreen()
        await app.push_screen(screen)
        await pilot.pause()

        lst = screen.query_one("#clnr-list", OptionList)
        lst.highlighted = 0
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#clnr-apply", Button))
        )
        await pilot.pause()
        status = str(screen.query_one("#clnr-status", Static).render())

    assert calls == [backup.path]
    assert "Restored 1" in status


@pytest.mark.asyncio
async def test_restore_screen_requires_a_highlighted_backup(tmp_path, monkeypatch):
    backup = BackupInfo(
        path=tmp_path / "20260101-101010",
        timestamp="20260101-101010",
        entry_count=1,
        total_bytes=8,
    )
    monkeypatch.setattr(
        "cabal.views.cleanup_restore.list_cleanup_backups", lambda: [backup]
    )
    calls: list[Path] = []
    monkeypatch.setattr(
        "cabal.views.cleanup_restore.restore_cleanup",
        lambda path: calls.append(path) or RestoreResult(backup_dir=path),
    )
    app = App()
    async with app.run_test() as pilot:
        screen = CleanupRestoreScreen()
        await app.push_screen(screen)
        await pilot.pause()

        screen.query_one("#clnr-list", OptionList).highlighted = None
        screen.on_button_pressed(
            Button.Pressed(screen.query_one("#clnr-apply", Button))
        )
        await pilot.pause()
        status = str(screen.query_one("#clnr-status", Static).render())

    assert calls == []
    assert "Pick a backup first" in status


@pytest.mark.asyncio
async def test_update_screen_cleanup_button_pushes_cleanup_screen(monkeypatch):
    monkeypatch.setattr("cabal.views.cleanup.collect_extras", lambda: [])
    app = App()
    async with app.run_test() as pilot:
        screen = UpdateScreen()
        await app.push_screen(screen)
        await pilot.pause()

        button = screen.query_one("#upd-cleanup", Button)
        screen.on_button_pressed(Button.Pressed(button))
        await pilot.pause()

        assert isinstance(app.screen, CleanupScreen)
