# -*- coding: utf-8 -*-
"""Mount-and-render smoke tests for ContextGuardScreen."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Static

from cabal.views.context_guard import ContextGuardScreen


@pytest.fixture
def stub_policy(monkeypatch):
    saved: list[dict] = []
    state = {"enabled": False, "threshold_percent": 80, "max_context_tokens": 200000}

    def fake_load():
        return dict(state)

    def fake_save(policy):
        saved.append(dict(policy))
        state.update(policy)
        return Path("/fake/context-guard-policy.json")

    monkeypatch.setattr("cabal.views.context_guard.load_policy", fake_load)
    monkeypatch.setattr("cabal.views.context_guard.save_policy", fake_save)
    monkeypatch.setattr(
        "cabal.views.context_guard.policy_source",
        lambda: Path("/fake/context-guard-policy.json"),
    )
    return saved


async def _mounted_screen(app: App, pilot) -> ContextGuardScreen:
    screen = ContextGuardScreen()
    await app.push_screen(screen)
    await pilot.pause()
    return screen


@pytest.mark.asyncio
async def test_screen_loads_current_policy_into_the_form(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        enabled = screen.query_one("#cg-enabled", Checkbox).value
        threshold = screen.query_one("#cg-threshold", Input).value
        max_tokens = screen.query_one("#cg-max-tokens", Input).value

    assert enabled is False
    assert threshold == "80"
    assert max_tokens == "200000"


@pytest.mark.asyncio
async def test_saving_writes_the_edited_values(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.query_one("#cg-enabled", Checkbox).value = True
        screen.query_one("#cg-threshold", Input).value = "75"
        screen.query_one("#cg-max-tokens", Input).value = "1000000"
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-save", Button)))
        await pilot.pause()

    assert stub_policy == [
        {"enabled": True, "threshold_percent": 75, "max_context_tokens": 1000000}
    ]


@pytest.mark.asyncio
async def test_saving_shows_confirmation_status(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-save", Button)))
        await pilot.pause()
        status = str(screen.query_one("#cg-status", Static).render())

    assert "Saved" in status


@pytest.mark.asyncio
async def test_invalid_threshold_over_100_is_rejected_without_saving(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.query_one("#cg-threshold", Input).value = "150"
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-save", Button)))
        await pilot.pause()
        status = str(screen.query_one("#cg-status", Static).render())

    assert stub_policy == []
    assert "100" in status


@pytest.mark.asyncio
async def test_non_numeric_max_tokens_is_rejected_without_saving(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.query_one("#cg-max-tokens", Input).value = "not-a-number"
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-save", Button)))
        await pilot.pause()
        status = str(screen.query_one("#cg-status", Static).render())

    assert stub_policy == []
    assert "not-a-number" in status


@pytest.mark.asyncio
async def test_zero_threshold_is_rejected_without_saving(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.query_one("#cg-threshold", Input).value = "0"
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-save", Button)))
        await pilot.pause()

    assert stub_policy == []


@pytest.mark.asyncio
async def test_reload_restores_the_currently_persisted_policy(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        screen = await _mounted_screen(app, pilot)

        screen.query_one("#cg-threshold", Input).value = "12"
        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-reload", Button)))
        await pilot.pause()

        threshold = screen.query_one("#cg-threshold", Input).value

    assert threshold == "80"


@pytest.mark.asyncio
async def test_back_button_pops_the_screen(stub_policy):
    app = App()
    async with app.run_test() as pilot:
        home = Screen()
        await app.push_screen(home)
        await pilot.pause()
        screen = await _mounted_screen(app, pilot)

        screen.on_button_pressed(Button.Pressed(screen.query_one("#cg-back", Button)))
        await pilot.pause()
        final_screen = app.screen

    assert final_screen is home
