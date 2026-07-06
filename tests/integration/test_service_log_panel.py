# -*- coding: utf-8 -*-
"""Pilot integration tests for ServiceLogPanel — the inline live-tail pane for one service.

Mounts the widget through Textual's run_test() pipeline (so framework-shadow bugs surface)
inside a minimal host App, against a tmp_path capture-log dir, and asserts the empty hint,
show() seeding of existing content, retarget-clears-stale-lines, and live append behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import RichLog

from cabal import service_supervisor
from cabal.widgets.service_log_panel import _EMPTY_HINT, ServiceLogPanel


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the supervisor's capture-log dir into tmp_path so nothing touches ~/.cabal."""
    target = tmp_path / "logs"
    monkeypatch.setattr(service_supervisor, "_LOG_DIR", target)
    return target


class _PanelHost(App):
    """Minimal host App whose only child is the ServiceLogPanel under test."""

    def compose(self) -> ComposeResult:
        yield ServiceLogPanel(id="svc-log-panel")


def _rendered_lines(view: RichLog) -> list[str]:
    return [strip.text for strip in view.lines]


@pytest.mark.asyncio
async def test_empty_panel_shows_the_empty_hint(log_dir: Path):
    app = _PanelHost()

    async with app.run_test() as pilot:
        await pilot.pause()

        view = app.query_one("#svc-log-view", RichLog)

        assert any(_EMPTY_HINT in line for line in _rendered_lines(view))


@pytest.mark.asyncio
async def test_show_surfaces_existing_log_content(log_dir: Path):
    service_supervisor.log_path("a2a-bridge").write_text(
        "line-A\nline-B\n", encoding="utf-8"
    )
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()

        view = app.query_one("#svc-log-view", RichLog)

        assert any("line-B" in line for line in _rendered_lines(view))


@pytest.mark.asyncio
async def test_show_sets_the_panel_title_to_the_label(log_dir: Path):
    service_supervisor.log_path("a2a-bridge").write_text("line-A\n", encoding="utf-8")
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()

        assert panel.border_title == "Logs: A2A Bridge"


@pytest.mark.asyncio
async def test_retarget_reflects_second_service_content(log_dir: Path):
    service_supervisor.log_path("a2a-bridge").write_text(
        "alpha-first\n", encoding="utf-8"
    )
    service_supervisor.log_path("orchestrator").write_text(
        "omega-second\n", encoding="utf-8"
    )
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()
        panel.show("orchestrator", "Orchestrator")
        await pilot.pause()

        lines = _rendered_lines(app.query_one("#svc-log-view", RichLog))

        assert any("omega-second" in line for line in lines)


@pytest.mark.asyncio
async def test_retarget_clears_stale_first_service_lines(log_dir: Path):
    service_supervisor.log_path("a2a-bridge").write_text(
        "alpha-first\n", encoding="utf-8"
    )
    service_supervisor.log_path("orchestrator").write_text(
        "omega-second\n", encoding="utf-8"
    )
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()
        panel.show("orchestrator", "Orchestrator")
        await pilot.pause()

        lines = _rendered_lines(app.query_one("#svc-log-view", RichLog))

        assert not any("alpha-first" in line for line in lines)


@pytest.mark.asyncio
async def test_retarget_updates_the_panel_title(log_dir: Path):
    service_supervisor.log_path("a2a-bridge").write_text("a\n", encoding="utf-8")
    service_supervisor.log_path("orchestrator").write_text("b\n", encoding="utf-8")
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()
        panel.show("orchestrator", "Orchestrator")
        await pilot.pause()

        assert panel.border_title == "Logs: Orchestrator"


@pytest.mark.asyncio
async def test_pull_new_surfaces_appended_lines(log_dir: Path):
    log_path = service_supervisor.log_path("a2a-bridge")
    log_path.write_text("seed-line\n", encoding="utf-8")
    app = _PanelHost()

    async with app.run_test() as pilot:
        panel = app.query_one("#svc-log-panel", ServiceLogPanel)
        panel.show("a2a-bridge", "A2A Bridge")
        await pilot.pause()

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("appended-line\n")
        panel._pull_new()
        await pilot.pause()

        lines = _rendered_lines(app.query_one("#svc-log-view", RichLog))

        assert any("appended-line" in line for line in lines)
