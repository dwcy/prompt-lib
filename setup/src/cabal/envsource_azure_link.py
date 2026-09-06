# -*- coding: utf-8 -*-
"""Per-project explicit Azure scope: the one write this feature performs (FR-025).

Local workspace state in the app's own platform data directory, keyed by project path, and
never sent to any provider. Clearing it restores automatic detection (FR-033).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import platformdirs

from cabal.models.envsources import AzureProjectLink, LinkConfidence

STORE_NAME = "azure-project-links.json"
_SCHEMA = "cabal-azure-links.v1"

_REASON = "an Azure scope you recorded for this project"


def store_path() -> Path:
    return Path(platformdirs.user_data_dir("cabal", appauthor=False)) / STORE_NAME


def load_link(project: Path, *, path: Path | None = None) -> AzureProjectLink | None:
    """The scope recorded for `project`, or None when automatic detection should apply."""
    record = _load_all(path or store_path()).get(_key(project))
    if not isinstance(record, dict):
        return None
    subscription = record.get("subscription_id")
    resource_group = record.get("resource_group")
    if not isinstance(subscription, str) or not subscription:
        return None
    return AzureProjectLink(
        subscription_id=subscription,
        resource_group=resource_group if isinstance(resource_group, str) and resource_group else None,
        confidence=LinkConfidence.EXPLICIT,
        reason=_REASON,
        is_explicit=True,
    )


def save_link(
    project: Path,
    subscription_id: str,
    resource_group: str | None,
    *,
    path: Path | None = None,
) -> AzureProjectLink:
    target = path or store_path()
    records = _load_all(target)
    records[_key(project)] = {
        "subscription_id": subscription_id,
        "resource_group": resource_group or None,
    }
    _write_all(target, records)
    return AzureProjectLink(
        subscription_id=subscription_id,
        resource_group=resource_group or None,
        confidence=LinkConfidence.EXPLICIT,
        reason=_REASON,
        is_explicit=True,
    )


def clear_link(project: Path, *, path: Path | None = None) -> bool:
    """Drop the recorded scope; returns whether there was one. Automatic detection resumes."""
    target = path or store_path()
    records = _load_all(target)
    if _key(project) not in records:
        return False
    del records[_key(project)]
    _write_all(target, records)
    return True


def _key(project: Path) -> str:
    try:
        return str(Path(project).resolve())
    except OSError:
        return str(project)


def _load_all(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    links = document.get("links") if isinstance(document, dict) else None
    return dict(links) if isinstance(links, dict) else {}


def _write_all(path: Path, records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"schema": _SCHEMA, "links": records}, indent=2, sort_keys=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload + "\n")
        os.replace(temporary, path)
    except OSError:
        Path(temporary).unlink(missing_ok=True)
        raise
