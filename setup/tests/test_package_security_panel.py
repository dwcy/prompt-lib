# -*- coding: utf-8 -*-
"""Mount-and-render smoke test for PackageSecurityPanel (Home-screen summary widget)."""

from __future__ import annotations

import pytest
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from cabal.app import CabalApp
from cabal.package_security import service
from cabal.package_security.models import Finding, ScanOutcome
from cabal.widgets.package_security_panel import PackageSecurityPanel, summarize


class _HostScreen(Screen):
    """Minimal host so the widget mounts through a real compose/render pass."""

    def compose(self) -> ComposeResult:
        yield PackageSecurityPanel()


@pytest.mark.asyncio
async def test_panel_renders_scan_summary_after_mount(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "load_cached", lambda project: None)
    monkeypatch.setattr(
        service,
        "scan_project",
        lambda project: [
            ScanOutcome(
                ecosystem="npm",
                findings=(
                    Finding("npm", "lodash", "vulnerable", "high", "4.17.15", "4.17.21", "npm install lodash@4.17.21"),
                ),
            )
        ],
    )
    monkeypatch.setattr(service, "save_cache", lambda project, outcomes: None)

    app = CabalApp()
    app.selected_project = tmp_path
    async with app.run_test() as pilot:
        await app.push_screen(_HostScreen())
        await app.workers.wait_for_complete()
        await pilot.pause()

        summary = str(app.screen.query_one("#pkgsec-summary", Static).render())

    assert "1 vulnerable" in summary


def test_summarize_reports_clean_when_no_findings_or_notices():
    outcomes = [ScanOutcome(ecosystem="python", findings=())]

    text = summarize(outcomes)

    assert "No package security findings" in text


def test_summarize_reports_no_ecosystems_detected_for_empty_outcomes():
    assert "No .NET, npm, or Python" in summarize([])
