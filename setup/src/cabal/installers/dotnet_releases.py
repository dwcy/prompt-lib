# -*- coding: utf-8 -*-
"""Fetches and classifies Microsoft's .NET releases-index into latest/previous LTS + preview channels."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from cabal.widget_cache import load_entry, load_entry_if_fresh, save_entry

_RELEASES_INDEX_URL = (
    "https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/releases-index.json"
)
_CACHE_KEY = "dotnet-releases-index"
_CACHE_MAX_AGE = timedelta(hours=24)
_FETCH_TIMEOUT = 5.0
_LTS_SUPPORT_PHASES = {"active", "maintenance"}


@dataclass(frozen=True)
class DotnetChannel:
    channel_version: str
    latest_sdk: str
    support_phase: str
    release_type: str


@dataclass(frozen=True)
class DotnetReleaseSet:
    latest_lts: DotnetChannel | None
    previous_lts: DotnetChannel | None
    preview: DotnetChannel | None


def _parse_channel_version(raw: str) -> tuple[int, int]:
    parts = raw.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return (0, 0)


def _fetch_releases_index(timeout: float = _FETCH_TIMEOUT) -> list[dict] | None:
    """Fetch the raw releases-index payload.

    Any network hiccup or malformed payload returns None rather than raising.
    Only called from `refresh_release_cache`, which the Tools screen runs in a
    background worker thread — never from `compose()` or `version_options_for`.
    """
    try:
        with urllib.request.urlopen(_RELEASES_INDEX_URL, timeout=timeout) as resp:
            payload = json.load(resp)
    except Exception:
        return None
    releases = payload.get("releases-index") if isinstance(payload, dict) else None
    return releases if isinstance(releases, list) else None


def _classify(releases: list[dict]) -> DotnetReleaseSet:
    """Classify releases-index entries into latest LTS / previous LTS / active preview.

    Even/odd parity alone can't tell us which LTS is *current* — an older LTS
    channel keeps reporting support-phase "maintenance" after a newer one goes
    "active", so the phase field (not just the version number) decides "latest".
    """
    lts_channels: list[DotnetChannel] = []
    preview_channel: DotnetChannel | None = None
    for entry in releases:
        if not isinstance(entry, dict):
            continue
        channel_version = entry.get("channel-version")
        latest_sdk = entry.get("latest-sdk")
        support_phase = entry.get("support-phase")
        release_type = entry.get("release-type")
        if not isinstance(channel_version, str) or not isinstance(latest_sdk, str):
            continue
        channel = DotnetChannel(
            channel_version=channel_version,
            latest_sdk=latest_sdk,
            support_phase=support_phase or "",
            release_type=release_type or "",
        )
        if support_phase == "preview":
            if preview_channel is None or _parse_channel_version(
                channel_version
            ) > _parse_channel_version(preview_channel.channel_version):
                preview_channel = channel
            continue
        if release_type == "lts" and support_phase in _LTS_SUPPORT_PHASES:
            lts_channels.append(channel)

    lts_channels.sort(key=lambda c: _parse_channel_version(c.channel_version), reverse=True)
    latest_lts = lts_channels[0] if lts_channels else None
    previous_lts = lts_channels[1] if len(lts_channels) > 1 else None
    return DotnetReleaseSet(latest_lts=latest_lts, previous_lts=previous_lts, preview=preview_channel)


def get_cached_release_set() -> DotnetReleaseSet | None:
    """Read-only: classify whatever is already cached (fresh, else stale). Never fetches.

    Safe to call from the UI thread — `version_options_for("dotnet")` uses this
    during `compose()` so a cache-miss degrades to static placeholders instead
    of blocking on network I/O. The background worker (`refresh_release_cache`)
    is the only path that hits the network and populates this cache.
    """
    cached = load_entry_if_fresh(_CACHE_KEY, _CACHE_MAX_AGE)
    if isinstance(cached, list):
        return _classify(cached)

    stale = load_entry(_CACHE_KEY)
    if isinstance(stale, list):
        return _classify(stale)
    return None


def refresh_release_cache() -> DotnetReleaseSet | None:
    """Fetch + populate the 24h cache. Must only be called off the UI thread.

    Skips the network call when a fresh cache entry already exists (same TTL
    gate `get_cached_release_set` reads), so calling this on every background
    refresh cycle is cheap. Falls back to a stale cache entry on fetch failure
    so a network outage doesn't discard an already-known-good release set.
    """
    cached = load_entry_if_fresh(_CACHE_KEY, _CACHE_MAX_AGE)
    if isinstance(cached, list):
        return _classify(cached)

    fetched = _fetch_releases_index()
    if fetched is not None:
        save_entry(_CACHE_KEY, fetched)
        return _classify(fetched)

    stale = load_entry(_CACHE_KEY)
    if isinstance(stale, list):
        return _classify(stale)
    return None
