# -*- coding: utf-8 -*-
"""Tests for dotnet_releases — classification, the 24h cache gate, and the
UI-thread-safe (`get_cached_release_set`) vs network-fetching
(`refresh_release_cache`) split.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal import widget_cache
from cabal.installers import dotnet_releases

_RELEASES_INDEX = [
    {
        "channel-version": "10.0",
        "support-phase": "active",
        "release-type": "lts",
        "latest-sdk": "10.0.100",
    },
    {
        "channel-version": "9.0",
        "support-phase": "active",
        "release-type": "sts",
        "latest-sdk": "9.0.305",
    },
    {
        "channel-version": "8.0",
        "support-phase": "maintenance",
        "release-type": "lts",
        "latest-sdk": "8.0.404",
    },
    {
        "channel-version": "6.0",
        "support-phase": "eol",
        "release-type": "lts",
        "latest-sdk": "6.0.428",
    },
    {
        "channel-version": "11.0",
        "support-phase": "preview",
        "release-type": "lts",
        "latest-sdk": "11.0.0-preview.2.24157.14",
    },
]


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")


def _mark_cache_stale() -> None:
    data = widget_cache._read_all()
    data["entries"][dotnet_releases._CACHE_KEY]["ts"] = "2020-01-01T00:00:00+00:00"
    widget_cache._write_all(data)


def test_classify_picks_latest_and_previous_lts_and_active_preview():
    result = dotnet_releases._classify(_RELEASES_INDEX)

    assert result.latest_lts is not None
    assert result.latest_lts.channel_version == "10.0"
    assert result.previous_lts is not None
    assert result.previous_lts.channel_version == "8.0"
    assert result.preview is not None
    assert result.preview.channel_version == "11.0"
    assert result.preview.latest_sdk == "11.0.0-preview.2.24157.14"


def test_classify_excludes_eol_lts_channels_from_previous_lts():
    index_without_eight = [e for e in _RELEASES_INDEX if e["channel-version"] != "8.0"]

    result = dotnet_releases._classify(index_without_eight)

    assert result.previous_lts is None


def test_get_cached_release_set_never_calls_network_fetch(monkeypatch):
    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("get_cached_release_set must never fetch over the network")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)

    result = dotnet_releases.get_cached_release_set()

    assert result is None


def test_get_cached_release_set_returns_fresh_cache_without_fetching(monkeypatch):
    widget_cache.save_entry(dotnet_releases._CACHE_KEY, _RELEASES_INDEX)

    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("get_cached_release_set must never fetch over the network")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)

    result = dotnet_releases.get_cached_release_set()

    assert result is not None
    assert result.latest_lts.channel_version == "10.0"


def test_get_cached_release_set_falls_back_to_stale_cache_without_fetching(monkeypatch):
    widget_cache.save_entry(dotnet_releases._CACHE_KEY, _RELEASES_INDEX)
    _mark_cache_stale()

    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("get_cached_release_set must never fetch over the network")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)

    result = dotnet_releases.get_cached_release_set()

    assert result is not None
    assert result.latest_lts.channel_version == "10.0"


def test_refresh_release_cache_fetches_and_caches_on_success(monkeypatch):
    calls = {"count": 0}

    def fake_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        calls["count"] += 1
        return _RELEASES_INDEX

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fake_fetch)

    result = dotnet_releases.refresh_release_cache()

    assert calls["count"] == 1
    assert result is not None
    assert result.latest_lts.channel_version == "10.0"
    assert widget_cache.load_entry(dotnet_releases._CACHE_KEY) == _RELEASES_INDEX


def test_refresh_release_cache_skips_network_call_when_cache_is_fresh(monkeypatch):
    widget_cache.save_entry(dotnet_releases._CACHE_KEY, _RELEASES_INDEX)

    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("network fetch should not run when cache is fresh")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)

    result = dotnet_releases.refresh_release_cache()

    assert result is not None
    assert result.latest_lts.channel_version == "10.0"


def test_refresh_release_cache_refetches_when_cache_is_stale(monkeypatch):
    widget_cache.save_entry(dotnet_releases._CACHE_KEY, [])
    _mark_cache_stale()
    calls = {"count": 0}

    def fake_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        calls["count"] += 1
        return _RELEASES_INDEX

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fake_fetch)

    result = dotnet_releases.refresh_release_cache()

    assert calls["count"] == 1
    assert result is not None
    assert result.latest_lts.channel_version == "10.0"


def test_refresh_release_cache_falls_back_to_stale_cache_on_fetch_failure(monkeypatch):
    widget_cache.save_entry(dotnet_releases._CACHE_KEY, _RELEASES_INDEX)
    _mark_cache_stale()
    monkeypatch.setattr(
        dotnet_releases, "_fetch_releases_index", lambda timeout=dotnet_releases._FETCH_TIMEOUT: None
    )

    result = dotnet_releases.refresh_release_cache()

    assert result is not None
    assert result.latest_lts.channel_version == "10.0"


def test_refresh_release_cache_returns_none_when_no_cache_and_fetch_fails(monkeypatch):
    monkeypatch.setattr(
        dotnet_releases, "_fetch_releases_index", lambda timeout=dotnet_releases._FETCH_TIMEOUT: None
    )

    result = dotnet_releases.refresh_release_cache()

    assert result is None


def test_fetch_releases_index_returns_none_on_network_exception(monkeypatch):
    def raise_urlopen(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(dotnet_releases.urllib.request, "urlopen", raise_urlopen)

    assert dotnet_releases._fetch_releases_index() is None
