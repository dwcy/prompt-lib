"""Refresh orchestration for the curated news source catalog."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from cabal.news_feed import CURATED_SOURCES, fetch_source, source_payload


def refresh_sources(preferences: dict[str, bool] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    preferences = preferences or {}

    def load(source):
        return source, fetch_source(source)

    items: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(load, CURATED_SOURCES))
    for source, (values, error) in results:
        enabled = preferences.get(source.id, True)
        statuses.append({**source_payload(source, health="healthy" if not error else "degraded", error_hint=error), "enabled": enabled})
        if enabled:
            items.extend(value.__dict__ for value in values)
    items.sort(key=lambda value: value.get("published_at") or "", reverse=True)
    unique: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in items:
        url = item.get("canonical_url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append(item)
    return unique, statuses
