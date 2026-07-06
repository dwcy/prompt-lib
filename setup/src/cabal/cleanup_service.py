# -*- coding: utf-8 -*-
"""Backup-first selective removal of stale ~/.claude extras, plus their restore.

An "extra" is a file present under a component's destination in ~/.claude that no
longer exists in the repo source (computed by `diff_apply.find_extras`). This
module classifies extras, backs selected ones up (verified) before deleting, and
restores them from a cleanup backup. It performs no recursive directory sweeps —
every destructive call operates on the explicit path list it is handed.
"""

from __future__ import annotations

import filecmp
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

from cabal._paths import TARGET
from cabal.components import COMPONENTS
from cabal.diff_apply import find_extras

Classification = Literal["stale", "unknown"]

CLASS_STALE: Classification = "stale"
CLASS_UNKNOWN: Classification = "unknown"

CLEANUP_BACKUP_DIRNAME = ".cleanup-backups"
MANIFEST_NAME = "manifest.json"

_STALE_SKILL_REASON = (
    "Flat skills/*.md — Claude Code only loads directory-style skills/<name>/SKILL.md"
)
_UNKNOWN_REASON = "Not from this repo — may be user-authored; review before removing"


@dataclass(frozen=True)
class ExtraFile:
    component_key: str
    component_label: str
    rel: Path
    path: Path
    classification: Classification
    reason: str


@dataclass
class CleanupResult:
    backup_dir: Path | None = None
    backed_up: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    errors: dict[Path, str] = field(default_factory=dict)


@dataclass
class RestoreResult:
    backup_dir: Path
    restored: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    errors: dict[Path, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    timestamp: str
    entry_count: int
    total_bytes: int


def classify_extra(component_key: str, rel: Path) -> tuple[Classification, str]:
    """Classify one extra as provably dead config ("stale") or possibly user-authored.

    Only flat ``*.md`` files sitting directly under ``skills/`` are stale — Claude
    Code never loads them (it expects ``skills/<name>/SKILL.md``). Everything else
    defaults to "unknown" so a user's own agents, plugins, or backups are never
    marked for deletion by default.
    """
    if component_key == "skills" and rel.parent == Path(".") and rel.suffix == ".md":
        return CLASS_STALE, _STALE_SKILL_REASON
    return CLASS_UNKNOWN, _UNKNOWN_REASON


def collect_extras() -> list[ExtraFile]:
    """All target-only extras across every directory component, classified."""
    out: list[ExtraFile] = []
    for comp in COMPONENTS:
        if comp.type == "file":
            continue
        for rel in find_extras(comp):
            classification, reason = classify_extra(comp.key, rel)
            out.append(
                ExtraFile(
                    component_key=comp.key,
                    component_label=comp.label,
                    rel=rel,
                    path=comp.dst_path / rel,
                    classification=classification,
                    reason=reason,
                )
            )
    return out


def group_by_component(
    extras: Sequence[ExtraFile],
) -> list[tuple[str, list[ExtraFile]]]:
    """Group extras by component label, preserving COMPONENTS order."""
    order = {comp.key: i for i, comp in enumerate(COMPONENTS)}
    buckets: dict[str, list[ExtraFile]] = {}
    labels: dict[str, str] = {}
    for ex in extras:
        buckets.setdefault(ex.component_key, []).append(ex)
        labels[ex.component_key] = ex.component_label
    keys = sorted(buckets, key=lambda k: order.get(k, len(order)))
    return [
        (labels[k], sorted(buckets[k], key=lambda e: e.rel.as_posix())) for k in keys
    ]


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def backup_and_remove(paths: Sequence[Path], target: Path = TARGET) -> CleanupResult:
    """Copy each selected file into a timestamped cleanup backup, verify it, then delete.

    No original is deleted until its backup exists and byte-matches the source, and
    the manifest has been written. Paths outside ``target`` are refused. Returns a
    result carrying the backup folder, what was backed up / deleted, and per-file
    errors.
    """
    result = CleanupResult()
    if not paths:
        return result

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = target / CLEANUP_BACKUP_DIRNAME / ts

    verified: list[tuple[Path, Path]] = []  # (original, backup copy)
    entries: list[dict[str, object]] = []
    for original in paths:
        if not _within(original, target):
            result.errors[original] = "Refused — path is outside the deploy target"
            continue
        if not original.is_file():
            result.errors[original] = "Not a file (skipped)"
            continue
        rel = original.resolve().relative_to(target.resolve())
        backup_path = backup_root / rel
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, backup_path)
        except OSError as exc:
            result.errors[original] = f"Backup failed: {exc}"
            continue
        if not backup_path.is_file() or not filecmp.cmp(
            original, backup_path, shallow=False
        ):
            result.errors[original] = "Backup verification failed — original kept"
            continue
        verified.append((original, backup_path))
        entries.append(
            {"relative_path": rel.as_posix(), "size": original.stat().st_size}
        )

    if not verified:
        _remove_empty_backup(backup_root, ts)
        return result

    manifest = {"timestamp": ts, "target": str(target), "entries": entries}
    try:
        (backup_root / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        for original, _backup in verified:
            result.errors[original] = f"Manifest write failed, original kept: {exc}"
        return result

    result.backup_dir = backup_root
    for original, _backup in verified:
        result.backed_up.append(original)
        try:
            original.unlink()
            result.deleted.append(original)
        except OSError as exc:
            result.errors[original] = f"Backed up but delete failed: {exc}"
    return result


def _remove_empty_backup(backup_root: Path, ts: str) -> None:
    try:
        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)
        parent = backup_root.parent
        if parent.name == CLEANUP_BACKUP_DIRNAME and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def list_cleanup_backups(target: Path = TARGET) -> list[BackupInfo]:
    """Cleanup backups newest-first, each summarised from its manifest."""
    root = target / CLEANUP_BACKUP_DIRNAME
    if not root.is_dir():
        return []
    infos: list[BackupInfo] = []
    for sub in root.iterdir():
        manifest_path = sub / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        entries = data.get("entries", [])
        total = sum(int(e.get("size", 0)) for e in entries)
        infos.append(
            BackupInfo(
                path=sub,
                timestamp=str(data.get("timestamp", sub.name)),
                entry_count=len(entries),
                total_bytes=total,
            )
        )
    infos.sort(key=lambda b: b.timestamp, reverse=True)
    return infos


def restore_cleanup(backup_dir: Path, target: Path = TARGET) -> RestoreResult:
    """Copy files from a cleanup backup back to ``target`` per its manifest.

    A destination that already exists and is newer than its backup copy is skipped
    (never silently overwritten) and reported. Other files are restored, recreating
    any missing parent directories.
    """
    result = RestoreResult(backup_dir=backup_dir)
    manifest_path = backup_dir / MANIFEST_NAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.errors[manifest_path] = f"Cannot read manifest: {exc}"
        return result

    for entry in data.get("entries", []):
        rel = Path(str(entry.get("relative_path", "")))
        if not rel.parts:
            continue
        src = backup_dir / rel
        dst = target / rel
        if not src.is_file():
            result.errors[dst] = "Missing from backup"
            continue
        if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
            result.skipped.append((dst, "Existing file is newer — left untouched"))
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            result.restored.append(dst)
        except OSError as exc:
            result.errors[dst] = f"Restore failed: {exc}"
    return result
