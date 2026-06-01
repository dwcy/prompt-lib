"""Regression guard for Ctrl+C quitting the CabalApp from any screen.

The default Textual binding set does NOT include ctrl+c — the terminal driver
silently swallows it in raw mode. This test makes sure we don't lose the
explicit binding on the next refactor of BINDINGS.
"""

from __future__ import annotations

import pytest

from cabal.app import CabalApp


@pytest.mark.asyncio
async def test_ctrl_c_quits_from_home_screen():
    app = CabalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert app._exit is True


def test_ctrl_c_binding_present_on_cabal_app():
    binding_keys = {b.key for b in CabalApp.BINDINGS}

    assert "ctrl+c" in binding_keys
