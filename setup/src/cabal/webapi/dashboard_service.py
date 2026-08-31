"""Cache-first per-project dashboard section collectors backing GET /api/dashboard."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from cabal import widget_cache
from cabal.dashboard_azuredevops_service import collect_azure_devops
from cabal.dashboard_git_service import collect_git
from cabal.dashboard_github_service import collect_github
from cabal.dashboard_supabase_service import collect_supabase
from cabal.dashboard_vercel_service import collect_vercel
from cabal.models.dashboard import AvailabilityState

SECTIONS = ("git", "github", "supabase", "vercel", "azure_devops")

_CACHE_PREFIX = "webapi-dashboard:"
_FRESH_WINDOW = timedelta(minutes=5)


def _cache_key(project: Path, section: str) -> str:
    digest = hashlib.sha1(str(project).encode("utf-8")).hexdigest()[:16]
    return f"{_CACHE_PREFIX}{section}:{digest}"


def _stringify_enums(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stringify_enums(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stringify_enums(item) for item in value]
    if isinstance(value, AvailabilityState):
        return value.value
    return value


def _collect(project: Path, section: str) -> dict[str, Any]:
    if section == "git":
        return _stringify_enums(asdict(collect_git(project)))
    if section == "github":
        git = collect_git(project)
        github = collect_github(project, git.current_branch, git.remotes)
        return _stringify_enums(asdict(github))
    if section == "supabase":
        return _stringify_enums(asdict(collect_supabase(project)))
    if section == "vercel":
        return _stringify_enums(asdict(collect_vercel(project)))
    if section == "azure_devops":
        return _stringify_enums(asdict(collect_azure_devops(project)))
    raise ValueError(f"Unknown dashboard section {section!r}")


def get_dashboard_section(project: Path, section: str) -> tuple[dict[str, Any], bool]:
    """Return (section_payload, stale) for `section` — cache-first, live-refresh fallback.

    Mirrors the stale-while-revalidate pattern already used by
    `installers/dotnet_releases.py`: a fresh cache entry is served without doing
    any collector I/O; otherwise a live collect runs and repopulates the cache.
    If the live collect ever raises, the last known cache entry (however old) is
    served with `stale=True` instead of failing the request outright.
    """
    key = _cache_key(project, section)
    fresh = widget_cache.load_entry_if_fresh(key, _FRESH_WINDOW)
    if isinstance(fresh, dict):
        return fresh, False
    try:
        data = _collect(project, section)
    except Exception:
        cached = widget_cache.load_entry(key)
        if isinstance(cached, dict):
            return cached, True
        raise
    widget_cache.save_entry(key, data)
    return data, False
