# -*- coding: utf-8 -*-
"""Mount-and-render smoke test for ClaudeDoctorPanel (Home-screen widget, 016 US3 T018)."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static

from cabal.config_doctor import Finding
from cabal.manifest_doctor import ManifestReport
from cabal.widgets import claude_doctor_panel
from cabal.widgets.claude_doctor_panel import ClaudeDoctorPanel


class _HostScreen(Screen):
    """Minimal host so the widget mounts through a real compose/render pass."""

    def compose(self) -> ComposeResult:
        yield ClaudeDoctorPanel()


def _stub_manifest_report(findings: list[Finding]):
    def _report() -> ManifestReport:
        return ManifestReport(
            present=True, status="complete", tool_version="0.1.0", findings=findings
        )

    return _report


@pytest.mark.asyncio
async def test_panel_renders_findings_and_shows_repair_button_for_repairable_category(
    monkeypatch,
):
    monkeypatch.setattr(
        claude_doctor_panel, "run_doctor_cached", lambda target, project=None: ([], False)
    )
    monkeypatch.setattr(
        claude_doctor_panel,
        "manifest_report",
        _stub_manifest_report(
            [
                Finding(
                    "error",
                    "missing-managed-file",
                    "rules/one.md",
                    "File is recorded in the install manifest but missing from disk.",
                    "Repair from the wizard doctor panel or run `cabal apply --yes`.",
                )
            ]
        ),
    )

    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(_HostScreen())
        await app.workers.wait_for_complete()
        await pilot.pause()

        summary = str(app.screen.query_one("#claude-doctor-summary", Static).render())
        button_display = app.screen.query_one("#claude-doctor-repair", Button).display

    assert "1 error" in summary
    assert button_display is True


@pytest.mark.asyncio
async def test_panel_hides_repair_button_when_only_user_modified_findings(monkeypatch):
    monkeypatch.setattr(
        claude_doctor_panel, "run_doctor_cached", lambda target, project=None: ([], False)
    )
    monkeypatch.setattr(
        claude_doctor_panel,
        "manifest_report",
        _stub_manifest_report(
            [
                Finding(
                    "warning",
                    "user-modified",
                    "CLAUDE.md",
                    "Content matches neither the install manifest nor the bundled source.",
                    "Repair skips this file; review it and resolve by hand.",
                )
            ]
        ),
    )

    app = App()
    async with app.run_test() as pilot:
        await app.push_screen(_HostScreen())
        await app.workers.wait_for_complete()
        await pilot.pause()

        button_display = app.screen.query_one("#claude-doctor-repair", Button).display

    assert button_display is False
