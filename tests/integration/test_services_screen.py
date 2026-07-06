"""Smoke tests for ServicesScreen — mounts via compose() and renders one row per service (T008).

Mount through Textual's run_test() pipeline so framework-shadow bugs surface, and
assert each runnable service row exposes a Start control.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button

from cabal.app import CabalApp
from cabal.service_catalog import all_services
from cabal.views.services import ServicesScreen
from cabal.widgets.service_log_panel import ServiceLogPanel


@pytest.mark.asyncio
async def test_services_screen_mounts_without_error():
    app = CabalApp()
    async with app.run_test() as pilot:
        app.push_screen(ServicesScreen())
        await pilot.pause()

        assert isinstance(app.screen, ServicesScreen)


@pytest.mark.asyncio
async def test_services_screen_renders_a_row_per_service():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        for service in all_services():
            assert screen.query(f"#svc-row-{service.key}")


@pytest.mark.asyncio
async def test_services_screen_labels_each_service():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        names = {str(static.render()) for static in screen.query(".svc-name")}
        for service in all_services():
            assert any(service.label in name for name in names)


@pytest.mark.asyncio
async def test_runnable_rows_have_a_start_button():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        for service in all_services():
            if not service.runnable:
                continue
            row = screen.query_one(f"#svc-row-{service.key}")
            buttons = list(row.query(Button))
            assert any("start" in (btn.id or "").lower() for btn in buttons)


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


@pytest.mark.asyncio
async def test_services_screen_embeds_the_inline_log_panel():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#svc-log-panel", ServiceLogPanel)


@pytest.mark.asyncio
async def test_open_logs_targets_the_panel_for_the_service():
    app = CabalApp()
    async with app.run_test() as pilot:
        screen = ServicesScreen()
        app.push_screen(screen)
        await pilot.pause()

        service = next(s for s in all_services() if s.runnable)
        screen._open_logs(service.key)
        await pilot.pause()

        panel = screen.query_one("#svc-log-panel", ServiceLogPanel)
        assert panel.border_title == f"Logs: {service.label}"
