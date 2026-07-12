# -*- coding: utf-8 -*-
"""Interrupted-apply recovery: resume via the shared apply path, or roll back backups."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cabal import install_manifest
from cabal.apply_service import ApplyOutcome, apply_components
from cabal.components import COMPONENTS
from cabal.install_manifest import InstallManifest, ManagedFile


class NoInterruptedApplyError(RuntimeError):
    """Resume/rollback was requested but no in_progress manifest exists."""


@dataclass
class RollbackResult:
    restored: int = 0
    deleted: int = 0
    skipped: list[str] = field(default_factory=list)
    previous_manifest_restored: bool = False


def interrupted_state() -> InstallManifest | None:
    """The in_progress manifest left by an apply that died mid-write, if any."""
    return install_manifest.detect_interrupted()


def resume_interrupted() -> ApplyOutcome:
    """Re-apply the interrupted manifest's component set through the shared path.

    The apply is diff-driven and content-compared, so re-running it is
    idempotent (research.md R4); completing it flips the journal to
    ``complete``, clearing the interrupted state even when every file already
    matches the source.
    """
    manifest = install_manifest.detect_interrupted()
    if manifest is None:
        raise NoInterruptedApplyError("no in_progress manifest to resume")
    return apply_components(manifest.components)


def _destination_for(entry: ManagedFile) -> Path | None:
    comp = next((c for c in COMPONENTS if c.key == entry.component), None)
    if comp is None:
        return None
    return comp.dst_path if comp.type == "file" else comp.dst_path / entry.rel


def _restore_backups(manifest: InstallManifest, result: RollbackResult) -> None:
    backup_root = (
        Path(manifest.backup_dir) if manifest.backup_dir is not None else None
    )
    for entry in manifest.files:
        if entry.backup is None:
            continue
        dest = _destination_for(entry)
        source = backup_root / entry.backup if backup_root is not None else None
        if dest is None or source is None or not source.is_file():
            result.skipped.append(f"{entry.rel} (backup missing)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        result.restored += 1


def _delete_created(manifest: InstallManifest, result: RollbackResult) -> None:
    for entry in manifest.files:
        if entry.action != "created":
            continue
        dest = _destination_for(entry)
        if dest is None:
            result.skipped.append(f"{entry.rel} (unknown component)")
            continue
        if not dest.is_file():
            continue  # crash happened before this file was written
        if install_manifest.sha256_file(dest) != entry.sha256:
            result.skipped.append(f"{entry.rel} (user-modified, kept)")
            continue
        dest.unlink()
        result.deleted += 1


def rollback_interrupted() -> RollbackResult:
    """Undo an interrupted apply and return the deploy target to its pre-apply state.

    Restores every recorded backup to its destination, deletes files the
    interrupted manifest recorded as ``created`` — only when their current
    content hash still matches the manifest's sha256, so user-modified content
    is never deleted (skipped and reported instead) — then removes the
    in_progress manifest and restores the previous complete manifest from
    history when one exists.
    """
    manifest = install_manifest.detect_interrupted()
    if manifest is None:
        raise NoInterruptedApplyError("no in_progress manifest to roll back")
    result = RollbackResult()
    _restore_backups(manifest, result)
    _delete_created(manifest, result)
    install_manifest.manifest_path().unlink(missing_ok=True)
    result.previous_manifest_restored = install_manifest.restore_latest_history()
    return result


def rollback_summary(result: RollbackResult) -> list[str]:
    """Plain-text rollback report lines shared by wizard and headless surfaces."""
    lines = [
        f"{result.restored} restored from backup, "
        f"{result.deleted} created file(s) removed"
    ]
    if result.skipped:
        lines.append("Skipped: " + ", ".join(result.skipped))
    lines.append(
        "Previous install manifest restored from history."
        if result.previous_manifest_restored
        else "No previous manifest — deploy target is back to its pre-install state."
    )
    return lines
