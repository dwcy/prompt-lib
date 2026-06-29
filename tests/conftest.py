"""Shared pytest fixtures for tests/unit and tests/integration.

The cabal package lives at setup/src/cabal; put that on sys.path before any test
imports so we do not require a wheel install.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CABAL_SRC = REPO_ROOT / "setup" / "src"
if str(CABAL_SRC) not in sys.path:
    sys.path.insert(0, str(CABAL_SRC))


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


@pytest.fixture
def tmp_project_dir() -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix="cabal-test-proj-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
