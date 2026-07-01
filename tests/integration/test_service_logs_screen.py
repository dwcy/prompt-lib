# -*- coding: utf-8 -*-
"""Smoke tests for ServiceLogScreen — mounts via run_test() and tails a service's capture log.

Mounts the log screen through Textual's pilot pipeline (so framework-shadow bugs surface)
against a tmp_path capture-log dir, and asserts the empty-hint / existing-content seeding
plus that runnable service rows expose a Logs control while the non-runnable mcp-bus does not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import RichLog

from cabal import service_supervisor
from cabal.app import CabalApp
from cabal.service_catalog import all_services
from cabal.views.service_logs import _EMPTY_HINT, ServiceLogScreen
from cabal.views.services import ServicesScreen


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the supervisor's capture-log dir into tmp_path so nothing touches ~/.cabal."""
    target = tmp_path / "logs"
    monkeypatch.setattr(service_supervisor, "_LOG_DIR", target)
    return target


def _rendered_lines(view: RichLog) -> list[str]:
    return [strip.text for strip in view.lines]


@pytest.mark.asyncio
async def test_empty_log_shows_the_empty_hint(log_dir: Path):
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(ServiceLogScreen("a2a-bridge", "A2A Bridge"))
        await pilot.pause()

        view = app.screen.query_one("#svc-log-view", RichLog)
        assert any(_EMPTY_HINT in line for line in _rendered_lines(view))


@pytest.mark.asyncio
async def test_existing_content_is_surfaced_on_mount(log_dir: Path):
    log_path = service_supervisor.log_path("a2a-bridge")
    log_path.write_text("line-A\nline-B\n", encoding="utf-8")

    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(ServiceLogScreen("a2a-bridge", "A2A Bridge"))
        await pilot.pause()

        view = app.screen.query_one("#svc-log-view", RichLog)
        assert any("line-B" in line for line in _rendered_lines(view))


@pytest.mark.asyncio
async def test_runnable_rows_have_a_logs_button():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        for service in all_services():
            if not service.runnable:
                continue
            assert screen.query(f"#svc-logs-{service.key}")


@pytest.mark.asyncio
async def test_non_runnable_rows_have_no_logs_button():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        for service in all_services():
            if service.runnable:
                continue
            assert not screen.query(f"#svc-logs-{service.key}")
