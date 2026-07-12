# -*- coding: utf-8 -*-
"""Persistence and journaling of the ~/.claude/.cabal install manifest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from cabal import _paths

SCHEMA_VERSION = 1
MANIFEST_NAME = "install-manifest.json"
HISTORY_DIRNAME = "history"
HISTORY_KEEP = 10

Action = Literal["created", "updated", "unchanged"]
SourceMode = Literal["source", "wheel", "frozen"]
Status = Literal["in_progress", "complete"]

_ACTIONS: tuple[Action, ...] = ("created", "updated", "unchanged")
_SOURCE_MODES: tuple[SourceMode, ...] = ("source", "wheel", "frozen")
_STATUSES: tuple[Status, ...] = ("in_progress", "complete")


class ManifestError(Exception):
    """An on-disk manifest carries file entries that must not be trusted."""


@dataclass(frozen=True)
class ManagedFile:
    component: str
    rel: str
    sha256: str
    action: Action
    backup: str | None = None


@dataclass
class InstallManifest:
    tool_version: str
    source_mode: SourceMode
    applied_at: str
    status: Status
    components: list[str]
    backup_dir: str | None
    files: list[ManagedFile]
    schema_version: int = SCHEMA_VERSION


def manifest_dir() -> Path:
    return _paths.TARGET / ".cabal"


def manifest_path() -> Path:
    return manifest_dir() / MANIFEST_NAME


def history_dir() -> Path:
    return manifest_dir() / HISTORY_DIRNAME


def current_source_mode() -> SourceMode:
    if _paths.IS_FROZEN:
        return "frozen"
    if _paths.IS_INSTALLED:
        return "wheel"
    return "source"


def sha256_file(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _validate_rel(rel: str) -> None:
    win = PureWindowsPath(rel)
    if (
        win.is_absolute()
        or win.drive
        or win.root
        or PurePosixPath(rel).is_absolute()
        or ".." in win.parts
    ):
        raise ManifestError(f"Unsafe manifest file path (absolute or traversal): {rel!r}")


def _managed_file_from(entry: dict[str, object]) -> ManagedFile:
    rel = str(entry["rel"])
    _validate_rel(rel)
    action = entry["action"]
    if action not in _ACTIONS:
        raise ValueError(f"Unknown action: {action!r}")
    backup = entry.get("backup")
    return ManagedFile(
        component=str(entry["component"]),
        rel=rel,
        sha256=str(entry["sha256"]),
        action=action,
        backup=str(backup) if backup is not None else None,
    )


def load_manifest() -> InstallManifest | None:
    """Read the on-disk manifest; None when missing, unreadable, or unknown schema.

    Malformed JSON and a ``schema_version`` other than :data:`SCHEMA_VERSION` are
    treated as "no manifest" (legacy fallback per data-model.md). A structurally
    valid manifest whose file entries contain absolute or ``..`` paths raises
    :class:`ManifestError` instead: a tampered record must halt doctor/uninstall,
    not silently degrade to the legacy path.
    """
    try:
        data = json.loads(manifest_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return None
    try:
        source_mode = data["source_mode"]
        status = data["status"]
        if source_mode not in _SOURCE_MODES or status not in _STATUSES:
            return None
        files_raw = data.get("files", [])
        if not isinstance(files_raw, list):
            return None
        files = [_managed_file_from(entry) for entry in files_raw]
        backup_dir = data.get("backup_dir")
        return InstallManifest(
            tool_version=str(data["tool_version"]),
            source_mode=source_mode,
            applied_at=str(data["applied_at"]),
            status=status,
            components=[str(c) for c in data.get("components", [])],
            backup_dir=str(backup_dir) if backup_dir is not None else None,
            files=files,
        )
    except (KeyError, TypeError, ValueError):
        return None


def save_manifest(manifest: InstallManifest) -> None:
    """Write the manifest as UTF-8 JSON via a same-directory temp file + replace."""
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    tmp.replace(path)


def _history_name(applied_at: str) -> str:
    try:
        ts = datetime.fromisoformat(applied_at)
    except ValueError:
        ts = datetime.now(UTC)
    return ts.strftime("%Y%m%d-%H%M%S") + ".json"


def _rotate_previous() -> None:
    path = manifest_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict) or data.get("status") != "complete":
        return
    hist = history_dir()
    hist.mkdir(parents=True, exist_ok=True)
    name = _history_name(str(data.get("applied_at", "")))
    dest = hist / name
    counter = 1
    while dest.exists():
        dest = hist / f"{Path(name).stem}-{counter}.json"
        counter += 1
    path.replace(dest)


def _prune_history(keep: int = HISTORY_KEEP) -> None:
    """Keep the newest `keep` snapshots, oldest first pruned.

    Sorts by filename rather than filesystem mtime: history filenames are
    ``%Y%m%d-%H%M%S.json`` (derived from ``applied_at``), which sorts
    chronologically and deterministically. Consecutive applies within the
    same apply session can land in the same mtime tick on some filesystems,
    which would otherwise make pruning order unstable.
    """
    hist = history_dir()
    if not hist.is_dir():
        return
    snapshots = sorted(hist.glob("*.json"), key=lambda p: p.name, reverse=True)
    for old in snapshots[keep:]:
        old.unlink(missing_ok=True)


def begin_apply(manifest: InstallManifest) -> None:
    """Journal the start of an apply: rotate the previous complete manifest into
    history, prune history to the newest :data:`HISTORY_KEEP`, then persist this
    manifest with status ``in_progress``."""
    _rotate_previous()
    _prune_history()
    manifest.status = "in_progress"
    save_manifest(manifest)


def complete_apply(manifest: InstallManifest) -> None:
    """Flip the journal to ``complete`` and persist — the last step of an apply."""
    manifest.status = "complete"
    save_manifest(manifest)


def detect_interrupted() -> InstallManifest | None:
    """The on-disk manifest iff a previous apply died mid-write (status in_progress)."""
    manifest = load_manifest()
    if manifest is not None and manifest.status == "in_progress":
        return manifest
    return None


def restore_latest_history() -> bool:
    """Move the newest history snapshot back to the live manifest path.

    Rollback support: once an interrupted manifest has been discarded, the
    previous complete manifest (rotated into history by :func:`begin_apply`)
    becomes current again. Returns False when no history exists — the deploy
    target is then in its pre-install state (no manifest at all).
    """
    hist = history_dir()
    snapshots = (
        sorted(hist.glob("*.json"), key=lambda p: p.name, reverse=True)
        if hist.is_dir()
        else []
    )
    if not snapshots:
        return False
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshots[0].replace(path)
    return True
