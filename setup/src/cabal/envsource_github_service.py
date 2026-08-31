# -*- coding: utf-8 -*-
"""GitHub collector for the environment browser — all `gh` subprocess I/O lives here.

Every secret is classified `never` rather than `permission_gated` (FR-019): the REST API
returns secret names and timestamps with no value field at all, by design, so no amount of
permission would produce one. Variables are `readable`. Read-only throughout (FR-023) — the
only verbs issued are GETs through `gh api`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

from cabal.dashboard_links import parse_github_remote
from cabal.models.envsources import (
    AvailabilityState,
    Retrievability,
    SourceKind,
    VariableContainer,
    VariableEntry,
    VariableSource,
)

SOURCE_ID = "github"
LABEL = "GitHub"

_GH = "gh"
_GIT = "git"
_TIMEOUT = 8
_PER_PAGE = "100"

REASON_SECRET_NEVER = "GitHub never returns secret values — the API omits them by design"

_HINT_NO_CLI = "the GitHub CLI (gh) is not installed"
_HINT_NOT_AUTHED = "GitHub sign-in is required — run `gh auth login`"
_HINT_TIMEOUT = "the GitHub CLI did not answer within {timeout}s"
_HINT_FAILED = "GitHub returned: {detail}"


def collect_github(project: Path) -> list[VariableSource]:
    """Repository-level and per-environment variables/secrets; never raises."""
    owner_repo = _owner_repo(project)
    if owner_repo is None:
        return []
    if shutil.which(_GH) is None:
        return [_source(AvailabilityState.DEGRADED, _HINT_NO_CLI)]

    code, payload = _api(f"repos/{owner_repo}/actions/variables?per_page={_PER_PAGE}")
    if code != 0:
        return [_source(AvailabilityState.DEGRADED, _classify(payload))]

    containers = [
        _container("repository", "Repository", _entries(payload, "variables", Retrievability.READABLE))
    ]
    containers.extend(_secret_container(owner_repo, "repository", "Repository"))
    containers.extend(_environment_containers(owner_repo))

    populated = [container for container in containers if container.entries]
    if not populated:
        return [_source(AvailabilityState.EMPTY, None)]
    return [_source(AvailabilityState.OK, None, populated)]


def reveal_github(project: Path, container_id: str, name: str):
    """Fetch one GitHub *variable*; secrets never reach here (data-model rule 8)."""
    owner_repo = _owner_repo(project)
    if owner_repo is None:
        return None, "this project has no GitHub origin"
    scope = _scope_of(container_id)
    path = (
        f"repos/{owner_repo}/actions/variables/{name}"
        if scope is None
        else f"repos/{owner_repo}/environments/{scope}/variables/{name}"
    )
    code, payload = _api(path)
    if code != 0:
        return None, _classify(payload)
    try:
        document = json.loads(payload)
    except ValueError:
        return None, "GitHub returned a response this module could not read"
    value = document.get("value") if isinstance(document, dict) else None
    if not isinstance(value, str):
        return None, "GitHub returned no value for that variable"
    return value, None


def _environment_containers(owner_repo: str) -> list[VariableContainer]:
    code, payload = _api(f"repos/{owner_repo}/environments?per_page={_PER_PAGE}")
    if code != 0:
        return []
    try:
        document = json.loads(payload)
    except ValueError:
        return []
    environments = document.get("environments") if isinstance(document, dict) else None
    if not isinstance(environments, list):
        return []

    containers: list[VariableContainer] = []
    for environment in environments:
        name = environment.get("name") if isinstance(environment, dict) else None
        if not isinstance(name, str) or not name:
            continue
        code, payload = _api(f"repos/{owner_repo}/environments/{name}/variables?per_page={_PER_PAGE}")
        entries = _entries(payload, "variables", Retrievability.READABLE, target=name) if code == 0 else []
        containers.append(_container(f"env:{name}", name, entries))
        containers.extend(_secret_container(owner_repo, f"env:{name}", name, environment=name))
    return containers


def _secret_container(
    owner_repo: str, suffix: str, label: str, *, environment: str | None = None
) -> list[VariableContainer]:
    path = (
        f"repos/{owner_repo}/environments/{environment}/secrets?per_page={_PER_PAGE}"
        if environment is not None
        else f"repos/{owner_repo}/actions/secrets?per_page={_PER_PAGE}"
    )
    code, payload = _api(path)
    if code != 0:
        return []
    entries = _entries(
        payload,
        "secrets",
        Retrievability.NEVER,
        target=environment,
        reason=REASON_SECRET_NEVER,
        entry_type="secret",
    )
    return [_container(f"{suffix}:secrets", f"{label} secrets", entries)] if entries else []


def _entries(
    payload: str,
    field: str,
    retrievability: Retrievability,
    *,
    target: str | None = None,
    reason: str | None = None,
    entry_type: str | None = None,
) -> list[VariableEntry]:
    try:
        document = json.loads(payload)
    except ValueError:
        return []
    items = document.get(field) if isinstance(document, dict) else None
    if not isinstance(items, list):
        return []
    entries: list[VariableEntry] = []
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            continue
        updated = item.get("updated_at") or item.get("created_at")
        entries.append(
            VariableEntry(
                name=name,
                source_id=SOURCE_ID,
                container_id="",
                target=target,
                entry_type=entry_type,
                updated_at=updated if isinstance(updated, str) else None,
                retrievability=retrievability,
                retrievability_reason=reason,
            )
        )
    return entries


def _container(suffix: str, label: str, entries: list[VariableEntry]) -> VariableContainer:
    container_id = f"{SOURCE_ID}:{suffix}"
    return VariableContainer(
        id=container_id,
        source_id=SOURCE_ID,
        label=label,
        qualifier=LABEL,
        entries=[replace(entry, container_id=container_id) for entry in entries],
    )


def _scope_of(container_id: str) -> str | None:
    """The environment a container belongs to, or None for the repository-level scope."""
    suffix = container_id[len(SOURCE_ID) + 1 :] if container_id.startswith(SOURCE_ID + ":") else container_id
    suffix = suffix.removesuffix(":secrets")
    return suffix[len("env:") :] if suffix.startswith("env:") else None


def _source(
    state: AvailabilityState,
    hint: str | None,
    containers: list[VariableContainer] | None = None,
) -> VariableSource:
    return VariableSource(
        id=SOURCE_ID,
        kind=SourceKind.GITHUB,
        label=LABEL,
        state=state,
        hint=hint,
        outside_repository=True,
        containers=containers or [],
    )


def _owner_repo(project: Path) -> str | None:
    git = shutil.which(_GIT)
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, "-C", str(project), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    parsed = parse_github_remote((result.stdout or "").strip())
    return f"{parsed[0]}/{parsed[1]}" if parsed is not None else None


def _api(path: str) -> tuple[int, str]:
    """`gh api <path>` — returns (0, body) or (code, diagnostic text). Never raises.

    Runs the resolved executable: on Windows a CLI shipped as a `.CMD` wrapper cannot be
    launched from the bare name (WinError 2), and `gh` is packaged that way on some installs.
    """
    executable = shutil.which(_GH)
    if executable is None:
        return 1, _HINT_NO_CLI
    try:
        result = subprocess.run(
            [executable, "api", "-H", "Accept: application/vnd.github+json", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 1, _HINT_TIMEOUT.format(timeout=_TIMEOUT)
    except OSError as exc:
        return 1, str(exc)
    if result.returncode != 0:
        return result.returncode, ((result.stderr or result.stdout) or "").strip()
    return 0, result.stdout or ""


def _classify(detail: str) -> str:
    lowered = (detail or "").lower()
    if "did not answer" in lowered:
        return detail
    if "auth" in lowered and ("login" in lowered or "token" in lowered or "credential" in lowered):
        return _HINT_NOT_AUTHED
    if "401" in lowered or "unauthorized" in lowered or "403" in lowered:
        return _HINT_NOT_AUTHED
    return _HINT_FAILED.format(detail=detail.strip() or "an unexplained failure")
