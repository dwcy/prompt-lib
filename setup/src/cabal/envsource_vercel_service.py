# -*- coding: utf-8 -*-
"""Vercel collector for the environment browser — all Vercel REST I/O lives here.

REST with `VERCEL_TOKEN` is the primary path, matching `dashboard_vercel_service.py`: the CLI
is frequently absent and adds nothing this needs (research R7). Entries Vercel types
`sensitive` are `never` retrievable — the platform does not return them at any permission
level (FR-020); everything else is `permission_gated`, since the decrypt call can still be
refused. Read-only throughout (FR-023) — GET only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cabal.dashboard_links import find_vercel_link
from cabal.models.envsources import (
    AvailabilityState,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
)

SOURCE_ID = "vercel"
LABEL = "Vercel"

_TOKEN_ENV = "VERCEL_TOKEN"
_API_BASE = "https://api.vercel.com"
_PATH_ENVS = "/v9/projects/{project_id}/env"
_PATH_ENV_VALUE = "/v9/projects/{project_id}/env/{env_id}"
_TIMEOUT = 10

SENSITIVE_TYPE = "sensitive"
REASON_SENSITIVE_NEVER = "Vercel never returns the value of a variable marked sensitive"
REASON_ENCRYPTED_GATED = "reading this value requires a token with access to the project"

_HINT_TOKEN_MISSING = f"no Vercel credential — set {_TOKEN_ENV} to list this project's variables"
_HINT_TOKEN_REJECTED = "the Vercel token was rejected — it may be expired or scoped elsewhere"
_HINT_TIMEOUT = f"the Vercel API did not answer within {_TIMEOUT}s"
_HINT_FAILED = "Vercel returned HTTP {status}"

_UNTARGETED = "all targets"


def collect_vercel(project: Path) -> list[VariableSource]:
    """Environment variable names grouped by deployment target; never raises."""
    project_id, org_id = find_vercel_link(project)
    if project_id is None:
        return []
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        return [_source(AvailabilityState.DEGRADED, _HINT_TOKEN_MISSING)]

    status, payload = _api_get(_team_query(_PATH_ENVS.format(project_id=project_id), org_id), token)
    hint = _hint_for(status)
    if hint is not None:
        return [_source(AvailabilityState.DEGRADED, hint)]

    containers = _containers(payload)
    if not containers:
        return [_source(AvailabilityState.EMPTY, None)]
    return [_source(AvailabilityState.OK, None, containers)]


def reveal_vercel(project: Path, name: str, entry_type: str | None):
    """Decrypt one non-sensitive variable. A `sensitive` entry never reaches this function."""
    if (entry_type or "").lower() == SENSITIVE_TYPE:
        return None, REASON_SENSITIVE_NEVER
    project_id, org_id = find_vercel_link(project)
    if project_id is None:
        return None, "this project has no linked Vercel project"
    token = os.environ.get(_TOKEN_ENV)
    if not token:
        return None, _HINT_TOKEN_MISSING

    status, payload = _api_get(
        _team_query(_PATH_ENVS.format(project_id=project_id) + "?decrypt=true", org_id), token
    )
    hint = _hint_for(status)
    if hint is not None:
        return None, hint
    for item in _envs(payload):
        if item.get("key") == name:
            value = item.get("value")
            return (str(value) if value is not None else ""), None
    return None, "that variable is no longer present on the Vercel project"


def _containers(payload) -> list[VariableContainer]:
    grouped: dict[str, list[VariableEntry]] = {}
    for item in _envs(payload):
        name = item.get("key")
        if not isinstance(name, str) or not name:
            continue
        entry_type = item.get("type") if isinstance(item.get("type"), str) else None
        is_sensitive = (entry_type or "").lower() == SENSITIVE_TYPE
        for target in _targets(item):
            container_id = f"{SOURCE_ID}:{target}"
            grouped.setdefault(target, []).append(
                VariableEntry(
                    name=name,
                    source_id=SOURCE_ID,
                    container_id=container_id,
                    target=target,
                    entry_type=entry_type,
                    updated_at=_iso_ms(item.get("updatedAt")),
                    retrievability=Retrievability.NEVER if is_sensitive else Retrievability.PERMISSION_GATED,
                    retrievability_reason=(
                        REASON_SENSITIVE_NEVER if is_sensitive else REASON_ENCRYPTED_GATED
                    ),
                )
            )
    return [
        VariableContainer(
            id=f"{SOURCE_ID}:{target}",
            source_id=SOURCE_ID,
            label=target,
            qualifier=LABEL,
            entries=entries,
        )
        for target, entries in sorted(grouped.items())
    ]


def _targets(item) -> list[str]:
    target = item.get("target")
    if isinstance(target, str) and target:
        return [target]
    if isinstance(target, list):
        named = [str(value) for value in target if isinstance(value, str) and value]
        if named:
            return named
    return [_UNTARGETED]


def _envs(payload) -> list[dict]:
    if isinstance(payload, dict):
        items = payload.get("envs")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _iso_ms(value) -> str | None:
    """Vercel reports epoch milliseconds; keep it a string rather than inventing a timezone."""
    if isinstance(value, (int, float)):
        return str(int(value))
    return value if isinstance(value, str) else None


def _hint_for(status: int) -> str | None:
    if status == 200:
        return None
    if status == 0:
        return _HINT_TIMEOUT
    if status in (401, 403):
        return _HINT_TOKEN_REJECTED
    return _HINT_FAILED.format(status=status)


def _source(
    state: AvailabilityState, hint: str | None, containers: list[VariableContainer] | None = None
) -> VariableSource:
    return VariableSource(
        id=SOURCE_ID,
        kind=SourceKind.VERCEL,
        label=LABEL,
        state=state,
        hint=hint,
        outside_repository=True,
        containers=containers or [],
    )


def _team_query(path: str, org_id: str | None) -> str:
    if not org_id:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}teamId={urllib.parse.quote(org_id)}"


def _api_get(path: str, token: str) -> tuple[int, object]:
    """Return (http_status, decoded body); status 0 means the call never completed."""
    request = urllib.request.Request(
        _API_BASE + path,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return 0, None
