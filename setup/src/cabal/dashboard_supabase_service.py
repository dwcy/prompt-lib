# -*- coding: utf-8 -*-
"""Supabase collector for the dashboard — all `supabase` CLI + Management API I/O lives here."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cabal.dashboard_links import (
    find_supabase_ref,
    supabase_dashboard_url,
    supabase_schema_url,
)
from cabal.models.dashboard import AvailabilityState, ProjectMember, SupabaseSection

_SUPABASE = "supabase"
_TIMEOUT = 10
_DB_HOST_TEMPLATE = "db.{ref}.supabase.co"

_TOKEN_ENV = "SUPABASE_ACCESS_TOKEN"
_API_BASE = "https://api.supabase.com"
_PATH_PROJECTS = "/v1/projects"
_PATH_BACKUPS = "/v1/projects/{ref}/database/backups"
_PATH_ORG_MEMBERS = "/v1/organizations/{slug}/members"

_ARGS_MIGRATION_LIST = ("migration", "list")

_HINT_NO_LINK = "no linked Supabase project"
_HINT_TOKEN_MISSING = "set SUPABASE_ACCESS_TOKEN for plan/region/members/backups"
_HINT_TOKEN_REJECTED = "Supabase token rejected"
_HINT_TIMEOUT = "Supabase Management API timed out"


def collect_supabase(project: Path) -> SupabaseSection:
    """Collect the Supabase baseline + token-enriched state for `project`; never raises."""
    ref = find_supabase_ref(project)
    if ref is None:
        return SupabaseSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NO_LINK)

    section = SupabaseSection(
        state=AvailabilityState.OK,
        project_ref=ref,
        dashboard_url=supabase_dashboard_url(ref),
        schema_visualizer_url=supabase_schema_url(ref),
        db_location=_DB_HOST_TEMPLATE.format(ref=ref),
        last_migration=_collect_last_migration(project),
    )
    _enrich(section, ref)
    return section


def _collect_last_migration(project: Path) -> str | None:
    """Return the most-recent applied migration id/name via the CLI, or None when absent."""
    cli = shutil.which(_SUPABASE)
    if cli is None:
        return None
    try:
        result = subprocess.run(
            [cli, *_ARGS_MIGRATION_LIST],
            cwd=str(project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return _parse_last_migration(result.stdout or "")


def _parse_last_migration(output: str) -> str | None:
    """Pick the most-recent applied migration from `supabase migration list` table output."""
    latest: str | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or "|" not in stripped:
            continue
        cells = [cell.strip() for cell in stripped.split("|")]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        head = cells[0].lower()
        if head in ("local", "remote", "time"):
            continue
        applied = cells[0]
        if applied.isdigit():
            latest = applied
    return latest


def _enrich(section: SupabaseSection, ref: str) -> None:
    """Populate token-enriched fields in place; degrade per-call, never raise."""
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        section.enrich_state = AvailabilityState.TOKEN_MISSING
        section.enrich_hint = _HINT_TOKEN_MISSING
        return

    status, payload = _api_get(_PATH_PROJECTS, token)
    if status in (401, 403):
        section.enrich_state = AvailabilityState.TOKEN_REJECTED
        section.enrich_hint = _HINT_TOKEN_REJECTED
        return
    if status == 0:
        section.enrich_state = AvailabilityState.TIMEOUT
        section.enrich_hint = _HINT_TIMEOUT
        return

    org_slug = _apply_project_fields(section, payload, ref)
    _apply_last_backup(section, ref, token)
    if org_slug is not None:
        _apply_org_members(section, org_slug, token)
    section.enrich_state = AvailabilityState.OK


def _apply_project_fields(
    section: SupabaseSection, payload: Any, ref: str
) -> str | None:
    """Set status/region/db host from the matching project entry; return its org slug if any."""
    if not isinstance(payload, list):
        return None
    for entry in payload:
        if not isinstance(entry, dict) or entry.get("id") != ref:
            continue
        section.status = _as_str(entry.get("status"))
        section.region = _as_str(entry.get("region"))
        host = entry.get("database")
        if isinstance(host, dict):
            section.db_location = _as_str(host.get("host")) or section.db_location
        org = entry.get("organization_slug") or entry.get("organization_id")
        return _as_str(org)
    return None


def _apply_last_backup(section: SupabaseSection, ref: str, token: str) -> None:
    status, payload = _api_get(_PATH_BACKUPS.format(ref=ref), token)
    if status != 200:
        return
    backups: Any = payload
    if isinstance(payload, dict):
        backups = payload.get("backups")
    if not isinstance(backups, list):
        return
    timestamps = [
        _as_str(b.get("inserted_at") or b.get("created_at"))
        for b in backups
        if isinstance(b, dict)
    ]
    timestamps = [ts for ts in timestamps if ts]
    if timestamps:
        section.last_backup = max(timestamps)


def _apply_org_members(section: SupabaseSection, slug: str, token: str) -> None:
    status, payload = _api_get(_PATH_ORG_MEMBERS.format(slug=slug), token)
    if status != 200 or not isinstance(payload, list):
        return
    members: list[ProjectMember] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        name = _as_str(
            entry.get("username") or entry.get("user_name") or entry.get("email")
        )
        if name is None:
            continue
        members.append(ProjectMember(name=name, role=_as_str(entry.get("role_name"))))
    section.members = members


def _api_get(path: str, token: str) -> tuple[int, Any]:
    """GET `<_API_BASE><path>` with a bearer token; return (status, parsed-json).

    Status 0 signals a timeout/transport failure. Never raises; never logs the token.
    """
    request = urllib.request.Request(
        f"{_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, _parse_json(body)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


def _parse_json(body: str) -> Any:
    try:
        return json.loads(body or "null")
    except ValueError:
        return None


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
