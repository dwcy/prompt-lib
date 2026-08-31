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


# -- Azure link ladder (020-env-variable-sources FR-030) -------------------
# Four signals, first match wins. Pure detection only: `machine_default` is resolved by
# the Azure collector, because it needs `az account show` and this module stays I/O-free.

AZD_MARKER_FILE = "azure.yaml"
AZD_MARKER_DIR = ".azure"
IAC_DIR = "infra"
_IAC_SUFFIXES = (".bicep", ".tf")


def find_azd_link(project: Path) -> str | None:
    """Return the Azure Developer CLI signal describing this project, or None."""
    if (project / AZD_MARKER_FILE).is_file():
        return AZD_MARKER_FILE
    azure_dir = project / AZD_MARKER_DIR
    if not azure_dir.is_dir():
        return None
    environments = sorted(child.name for child in _safe_iterdir(azure_dir) if child.is_dir())
    if environments:
        return f"{AZD_MARKER_DIR}/ ({', '.join(environments)})"
    return f"{AZD_MARKER_DIR}/"


def find_azd_environment_name(project: Path) -> str | None:
    """Name the azd environment when `.azure/<env>/.env` identifies exactly one."""
    azure_dir = project / AZD_MARKER_DIR
    if not azure_dir.is_dir():
        return None
    named = [
        child.name
        for child in _safe_iterdir(azure_dir)
        if child.is_dir() and (child / ".env").is_file()
    ]
    return named[0] if len(named) == 1 else None


def find_iac_link(project: Path) -> str | None:
    """Return the infrastructure-as-code signal under `infra/`, or None."""
    infra = project / IAC_DIR
    if not infra.is_dir():
        return None
    for child in sorted(_safe_iterdir(infra), key=lambda item: item.name.lower()):
        if child.is_file() and child.suffix.lower() in _IAC_SUFFIXES:
            return f"{IAC_DIR}/{child.name}"
    return None


def _safe_iterdir(directory: Path) -> list[Path]:
    try:
        return list(directory.iterdir())
    except OSError:
        return []
