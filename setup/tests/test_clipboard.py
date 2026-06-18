# -*- coding: utf-8 -*-
"""Tests for OS clipboard paste — ctrl+v reads the system clipboard, ctrl+c copies."""

from __future__ import annotations

import pytest
from textual.app import ComposeResult
from textual.widgets import Input

import cabal.app as app_module
from cabal.app import CabalApp
from cabal import clipboard


class _ClipApp(CabalApp):
    """CabalApp with an Input mounted directly, bypassing the project gate."""

    def on_mount(self) -> None:
        pass

    def compose(self) -> ComposeResult:
        yield Input(id="probe")


def test_read_clipboard_returns_str_and_never_raises(monkeypatch):
    monkeypatch.setattr(clipboard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(clipboard, "_read_windows", lambda: "clipboard text")

    result = clipboard.read_clipboard()

    assert result == "clipboard text"


def test_clipboard_property_prefers_os_clipboard(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "C:/projects/demo")
    app = CabalApp()

    assert app.clipboard == "C:/projects/demo"


def test_clipboard_property_falls_back_to_internal_buffer(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    app = CabalApp()
    app._clipboard = "copied-in-app"

    assert app.clipboard == "copied-in-app"


@pytest.mark.asyncio
async def test_ctrl_v_pastes_os_clipboard_into_focused_input(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "C:/projects/demo")
    app = _ClipApp()

    async with app.run_test() as pilot:
        probe = app.query_one("#probe", Input)
        app.set_focus(probe)
        await pilot.pause()
        await pilot.press("ctrl+v")
        await pilot.pause()

        assert probe.value == "C:/projects/demo"


@pytest.mark.asyncio
async def test_ctrl_c_copies_selection_to_clipboard(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    app = _ClipApp()

    async with app.run_test() as pilot:
        probe = app.query_one("#probe", Input)
        probe.value = "selected-path"
        app.set_focus(probe)
        probe.select_all()
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert app._clipboard == "selected-path"
