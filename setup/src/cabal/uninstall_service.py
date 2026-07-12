# -*- coding: utf-8 -*-
"""Manifest-driven uninstall: plan managed-file removal, execute it, restore backups.

Removal is an explicit path list derived from the latest complete install
manifest (or, gated behind ``legacy=True``, from the component registry when no
manifest exists) — never a recursive directory sweep. Files whose content
matches neither the manifest record nor the bundled source are kept and
reported. The ``~/.claude/.cabal`` state dir is deleted last, manifest file
last of all, so an interrupted uninstall can always be re-run.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cabal import _paths, install_manifest
from cabal.apply_service import source_sha
from cabal.components import COMPONENTS
from cabal.install_manifest import InstallManifest
from cabal.manifest_doctor import classify_files

_REASON_USER_MODIFIED = (
    "user-modified — matches neither the manifest record nor the bundled source"
)
_REASON_UNREGISTERED = "component no longer in the registry — resolve by hand"
_REASON_MISSING = "already missing from disk"
_REASON_LEGACY_MATCH = "needs review — no manifest; content matches the bundled source"
_REASON_LEGACY_DIFFERS = (
    "needs review — no manifest; content differs from the bundled source"
)


class NoManifestError(RuntimeError):
    """No complete install manifest exists and the legacy fallback was not requested."""


class InterruptedInstallError(RuntimeError):
    """An in_progress manifest blocks uninstall until it is resumed or rolled back."""


@dataclass(frozen=True)
class UninstallItem:
    """One planned file: destination path, why it is (not) removed, its backup ref."""

    component: str
    rel: str
    path: Path | None  # None when the component left the registry (unresolvable)
    reason: str = ""
    backup: str | None = None


@dataclass
class UninstallPlan:
    legacy: bool
    manifest: InstallManifest | None
    backup_dir: Path | None = None
    remove: list[UninstallItem] = field(default_factory=list)
    skip: list[UninstallItem] = field(default_factory=list)
    missing: list[UninstallItem] = field(default_factory=list)
    backups: list[UninstallItem] = field(default_factory=list)


@dataclass
class UninstallResult:
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    restore_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state_dir_removed: bool = False


def uninstall_plan(*, legacy: bool = False) -> UninstallPlan:
    """Classify every manifest entry into remove / skip / missing, plus backups.

    A file is removable when its on-disk hash matches the manifest sha256 or
    the current bundled source hash (``manifest_doctor.classify_files`` health
    "ok" / "stale"); anything else is user-modified and kept. Without a
    manifest this raises :class:`NoManifestError` unless ``legacy`` is set, in
    which case the plan comes from the component registry with every entry
    flagged needs-review — only files byte-matching the bundled source land in
    ``remove``. An ``in_progress`` manifest refuses with
    :class:`InterruptedInstallError` — recovery owns that state.
    """
    manifest = install_manifest.load_manifest()
    if manifest is None:
        if not legacy:
            raise NoManifestError(
                "no install manifest found — nothing recorded to uninstall"
            )
        return _legacy_plan()
    if manifest.status == "in_progress":
        raise InterruptedInstallError(
            "a previous apply was interrupted (manifest status: in_progress) — "
            "resume or roll it back first (wizard recovery dialog, "
            "or `cabal apply --yes` to resume)"
        )
    plan = UninstallPlan(
        legacy=False,
        manifest=manifest,
        backup_dir=(
            Path(manifest.backup_dir) if manifest.backup_dir is not None else None
        ),
    )
    covered: set[tuple[str, str]] = set()
    for state in classify_files(manifest):
        entry = state.entry
        covered.add((entry.component, entry.rel))
        if state.health in ("ok", "stale"):
            item = UninstallItem(
                entry.component, entry.rel, state.dest, backup=entry.backup
            )
            plan.remove.append(item)
        elif state.health == "missing":
            item = UninstallItem(
                entry.component,
                entry.rel,
                state.dest,
                reason=_REASON_MISSING,
                backup=entry.backup,
            )
            plan.missing.append(item)
        else:
            item = UninstallItem(
                entry.component,
                entry.rel,
                state.dest,
                reason=_REASON_USER_MODIFIED,
                backup=entry.backup,
            )
            plan.skip.append(item)
        if item.backup is not None and plan.backup_dir is not None:
            plan.backups.append(item)
    for entry in manifest.files:
        if (entry.component, entry.rel) in covered:
            continue
        plan.skip.append(
            UninstallItem(
                entry.component,
                entry.rel,
                None,
                reason=_REASON_UNREGISTERED,
                backup=entry.backup,
            )
        )
    return plan


def _legacy_plan() -> UninstallPlan:
    """No-manifest fallback: registry files present on disk, all needs-review.

    Only files whose deployed content byte-matches the bundled source are
    removable — cabal can prove it deployed those. Everything else is kept.
    """
    plan = UninstallPlan(legacy=True, manifest=None)
    for comp in COMPONENTS:
        for src, rel in comp.list_files():
            dest = comp.dst_path if comp.type == "file" else comp.dst_path / rel
            if not dest.is_file():
                continue
            rel_posix = Path(rel).as_posix()
            if install_manifest.sha256_file(dest) == source_sha(src):
                plan.remove.append(
                    UninstallItem(comp.key, rel_posix, dest, reason=_REASON_LEGACY_MATCH)
                )
            else:
                plan.skip.append(
                    UninstallItem(
                        comp.key, rel_posix, dest, reason=_REASON_LEGACY_DIFFERS
                    )
                )
    return plan


def _within_target(path: Path) -> bool:
    try:
        path.resolve().relative_to(_paths.TARGET.resolve())
        return True
    except ValueError:
        return False


def uninstall(plan: UninstallPlan, *, restore_backups: bool = False) -> UninstallResult:
    """Delete exactly ``plan.remove``, then optionally restore pre-install backups,
    prune now-empty component directories (rmdir only, never rmtree), and remove
    the ``.cabal`` state dir last.

    Crash-safety: the manifest file is only deleted once every other step
    finished without errors, so an interrupted or partially failed uninstall
    can simply be re-run against the still-present manifest.
    """
    result = UninstallResult(
        skipped=[f"{item.rel} ({item.reason})" for item in plan.skip],
        missing=[item.rel for item in plan.missing],
    )
    for item in plan.remove:
        if item.path is None or not _within_target(item.path):
            result.errors.append(f"{item.rel}: refused — outside the deploy target")
            continue
        try:
            item.path.unlink(missing_ok=True)
            result.removed.append(item.rel)
        except OSError as exc:
            result.errors.append(f"{item.rel}: delete failed: {exc}")
    if restore_backups:
        _restore_preinstall(plan, result)
    _prune_empty_dirs(plan)
    if not result.errors:
        _remove_state_dir(result)
    return result


def _restore_preinstall(plan: UninstallPlan, result: UninstallResult) -> None:
    """Copy manifest-referenced pre-install backups back to their destinations.

    Runs after removal; a destination that still exists (a kept user-modified
    file) is never overwritten — it is reported instead.
    """
    if plan.backup_dir is None:
        return
    for item in plan.backups:
        if item.backup is None:
            continue
        if item.path is None:
            result.restore_skipped.append(f"{item.rel} (destination unresolvable)")
            continue
        source = plan.backup_dir / item.backup
        if not source.is_file():
            result.errors.append(f"{item.rel}: pre-install backup missing: {source}")
            continue
        if item.path.exists():
            result.restore_skipped.append(f"{item.rel} (kept on disk — not overwritten)")
            continue
        try:
            item.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, item.path)
            result.restored.append(item.rel)
        except OSError as exc:
            result.errors.append(f"{item.rel}: restore failed: {exc}")


def _prune_empty_dirs(plan: UninstallPlan) -> None:
    """rmdir every now-empty directory that held a removed file, deepest first.

    ``rmdir`` fails on anything non-empty, so directories still holding user
    files (or freshly restored backups) survive untouched. The deploy target
    root itself is never a candidate.
    """
    target = _paths.TARGET.resolve()
    candidates: set[Path] = set()
    for item in plan.remove:
        if item.path is None:
            continue
        parent = item.path.resolve().parent
        while parent != target and target in parent.parents:
            candidates.add(parent)
            parent = parent.parent
    for directory in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _remove_state_dir(result: UninstallResult) -> None:
    """Delete ``~/.claude/.cabal`` via an explicit file list, manifest file last."""
    root = install_manifest.manifest_dir()
    if not root.is_dir():
        result.state_dir_removed = True
        return
    manifest_file = install_manifest.manifest_path()
    files = [p for p in root.rglob("*") if p.is_file() and p != manifest_file]
    for file in sorted(files):
        try:
            file.unlink()
        except OSError as exc:
            result.errors.append(f"{file}: delete failed: {exc}")
    if result.errors:
        return  # manifest kept — a re-run still has the full record
    manifest_file.unlink(missing_ok=True)
    subdirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for directory in (*subdirs, root):
        try:
            directory.rmdir()
        except OSError:
            pass
    result.state_dir_removed = not root.exists()


def uninstall_summary(result: UninstallResult) -> list[str]:
    """Plain-text uninstall report lines shared by wizard and headless surfaces."""
    lines = [
        f"{len(result.removed)} removed, {len(result.skipped)} kept, "
        f"{len(result.missing)} already missing, "
        f"{len(result.restored)} restored from backup"
    ]
    if result.skipped:
        lines.append("Kept: " + ", ".join(result.skipped))
    if result.restore_skipped:
        lines.append("Not restored: " + ", ".join(result.restore_skipped))
    if result.errors:
        lines.append("Errors: " + "; ".join(result.errors))
    lines.append(
        "State dir ~/.claude/.cabal removed."
        if result.state_dir_removed
        else "State dir ~/.claude/.cabal kept — resolve the errors above and re-run."
    )
    return lines
