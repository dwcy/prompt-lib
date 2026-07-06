# -*- coding: utf-8 -*-
"""Pilot integration tests for ClaudeDoctorPanel — mounts through run_test() so
framework-shadow bugs surface, against tmp ~/.claude trees (healthy and broken)."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cabal import widget_cache
from cabal.widgets.claude_doctor_panel import ClaudeDoctorPanel


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the shared widget cache into tmp_path so tests never touch ~/.cabal."""
    cache_dir = tmp_path / "cabal-cache"
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", cache_dir / "cache.json")


class _PanelHost(App):
    """Minimal host App whose only child is the ClaudeDoctorPanel under test."""

    def __init__(self, target: Path) -> None:
        super().__init__()
        self._target = target

    def compose(self) -> ComposeResult:
        yield ClaudeDoctorPanel(id="claude-doctor", target=self._target)


def _summary_text(app: App) -> str:
    return str(app.query_one("#claude-doctor-summary", Static).render())


async def _settled(app: App, pilot) -> None:
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_healthy_target_renders_the_happy_line(tmp_path: Path):
    skill = tmp_path / "skills" / "fine"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: fine\ndescription: Fine. Use whenever.\n---\n", encoding="utf-8"
    )
    app = _PanelHost(tmp_path)

    async with app.run_test() as pilot:
        await _settled(app, pilot)

        assert "Claude is healthy :D" in _summary_text(app)


@pytest.mark.asyncio
async def test_broken_target_lists_the_unhealthy_file_with_reason_and_hint(tmp_path: Path):
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "orphan.md").write_text("dead\n", encoding="utf-8")
    app = _PanelHost(tmp_path)

    async with app.run_test() as pilot:
        await _settled(app, pilot)
        text = _summary_text(app)

        assert "orphan.md" in text and "never loaded" in text and "SKILL.md" in text
