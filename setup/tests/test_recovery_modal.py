# -*- coding: utf-8 -*-
"""Smoke tests for RecoveryModal — render and Escape-to-review dismissal."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Static

from cabal.install_manifest import InstallManifest
from cabal.views.recovery_modal import RecoveryModal


def _sample_manifest() -> InstallManifest:
    return InstallManifest(
        tool_version="1.2.3",
        source_mode="source",
        applied_at="2026-01-01T00:00:00+00:00",
        status="in_progress",
        components=["agents", "hooks"],
        backup_dir=None,
        files=[],
    )


@pytest.mark.asyncio
async def test_renders_interrupted_apply_detail():
    app = App()
    async with app.run_test() as pilot:
        modal = RecoveryModal(_sample_manifest())
        await app.push_screen(modal)
        await pilot.pause()

        detail = str(modal.query_one("#rcv-detail", Static).render())
        assert "1.2.3" in detail
        assert "agents" in detail and "hooks" in detail


@pytest.mark.asyncio
async def test_escape_dismisses_with_review_none():
    app = App()
    results: list[str | None] = []
    async with app.run_test() as pilot:
        await app.push_screen(RecoveryModal(_sample_manifest()), results.append)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

    assert results == [None]
