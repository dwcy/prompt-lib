# -*- coding: utf-8 -*-
"""Vercel collector for the dashboard — all `vercel` CLI + REST API I/O lives here."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cabal.dashboard_links import find_vercel_link
from cabal.models.dashboard import AvailabilityState, ProjectMember, VercelSection

_VERCEL = "vercel"
_TIMEOUT = 10

_TOKEN_ENV = "VERCEL_TOKEN"
_API_BASE = "https://api.vercel.com"
_PATH_PROJECT = "/v9/projects/{project_id}"
_PATH_DEPLOYMENTS = "/v6/deployments?projectId={project_id}&limit=1"
_PATH_TEAM = "/v2/teams/{org_id}"
_PATH_TEAM_MEMBERS = "/v2/teams/{org_id}/members"

_DASHBOARD_BASE = "https://vercel.com"

_ARGS_PROJECT_LS = ("project", "ls", "--json")

_HINT_NO_LINK = "no linked Vercel project"
_HINT_TOKEN_MISSING = "set VERCEL_TOKEN for team/plan/region/members"
_HINT_TOKEN_REJECTED = "Vercel token rejected"
_HINT_TIMEOUT = "Vercel REST API timed out"


def collect_vercel(project: Path) -> VercelSection:
    """Collect the Vercel baseline + token-enriched state for `project`; never raises."""
    project_id, org_id = find_vercel_link(project)
    if project_id is None:
        return VercelSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NO_LINK)

    section = VercelSection(state=AvailabilityState.OK, project_id=project_id)
    _collect_cli_baseline(section, project)
    _enrich(section, project_id, org_id)
    return section


def _collect_cli_baseline(section: VercelSection, project: Path) -> None:
    """Best-effort non-interactive CLI read for project name; leave None on any failure."""
    cli = shutil.which(_VERCEL)
    if cli is None:
        return
    try:
        result = subprocess.run(
            [cli, *_ARGS_PROJECT_LS],
            cwd=str(project),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return
    if result.returncode != 0:
        return
    name = _parse_cli_project_name(result.stdout or "", section.project_id)
    if name is not None:
        section.project_name = name


def _parse_cli_project_name(output: str, project_id: str | None) -> str | None:
    """Pick the project's human name from `vercel project ls --json`, if discoverable."""
    payload = _parse_json(output)
    entries: Any = payload
    if isinstance(payload, dict):
        entries = payload.get("projects") or payload.get("data")
    if not isinstance(entries, list):
        return None
    fallback: str | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _as_str(entry.get("name"))
        if name is None:
            continue
        if project_id is not None and entry.get("id") == project_id:
            return name
        if fallback is None:
            fallback = name
    return fallback


def _enrich(section: VercelSection, project_id: str, org_id: str | None) -> None:
    """Populate token-enriched fields in place; degrade per-call, never raise."""
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        section.enrich_state = AvailabilityState.TOKEN_MISSING
        section.enrich_hint = _HINT_TOKEN_MISSING
        return

    status, payload = _api_get(
        _team_query(_PATH_PROJECT.format(project_id=project_id), org_id), token
    )
    if status in (401, 403):
        section.enrich_state = AvailabilityState.TOKEN_REJECTED
        section.enrich_hint = _HINT_TOKEN_REJECTED
        return
    if status == 0:
        section.enrich_state = AvailabilityState.TIMEOUT
        section.enrich_hint = _HINT_TIMEOUT
        return

    _apply_project_fields(section, payload)
    _apply_latest_deployment(section, project_id, org_id, token)
    team_slug = _apply_team(section, org_id, token)
    if org_id is not None:
        _apply_team_members(section, org_id, token)
    _apply_dashboard_url(section, team_slug)
    section.enrich_state = AvailabilityState.OK


def _apply_project_fields(section: VercelSection, payload: Any) -> None:
    """Set project name + latest deployment + region from the project payload."""
    if not isinstance(payload, dict):
        return
    section.project_name = _as_str(payload.get("name")) or section.project_name
    deployments = payload.get("latestDeployments")
    if isinstance(deployments, list) and deployments:
        _apply_deployment_entry(section, deployments[0])


def _apply_latest_deployment(
    section: VercelSection, project_id: str, org_id: str | None, token: str
) -> None:
    """Fill latest deployment status/url from the deployments endpoint if not already set."""
    if section.latest_deployment_status is not None:
        return
    path = _team_query(_PATH_DEPLOYMENTS.format(project_id=project_id), org_id)
    status, payload = _api_get(path, token)
    if status != 200:
        return
    deployments: Any = payload
    if isinstance(payload, dict):
        deployments = payload.get("deployments")
    if isinstance(deployments, list) and deployments:
        _apply_deployment_entry(section, deployments[0])


def _apply_deployment_entry(section: VercelSection, entry: Any) -> None:
    if not isinstance(entry, dict):
        return
    section.latest_deployment_status = (
        _as_str(entry.get("readyState") or entry.get("state"))
        or section.latest_deployment_status
    )
    url = entry.get("url")
    if isinstance(url, str) and url:
        section.latest_deployment_url = (
            url if url.startswith("http") else f"https://{url}"
        )


def _apply_team(section: VercelSection, org_id: str | None, token: str) -> str | None:
    """Set team_plan from the team endpoint; return the team slug for the dashboard URL."""
    if org_id is None:
        return None
    status, payload = _api_get(_PATH_TEAM.format(org_id=org_id), token)
    if status != 200 or not isinstance(payload, dict):
        return None
    section.team_plan = _as_str(
        payload.get("billing", {}).get("plan")
        if isinstance(payload.get("billing"), dict)
        else None
    ) or _as_str(payload.get("name"))
    return _as_str(payload.get("slug"))


def _apply_team_members(section: VercelSection, org_id: str, token: str) -> None:
    status, payload = _api_get(_PATH_TEAM_MEMBERS.format(org_id=org_id), token)
    if status != 200:
        return
    entries: Any = payload
    if isinstance(payload, dict):
        entries = payload.get("members")
    if not isinstance(entries, list):
        return
    members: list[ProjectMember] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _as_str(entry.get("name") or entry.get("email") or entry.get("username"))
        if name is None:
            continue
        members.append(ProjectMember(name=name, role=_as_str(entry.get("role"))))
    section.members = members


def _apply_dashboard_url(section: VercelSection, team_slug: str | None) -> None:
    if team_slug and section.project_name:
        section.dashboard_url = f"{_DASHBOARD_BASE}/{team_slug}/{section.project_name}"


def _team_query(path: str, org_id: str | None) -> str:
    """Append `teamId=<org_id>` to a path, respecting any existing query string."""
    if org_id is None:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}teamId={org_id}"


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
