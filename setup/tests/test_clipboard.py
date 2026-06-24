# -*- coding: utf-8 -*-
"""Tests for OS clipboard paste — ctrl+v reads the system clipboard, ctrl+c copies."""

from __future__ import annotations

import pytest
from textual.app import ComposeResult
from textual.widgets import Input, Static

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


def test_write_clipboard_returns_bool_and_never_raises(monkeypatch):
    monkeypatch.setattr(clipboard.platform, "system", lambda: "Windows")
    monkeypatch.setattr(clipboard, "_write_windows", lambda text: text == "copy me")

    assert clipboard.write_clipboard("copy me") is True


def test_copy_to_clipboard_writes_internal_and_os_clipboards(monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(app_module, "write_clipboard", lambda text: copied.append(text))
    app = CabalApp()

    app.copy_to_clipboard("selected text")

    assert app._clipboard == "selected text"
    assert copied == ["selected text"]


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
async def test_ctrl_shift_v_pastes_os_clipboard_into_focused_input(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "C:/projects/demo")
    app = _ClipApp()

    async with app.run_test() as pilot:
        probe = app.query_one("#probe", Input)
        app.set_focus(probe)
        await pilot.pause()
        await pilot.press("ctrl+shift+v")
        await pilot.pause()

        assert probe.value == "C:/projects/demo"


@pytest.mark.asyncio
async def test_ctrl_c_copies_selection_to_clipboard(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    copied: list[str] = []
    monkeypatch.setattr(app_module, "write_clipboard", lambda text: copied.append(text))
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
        assert copied == ["selected-path"]


@pytest.mark.asyncio
@pytest.mark.parametrize("copy_key", ["ctrl+c", "ctrl+shift+c"])
async def test_copy_keys_copy_screen_selection_even_when_screen_overrides_bindings(
    monkeypatch,
    copy_key,
):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    copied: list[str] = []
    monkeypatch.setattr(app_module, "write_clipboard", lambda text: copied.append(text))
    from cabal.views import project_gate

    monkeypatch.setattr(project_gate, "load_recents", lambda: [])
    app = CabalApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        copyable = app.screen.query_one("#gate-recents-empty", Static)
        copyable.text_select_all()
        await pilot.press(copy_key)
        await pilot.pause()

        assert "No projects opened yet" in app._clipboard
        assert len(copied) == 1
        assert "No projects opened yet" in copied[0]


@pytest.mark.asyncio
async def test_mouse_drag_selection_copies_to_os_clipboard(monkeypatch):
    monkeypatch.setattr(app_module, "read_clipboard", lambda: "")
    copied: list[str] = []
    monkeypatch.setattr(app_module, "write_clipboard", lambda text: copied.append(text))
    from cabal.views import project_gate

    monkeypatch.setattr(project_gate, "load_recents", lambda: [])
    app = CabalApp()

    async with app.run_test(size=(120, 80)) as pilot:
        await pilot.pause()
        await pilot.mouse_down("#gate-recents-empty", offset=(0, 0))
        await pilot.hover("#gate-recents-empty", offset=(22, 0))
        await pilot.mouse_up("#gate-recents-empty", offset=(22, 0))
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert copied == ["No projects opened yet"]
