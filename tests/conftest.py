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


@pytest.fixture
def tmp_project_dir() -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix="cabal-test-proj-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
