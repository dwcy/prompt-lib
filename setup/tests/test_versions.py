# -*- coding: utf-8 -*-
"""Tests for version_options_for's dotnet branch — real SDK versions, not channel placeholders."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal import widget_cache
from cabal.installers import dotnet_releases, versions
from cabal.installers.dotnet_releases import DotnetChannel, DotnetReleaseSet


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")


def test_dotnet_options_use_real_sdk_versions_from_release_set(monkeypatch):
    release_set = DotnetReleaseSet(
        latest_lts=DotnetChannel("10.0", "10.0.100", "active", "lts"),
        previous_lts=DotnetChannel("8.0", "8.0.404", "maintenance", "lts"),
        preview=DotnetChannel("11.0", "11.0.0-preview.2.24157.14", "preview", "lts"),
    )
    monkeypatch.setattr(versions, "get_cached_release_set", lambda: release_set)
    monkeypatch.setattr(versions, "installed_version_for", lambda _key: "9.0.100")

    result = versions.version_options_for("dotnet")

    by_channel = {opt.channel: opt for opt in result.options}
    assert by_channel["lts"].version == "10.0.100"
    assert by_channel["lts"].label == "Latest LTS (10.0.100)"
    assert by_channel["lts"].is_lts is True
    assert by_channel["lts"].is_latest is True
    assert by_channel["lts-previous"].version == "8.0.404"
    assert by_channel["lts-previous"].is_lts is True
    assert by_channel["lts-previous"].is_latest is False
    assert by_channel["preview"].version == "11.0.0-preview.2.24157.14"
    assert by_channel["preview"].is_lts is False
    assert by_channel["preview"].is_latest is False


def test_dotnet_options_fall_back_to_placeholders_when_release_set_unavailable(monkeypatch):
    monkeypatch.setattr(versions, "get_cached_release_set", lambda: None)
    monkeypatch.setattr(versions, "installed_version_for", lambda _key: "9.0.100")

    result = versions.version_options_for("dotnet")

    versions_seen = {opt.version for opt in result.options}
    assert "lts" in versions_seen
    assert "sts" in versions_seen


def test_version_options_for_dotnet_never_calls_the_network_fetch_function(monkeypatch):
    def fail_fetch(timeout=dotnet_releases._FETCH_TIMEOUT):
        raise AssertionError("version_options_for must never fetch over the network")

    monkeypatch.setattr(dotnet_releases, "_fetch_releases_index", fail_fetch)
    monkeypatch.setattr(versions, "installed_version_for", lambda _key: "9.0.100")

    result = versions.version_options_for("dotnet")

    assert result.options
