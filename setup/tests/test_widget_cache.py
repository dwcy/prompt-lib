# -*- coding: utf-8 -*-
"""Tests for widget_cache.load_entry_if_fresh — the daily-refresh staleness gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cabal import widget_cache


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")


def test_load_entry_if_fresh_returns_payload_when_within_max_age():
    widget_cache.save_entry("demo", {"value": 1})

    result = widget_cache.load_entry_if_fresh("demo", timedelta(hours=24))

    assert result == {"value": 1}


def test_load_entry_if_fresh_returns_none_when_entry_is_stale():
    widget_cache.save_entry("demo", {"value": 1})
    data = widget_cache._read_all()
    data["entries"]["demo"]["ts"] = (
        datetime.now(timezone.utc) - timedelta(hours=48)
    ).isoformat()
    widget_cache._write_all(data)

    result = widget_cache.load_entry_if_fresh("demo", timedelta(hours=24))

    assert result is None


def test_load_entry_if_fresh_returns_none_when_key_missing():
    result = widget_cache.load_entry_if_fresh("missing", timedelta(hours=24))

    assert result is None
