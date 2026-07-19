# -*- coding: utf-8 -*-
"""Claude changelog parsing, status classification, and cache behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal import widget_cache
from cabal import claude_release_feed as feed


_CHANGELOG_HTML = """
<div class="update update-container" id="2-1-211">
  <div data-component-part="update-label">2.1.211</div>
  <div data-component-part="update-description">July 11, 2026</div>
  <div data-component-part="update-content"><ul>
    <li>Added <code>--forward-subagent-text</code> for nested agents</li>
    <li>Fixed permission previews in chat channels</li>
    <li>Improved startup performance</li>
    <li>Minor internal cleanup</li>
  </ul></div>
</div>
<div class="update update-container" id="2-1-210">
  <div data-component-part="update-label">2.1.210</div>
  <div data-component-part="update-description">July 10, 2026</div>
  <div data-component-part="update-content"><ul>
    <li>[VSCode] Added a session picker</li>
  </ul></div>
</div>
"""

_STATUS_SUMMARY = {
    "page": {"updated_at": "2026-07-16T19:49:13.185Z"},
    "status": {"indicator": "minor", "description": "Minor Service Outage"},
    "components": [
        {"id": "code", "name": "Claude Code", "status": "partial_outage"},
        {"id": "console", "name": "Claude Console", "status": "operational"},
    ],
    "incidents": [
        {
            "name": "Elevated errors for multiple models",
            "status": "identified",
            "impact": "major",
            "components": [{"id": "code", "name": "Claude Code"}],
        },
        {
            "name": "Console-only incident",
            "status": "investigating",
            "impact": "minor",
            "components": [{"id": "console", "name": "Claude Console"}],
        },
    ],
}


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widget_cache, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(widget_cache, "_CACHE_FILE", tmp_path / "cache.json")


def test_parse_changelog_groups_added_and_other_changes() -> None:
    releases = feed.parse_changelog_html(_CHANGELOG_HTML)

    assert [release.version for release in releases] == ["2.1.211", "2.1.210"]
    assert releases[0].date == "July 11, 2026"
    assert [item.text for item in releases[0].additions] == [
        "Added `--forward-subagent-text` for nested agents"
    ]
    assert [item.category for item in releases[0].other_changes] == [
        "Fixed",
        "Improved",
        "Other",
    ]
    assert releases[1].additions[0].category == "Added"


def test_parse_changelog_ignores_duplicate_rendered_versions() -> None:
    releases = feed.parse_changelog_html(_CHANGELOG_HTML + _CHANGELOG_HTML)

    assert [release.version for release in releases] == ["2.1.211", "2.1.210"]


def test_parse_status_summary_highlights_claude_code_and_relevant_incidents() -> None:
    status = feed.parse_status_summary(_STATUS_SUMMARY)

    assert status is not None
    assert status.component_status == "partial_outage"
    assert status.overall_indicator == "minor"
    assert status.overall_description == "Minor Service Outage"
    assert [incident.name for incident in status.incidents] == [
        "Elevated errors for multiple models"
    ]


def test_refresh_changelog_caches_successful_fetch(monkeypatch) -> None:
    expected = feed.parse_changelog_html(_CHANGELOG_HTML)
    monkeypatch.setattr(feed, "_fetch_changelog", lambda: expected)

    result = feed.refresh_changelog(force=True)

    assert result == expected
    assert feed.get_cached_changelog() == expected


def test_refresh_changelog_falls_back_to_stale_cache(monkeypatch) -> None:
    expected = feed.parse_changelog_html(_CHANGELOG_HTML)
    monkeypatch.setattr(feed, "_fetch_changelog", lambda: expected)
    feed.refresh_changelog(force=True)
    monkeypatch.setattr(feed, "_fetch_changelog", lambda: None)

    result = feed.refresh_changelog(force=True)

    assert result == expected


def test_refresh_status_caches_successful_fetch(monkeypatch) -> None:
    expected = feed.parse_status_summary(_STATUS_SUMMARY)
    assert expected is not None
    monkeypatch.setattr(feed, "_fetch_status", lambda: expected)

    result = feed.refresh_status(force=True)

    assert result == expected
    assert feed.get_cached_status() == expected


def test_fetch_helpers_fail_closed_on_network_errors(monkeypatch) -> None:
    def fail_request(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(feed, "_request_bytes", fail_request)

    assert feed._fetch_changelog() is None
    assert feed._fetch_status() is None
