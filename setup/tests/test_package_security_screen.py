# -*- coding: utf-8 -*-
"""Mount-and-render smoke tests for PackageSecurityScreen + the per-fix confirm flow."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Static

from cabal.app import CabalApp
from cabal.package_security import service
from cabal.package_security.models import Finding, ScanOutcome
from cabal.views.package_security import PackageSecurityScreen
from cabal.widgets.fix_confirm_modal import FixConfirmModal

_VULN_FINDING = Finding(
    ecosystem="npm",
    package="lodash",
    kind="vulnerable",
    severity="high",
    current_version="4.17.15",
    target_version="4.17.21",
    fix_command="npm install lodash@4.17.21",
    detail="Prototype Pollution",
)
_NO_FIX_FINDING = Finding(
    ecosystem="dotnet",
    package="Old.Package",
    kind="deprecated",
    severity="info",
    current_version="1.0.0",
    target_version=None,
    fix_command=None,
)


@pytest.fixture(autouse=True)
def _stub_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "load_cached", lambda project: None)
    monkeypatch.setattr(
        service,
        "scan_project",
        lambda project: [ScanOutcome(ecosystem="npm", findings=(_VULN_FINDING,), notices=("heads up",))],
    )
    monkeypatch.setattr(service, "save_cache", lambda project, outcomes: None)


async def _mounted_screen(app, tmp_path):
    app.selected_project = tmp_path
    screen = PackageSecurityScreen()
    await app.push_screen(screen)
    await app.workers.wait_for_complete()
    return screen


@pytest.mark.asyncio
async def test_screen_renders_table_columns_and_scanned_findings(tmp_path):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, tmp_path)
        await pilot.pause()

        table = screen.query_one("#pkgsec-table", DataTable)
        notices = str(screen.query_one("#pkgsec-notices", Static).render())

    assert len(table.columns) == 6
    assert table.row_count == 1
    assert "heads up" in notices


@pytest.mark.asyncio
async def test_fix_action_opens_confirm_modal_with_command_and_versions(tmp_path):
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, tmp_path)
        await pilot.pause()

        screen.action_fix()
        await pilot.pause()

        modal = app.screen
        body = "\n".join(str(w.render()) for w in modal.query(Static))

    assert isinstance(modal, FixConfirmModal)
    assert "npm install lodash@4.17.21" in body
    assert "4.17.15" in body and "4.17.21" in body


@pytest.mark.asyncio
async def test_fix_action_without_fix_command_never_opens_modal(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service,
        "scan_project",
        lambda project: [ScanOutcome(ecosystem="dotnet", findings=(_NO_FIX_FINDING,))],
    )
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, tmp_path)
        await pilot.pause()

        screen.action_fix()
        await pilot.pause()

        assert app.screen is screen


@pytest.mark.asyncio
async def test_confirming_the_modal_applies_the_fix_exactly_once(tmp_path, monkeypatch):
    calls: list[Finding] = []
    monkeypatch.setattr(
        service,
        "apply_fix",
        lambda finding, project: (calls.append(finding) or (True, "done")),
    )
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, tmp_path)
        await pilot.pause()
        screen.action_fix()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, FixConfirmModal)
        modal.on_button_pressed(Button.Pressed(modal.query_one("#fcm-confirm", Button)))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert calls == [_VULN_FINDING]


@pytest.mark.asyncio
async def test_cancelling_the_modal_never_applies_the_fix(tmp_path, monkeypatch):
    calls: list[Finding] = []
    monkeypatch.setattr(service, "apply_fix", lambda finding, project: calls.append(finding))
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, tmp_path)
        await pilot.pause()
        screen.action_fix()
        await pilot.pause()

        modal = app.screen
        modal.on_button_pressed(Button.Pressed(modal.query_one("#fcm-cancel", Button)))
        await pilot.pause()

    assert calls == []
