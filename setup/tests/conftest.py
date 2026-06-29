# -*- coding: utf-8 -*-
"""Pytest bootstrap: make `cabal` importable from the source tree."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


_FAST_ENV = {
    "os": "TestOS",
    "release": "1",
    "python": "3.14.0",
}


@pytest.fixture(autouse=True)
def fast_cabal_background_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep app smoke tests from repeatedly probing the host toolchain."""
    from cabal.widgets import env_panel, update_panel

    monkeypatch.setattr(env_panel, "detect_env", lambda: dict(_FAST_ENV))
    monkeypatch.setattr(
        update_panel,
        "check_for_updates",
        lambda: {"status": "up_to_date", "hash": "testhash", "date": "2026-06-29"},
    )
