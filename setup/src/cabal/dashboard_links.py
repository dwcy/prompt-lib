# -*- coding: utf-8 -*-
"""Pure link-file parsing + URL derivation for the dashboard — no subprocess, no network."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

SUPABASE_DASHBOARD_BASE = "https://supabase.com/dashboard/project"
_GITHUB_HTTPS = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)
_GITHUB_SSH = re.compile(
    r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def find_supabase_ref(project: Path) -> str | None:
    """Return the linked Supabase project ref from `<project>/supabase/config.toml`, or None."""
    config = project / "supabase" / "config.toml"
    if not config.is_file():
        return None
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ref = data.get("project_id")
    return ref if isinstance(ref, str) and ref else None


def supabase_dashboard_url(ref: str) -> str:
    return f"{SUPABASE_DASHBOARD_BASE}/{ref}"


def supabase_schema_url(ref: str) -> str:
    return f"{SUPABASE_DASHBOARD_BASE}/{ref}/database/schemas"


def find_vercel_link(project: Path) -> tuple[str | None, str | None]:
    """Return (projectId, orgId) from `<project>/.vercel/project.json`, or (None, None)."""
    link = project / ".vercel" / "project.json"
    if not link.is_file():
        return None, None
    try:
        data = json.loads(link.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    project_id = data.get("projectId")
    org_id = data.get("orgId")
    return (
        project_id if isinstance(project_id, str) else None,
        org_id if isinstance(org_id, str) else None,
    )


def parse_github_remote(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) for an HTTPS/SSH github.com remote, else None."""
    candidate = (url or "").strip()
    match = _GITHUB_HTTPS.match(candidate) or _GITHUB_SSH.match(candidate)
    if not match:
        return None
    owner = match.group("owner")
    repo = match.group("repo")
    if not owner or not repo:
        return None
    return owner, repo
