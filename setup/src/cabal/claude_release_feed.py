# -*- coding: utf-8 -*-
"""Cached Claude Code changelog and service-status feeds."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from html.parser import HTMLParser
from typing import Any

from cabal import widget_cache

CHANGELOG_URL = "https://code.claude.com/docs/en/changelog"
STATUS_URL = "https://status.claude.com/"
STATUS_SUMMARY_URL = "https://status.claude.com/api/v2/summary.json"

_CHANGELOG_CACHE_KEY = "claude-code-changelog"
_STATUS_CACHE_KEY = "claude-service-status"
_CHANGELOG_CACHE_MAX_AGE = timedelta(hours=1)
_STATUS_CACHE_MAX_AGE = timedelta(minutes=2)
_FETCH_TIMEOUT = 10.0
_MAX_CHANGELOG_BYTES = 8 * 1024 * 1024
_MAX_STATUS_BYTES = 1024 * 1024

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_CATEGORY_RE = re.compile(
    r"^(?:\[[^]]+\]\s*)?(?:(?:[A-Za-z][\w.-]*):\s*)?"
    r"(Added|Fixed|Improved|Changed|Updated|Removed|Deprecated|Restored)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChangelogItem:
    category: str
    text: str


@dataclass(frozen=True)
class ChangelogRelease:
    version: str
    date: str
    changes: tuple[ChangelogItem, ...]

    @property
    def additions(self) -> tuple[ChangelogItem, ...]:
        return tuple(item for item in self.changes if item.category == "Added")

    @property
    def other_changes(self) -> tuple[ChangelogItem, ...]:
        return tuple(item for item in self.changes if item.category != "Added")


@dataclass(frozen=True)
class StatusIncident:
    name: str
    status: str
    impact: str


@dataclass(frozen=True)
class ClaudeServiceStatus:
    component_status: str
    overall_indicator: str
    overall_description: str
    updated_at: str
    incidents: tuple[StatusIncident, ...]


def _normalise_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _change_category(text: str) -> str:
    match = _CATEGORY_RE.match(text)
    return match.group(1).title() if match else "Other"


class _ClaudeChangelogParser(HTMLParser):
    """Read Mintlify's semantic update elements without depending on CSS classes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.releases: list[ChangelogRelease] = []
        self._seen_versions: set[str] = set()
        self._version = ""
        self._date = ""
        self._changes: list[ChangelogItem] = []
        self._label_parts: list[str] | None = None
        self._date_parts: list[str] | None = None
        self._item_parts: list[str] | None = None
        self._content_div_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        part = attributes.get("data-component-part")

        if part == "update-label":
            self._label_parts = []
        elif part == "update-description":
            self._date_parts = []
        elif part == "update-content":
            self._changes = []
            self._content_div_depth = 1
        elif self._content_div_depth and tag == "div":
            self._content_div_depth += 1

        if self._content_div_depth and tag == "li":
            self._item_parts = []
        elif self._item_parts is not None and tag == "code":
            self._item_parts.append("`")
        elif self._item_parts is not None and tag == "br":
            self._item_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._item_parts is not None and tag == "code":
            self._item_parts.append("`")
        elif self._item_parts is not None and tag == "li":
            text = _normalise_text(self._item_parts)
            if text:
                self._changes.append(
                    ChangelogItem(category=_change_category(text), text=text)
                )
            self._item_parts = None

        if tag != "div":
            return

        if self._label_parts is not None:
            label = _normalise_text(self._label_parts)
            self._version = label if _VERSION_RE.match(label) else ""
            self._label_parts = None
            return

        if self._date_parts is not None:
            self._date = _normalise_text(self._date_parts)
            self._date_parts = None
            return

        if self._content_div_depth:
            self._content_div_depth -= 1
            if self._content_div_depth == 0:
                self._finish_release()

    def handle_data(self, data: str) -> None:
        if self._label_parts is not None:
            self._label_parts.append(data)
        elif self._date_parts is not None:
            self._date_parts.append(data)
        elif self._item_parts is not None:
            self._item_parts.append(data)

    def _finish_release(self) -> None:
        if (
            self._version
            and self._changes
            and self._version not in self._seen_versions
        ):
            self.releases.append(
                ChangelogRelease(
                    version=self._version,
                    date=self._date,
                    changes=tuple(self._changes),
                )
            )
            self._seen_versions.add(self._version)
        self._version = ""
        self._date = ""
        self._changes = []


def parse_changelog_html(html: str) -> tuple[ChangelogRelease, ...]:
    parser = _ClaudeChangelogParser()
    parser.feed(html)
    parser.close()
    return tuple(parser.releases)


def parse_status_summary(payload: dict[str, Any]) -> ClaudeServiceStatus | None:
    status = payload.get("status")
    page = payload.get("page")
    components = payload.get("components")
    incidents = payload.get("incidents")
    if not isinstance(status, dict) or not isinstance(components, list):
        return None

    claude_code = next(
        (
            component
            for component in components
            if isinstance(component, dict) and component.get("name") == "Claude Code"
        ),
        None,
    )
    component_status = (
        str(claude_code.get("status", "unknown"))
        if isinstance(claude_code, dict)
        else "unknown"
    )
    component_id = (
        str(claude_code.get("id", "")) if isinstance(claude_code, dict) else ""
    )

    relevant_incidents: list[StatusIncident] = []
    if isinstance(incidents, list):
        for incident in incidents:
            if not isinstance(incident, dict):
                continue
            affected = incident.get("components")
            if component_id and isinstance(affected, list):
                affects_claude_code = any(
                    isinstance(component, dict)
                    and str(component.get("id", "")) == component_id
                    for component in affected
                )
                if not affects_claude_code:
                    continue
            name = incident.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            relevant_incidents.append(
                StatusIncident(
                    name=name.strip(),
                    status=str(incident.get("status", "")),
                    impact=str(incident.get("impact", "")),
                )
            )

    return ClaudeServiceStatus(
        component_status=component_status,
        overall_indicator=str(status.get("indicator", "none")),
        overall_description=str(status.get("description", "Unknown")),
        updated_at=str(page.get("updated_at", "")) if isinstance(page, dict) else "",
        incidents=tuple(relevant_incidents),
    )


def _request_bytes(url: str, limit: int, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/json",
            "User-Agent": "Cabal-Claude-Info/1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise ValueError(f"response from {url} exceeded {limit} bytes")
    return payload


def _fetch_changelog(
    timeout: float = _FETCH_TIMEOUT,
) -> tuple[ChangelogRelease, ...] | None:
    try:
        payload = _request_bytes(CHANGELOG_URL, _MAX_CHANGELOG_BYTES, timeout)
        releases = parse_changelog_html(payload.decode("utf-8", errors="replace"))
    except Exception:
        return None
    return releases or None


def _fetch_status(timeout: float = _FETCH_TIMEOUT) -> ClaudeServiceStatus | None:
    try:
        payload = _request_bytes(STATUS_SUMMARY_URL, _MAX_STATUS_BYTES, timeout)
        decoded = json.loads(payload)
    except Exception:
        return None
    return parse_status_summary(decoded) if isinstance(decoded, dict) else None


def _release_to_dict(release: ChangelogRelease) -> dict[str, Any]:
    return {
        "version": release.version,
        "date": release.date,
        "changes": [
            {"category": item.category, "text": item.text}
            for item in release.changes
        ],
    }


def _release_from_dict(value: object) -> ChangelogRelease | None:
    if not isinstance(value, dict):
        return None
    version = value.get("version")
    date = value.get("date")
    changes = value.get("changes")
    if not isinstance(version, str) or not isinstance(date, str):
        return None
    if not isinstance(changes, list):
        return None
    parsed_changes: list[ChangelogItem] = []
    for change in changes:
        if not isinstance(change, dict):
            return None
        category = change.get("category")
        text = change.get("text")
        if not isinstance(category, str) or not isinstance(text, str):
            return None
        parsed_changes.append(ChangelogItem(category=category, text=text))
    return ChangelogRelease(version, date, tuple(parsed_changes))


def _status_to_dict(status: ClaudeServiceStatus) -> dict[str, Any]:
    return {
        "component_status": status.component_status,
        "overall_indicator": status.overall_indicator,
        "overall_description": status.overall_description,
        "updated_at": status.updated_at,
        "incidents": [
            {
                "name": incident.name,
                "status": incident.status,
                "impact": incident.impact,
            }
            for incident in status.incidents
        ],
    }


def _status_from_dict(value: object) -> ClaudeServiceStatus | None:
    if not isinstance(value, dict):
        return None
    fields = (
        "component_status",
        "overall_indicator",
        "overall_description",
        "updated_at",
    )
    if any(not isinstance(value.get(field), str) for field in fields):
        return None
    raw_incidents = value.get("incidents")
    if not isinstance(raw_incidents, list):
        return None
    incidents: list[StatusIncident] = []
    for incident in raw_incidents:
        if not isinstance(incident, dict):
            return None
        name = incident.get("name")
        status = incident.get("status")
        impact = incident.get("impact")
        if not all(isinstance(field, str) for field in (name, status, impact)):
            return None
        incidents.append(StatusIncident(name, status, impact))
    return ClaudeServiceStatus(
        component_status=value["component_status"],
        overall_indicator=value["overall_indicator"],
        overall_description=value["overall_description"],
        updated_at=value["updated_at"],
        incidents=tuple(incidents),
    )


def _cached_releases(*, fresh_only: bool) -> tuple[ChangelogRelease, ...] | None:
    raw = (
        widget_cache.load_entry_if_fresh(
            _CHANGELOG_CACHE_KEY, _CHANGELOG_CACHE_MAX_AGE
        )
        if fresh_only
        else widget_cache.load_entry(_CHANGELOG_CACHE_KEY)
    )
    if not isinstance(raw, list):
        return None
    releases = tuple(
        parsed for value in raw if (parsed := _release_from_dict(value)) is not None
    )
    return releases or None


def get_cached_changelog() -> tuple[ChangelogRelease, ...] | None:
    return _cached_releases(fresh_only=False)


def refresh_changelog(
    *, force: bool = False
) -> tuple[ChangelogRelease, ...] | None:
    if not force and (cached := _cached_releases(fresh_only=True)) is not None:
        return cached
    fetched = _fetch_changelog()
    if fetched is not None:
        widget_cache.save_entry(
            _CHANGELOG_CACHE_KEY,
            [_release_to_dict(release) for release in fetched],
        )
        return fetched
    return _cached_releases(fresh_only=False)


def _cached_status(*, fresh_only: bool) -> ClaudeServiceStatus | None:
    raw = (
        widget_cache.load_entry_if_fresh(_STATUS_CACHE_KEY, _STATUS_CACHE_MAX_AGE)
        if fresh_only
        else widget_cache.load_entry(_STATUS_CACHE_KEY)
    )
    return _status_from_dict(raw)


def get_cached_status() -> ClaudeServiceStatus | None:
    return _cached_status(fresh_only=False)


def refresh_status(*, force: bool = False) -> ClaudeServiceStatus | None:
    if not force and (cached := _cached_status(fresh_only=True)) is not None:
        return cached
    fetched = _fetch_status()
    if fetched is not None:
        widget_cache.save_entry(_STATUS_CACHE_KEY, _status_to_dict(fetched))
        return fetched
    return _cached_status(fresh_only=False)
