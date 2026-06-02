from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcp_bus.paths import ensure_db  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh isolated SQLite DB per test.

    storage.py binds `db_path` into its own namespace and falls back to it
    whenever a tool passes path=None (which the FastMCP tools always do).
    Patching that name makes every default-path storage call resolve to the
    temp DB, so server tools and direct storage calls share one isolated DB.
    """
    target = tmp_path / "bus.db"
    ensure_db(target)
    monkeypatch.setattr("mcp_bus.storage.db_path", lambda: target)
    return target
