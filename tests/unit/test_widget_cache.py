"""Unit tests for cabal.widget_cache — the stale-while-revalidate JSON store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal import widget_cache


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")
    yield tmp_path


def test_load_entry_returns_none_when_file_absent(isolated_cache):
    result = widget_cache.load_entry("env")

    assert result is None


def test_save_then_load_round_trips_dict(isolated_cache):
    payload = {"os": "Windows", "python": "3.11.1", "ollama_models": ["llama3"]}

    widget_cache.save_entry("env", payload)
    result = widget_cache.load_entry("env")

    assert result == payload


def test_save_writes_timestamp_alongside_payload(isolated_cache):
    widget_cache.save_entry("updates", {"status": "up_to_date"})

    raw = json.loads((isolated_cache / "cache.json").read_text(encoding="utf-8"))

    assert "ts" in raw["entries"]["updates"]
    assert raw["entries"]["updates"]["payload"] == {"status": "up_to_date"}


def test_load_entry_returns_none_on_corrupt_file(isolated_cache):
    (isolated_cache / "cache.json").write_text("not json {", encoding="utf-8")

    result = widget_cache.load_entry("env")

    assert result is None


def test_load_entry_returns_none_on_schema_mismatch(isolated_cache):
    (isolated_cache / "cache.json").write_text(
        json.dumps({"schema": 999, "entries": {"env": {"payload": {"x": 1}}}}),
        encoding="utf-8",
    )

    result = widget_cache.load_entry("env")

    assert result is None


def test_multiple_keys_coexist(isolated_cache):
    widget_cache.save_entry("env", {"os": "Linux"})
    widget_cache.save_entry("updates", {"status": "behind"})

    assert widget_cache.load_entry("env") == {"os": "Linux"}
    assert widget_cache.load_entry("updates") == {"status": "behind"}


def test_save_overwrites_existing_entry(isolated_cache):
    widget_cache.save_entry("env", {"os": "Windows"})
    widget_cache.save_entry("env", {"os": "Linux"})

    result = widget_cache.load_entry("env")

    assert result == {"os": "Linux"}


def test_load_entry_for_unknown_key_returns_none(isolated_cache):
    widget_cache.save_entry("env", {"os": "Windows"})

    result = widget_cache.load_entry("never-written")

    assert result is None
