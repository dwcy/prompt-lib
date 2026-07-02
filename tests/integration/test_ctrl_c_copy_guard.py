"""Regression guards: Ctrl+C must copy — never quit — on every cabal view.

This keeps breaking silently: a screen-level `ctrl+c` binding shadows the
app-level copy binding for that view only, so the regression is invisible
until someone tries to copy there. These tests scan every screen/widget class
and exercise the runtime path so the guarantee can't rot unnoticed.
"""

from __future__ import annotations

import importlib
import pkgutil
import signal

import pytest

import cabal.views
import cabal.widgets
from cabal.app import CabalApp, _suppress_sigint


def _binding_entries(cls) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for b in cls.__dict__.get("BINDINGS", []):
        if isinstance(b, tuple):
            key, action = str(b[0]), str(b[1])
        else:
            key, action = str(b.key), str(b.action)
        entries.append((key, action))
    return entries


def _classes_with_bindings():
    for package in (cabal.views, cabal.widgets):
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"{package.__name__}.{info.name}")
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and obj.__module__ == module.__name__:
                    if _binding_entries(obj):
                        yield obj


def test_no_view_or_widget_binds_ctrl_c():
    offenders = [
        f"{cls.__module__}.{cls.__name__}: {key} -> {action}"
        for cls in _classes_with_bindings()
        for key, action in _binding_entries(cls)
        if "ctrl+c" in key
    ]
    assert offenders == [], (
        "ctrl+c is reserved app-wide for copy; these bindings shadow it: "
        + "; ".join(offenders)
    )


def test_app_owns_ctrl_c_as_copy_and_quit_stays_on_q():
    entries = _binding_entries(CabalApp)
    ctrl_c_actions = {action for key, action in entries if "ctrl+c" in key}
    quit_keys = {key for key, action in entries if action == "quit"}

    assert ctrl_c_actions == {"copy"}
    assert quit_keys == {"ctrl+q", "q"}


def test_sigint_is_ignored_by_the_entrypoint_guard():
    original = signal.getsignal(signal.SIGINT)
    try:
        _suppress_sigint()
        assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, original)


@pytest.mark.asyncio
async def test_ctrl_c_does_not_quit_the_running_app():
    app = CabalApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert app.is_running


@pytest.mark.asyncio
async def test_ctrl_c_copies_selected_screen_text(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr("cabal.app.write_clipboard", captured.append)

    app = CabalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.text_select_all()
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert app.is_running
        assert captured and captured[0].strip()
