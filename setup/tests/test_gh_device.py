# -*- coding: utf-8 -*-
"""Mount smoke test for GhDeviceFlowScreen — unique widget IDs, code rendered."""

from __future__ import annotations

import webbrowser

import pytest
from textual.app import App
from textual.widgets import Static

from cabal.views import gh_device
from cabal.views.gh_device import GhDeviceFlowScreen

DEVICE = {
    "user_code": "ABCD-1234",
    "verification_uri": "https://github.com/login/device",
    "device_code": "x",
    "interval": 1,
    "expires_in": 5,
}


@pytest.mark.asyncio
async def test_screen_mounts_with_unique_ids(monkeypatch):
    monkeypatch.setattr(
        gh_device, "gh_device_poll", lambda *a: (False, "", "cancelled")
    )
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)

    app = App()
    async with app.run_test():
        screen = GhDeviceFlowScreen(dict(DEVICE))
        await app.push_screen(screen)

        ids = {w.id for w in screen.query(Static)}
        assert {"gh-title", "gh-instructions", "gh-code", "gh-status-line"} <= ids
