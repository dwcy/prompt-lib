# -*- coding: utf-8 -*-
"""Shared wizard/headless apply orchestration: plan, backup, deploy, manifest journal."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cabal
from cabal import _paths, install_manifest
from cabal.components import COMPONENTS, FileStatus
from cabal.diff_apply import apply_statuses, diff_component
from cabal.install_manifest import InstallManifest, ManagedFile
from cabal.settings_helpers import _effective_settings_text, _is_settings_json

REQUIRED_COMPONENT_KEYS: tuple[str, ...] = ("settings", "claude_md")
BACKUP_DIRNAME = "backups"
BACKUP_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

_STATE_TO_ACTION: dict[str, install_manifest.Action] = {
    "NEW": "created",
    "CHANGED": "updated",
    "UNCHANGED": "unchanged",
}


class UnknownComponentError(ValueError):
    """A requested component key is not in the component registry."""


@dataclass(frozen=True)
class PlannedFile:
    component: str
    status: FileStatus


@dataclass
class ApplyOutcome:
    components: list[str]
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    backed_up: int = 0
    skipped: int = 0
    backup_dir: Path | None = None
    manifest_file: Path | None = None
    files: list[ManagedFile] = field(default_factory=list)


def resolve_component_keys(requested: Sequence[str] | None) -> list[str]:
    """Registry-ordered keys: all when None, else required core + the requested set."""
    known = [c.key for c in COMPONENTS]
    if requested is None:
        return known
    unknown = sorted(set(requested) - set(known))
    if unknown:
        raise UnknownComponentError(
            f"unknown component key(s): {', '.join(unknown)} "
            f"(known: {', '.join(known)})"
        )
    wanted = set(requested) | set(REQUIRED_COMPONENT_KEYS)
    return [k for k in known if k in wanted]


def build_plan(
    keys: Sequence[str],
    selected: Mapping[str, Collection[str]] | None = None,
) -> list[PlannedFile]:
    """Per-file deploy statuses across the requested components.

    ``selected`` optionally narrows each component to an explicit set of relative
    paths (the wizard's per-file toggles); None means every source file.
    """
    wanted = set(keys)
    plan: list[PlannedFile] = []
    for comp in COMPONENTS:
        if comp.key not in wanted or not comp.src_path.exists():
            continue
        statuses = diff_component(comp)
        if selected is not None:
            allow = {Path(rel).as_posix() for rel in selected.get(comp.key, ())}
            statuses = [s for s in statuses if Path(s.rel).as_posix() in allow]
        plan.extend(PlannedFile(comp.key, s) for s in statuses)
    return plan


def source_sha(src: Path) -> str:
    """Hash of the content an apply would deploy from this source file.

    settings.json deploys as its effective (MCP-stripped, OS-translated) text,
    so its hash comes from that text rather than the raw file bytes.
    """
    if _is_settings_json(src):
        text = _effective_settings_text(src)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    return install_manifest.sha256_file(src)


def _planned_sha(status: FileStatus) -> str:
    """Hash a planned file will carry once deployed — its source content hash."""
    return source_sha(status.src)


def _create_backups(
    overwrites: Sequence[PlannedFile],
) -> tuple[Path | None, dict[tuple[str, str], str]]:
    """Copy every file about to be overwritten into one timestamped backup dir.

    Returns the backup root (None when nothing gets overwritten) and a map of
    (component, rel) → backup path relative to that root.
    """
    if not overwrites:
        return None, {}
    ts = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
    root = install_manifest.manifest_dir() / BACKUP_DIRNAME / ts
    refs: dict[tuple[str, str], str] = {}
    for pf in overwrites:
        backup_rel = pf.status.dst.relative_to(_paths.TARGET).as_posix()
        dest = root / backup_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pf.status.dst, dest)
        refs[(pf.component, Path(pf.status.rel).as_posix())] = backup_rel
    return root, refs


def _manifest_entries(
    plan: Sequence[PlannedFile],
    refs: Mapping[tuple[str, str], str],
    *,
    deployed: bool,
) -> list[ManagedFile]:
    entries: list[ManagedFile] = []
    for pf in plan:
        rel = Path(pf.status.rel).as_posix()
        sha = (
            install_manifest.sha256_file(pf.status.dst)
            if deployed
            else _planned_sha(pf.status)
        )
        entries.append(
            ManagedFile(
                component=pf.component,
                rel=rel,
                sha256=sha,
                action=_STATE_TO_ACTION[pf.status.state],
                backup=refs.get((pf.component, rel)),
            )
        )
    return entries


def apply_plan(plan: Sequence[PlannedFile], *, dry_run: bool = False) -> ApplyOutcome:
    """Deploy a plan: backups first, manifest journaled in_progress → complete.

    Order per specs/016-install-wizard: back up every overwrite target, journal
    the planned inventory as ``in_progress`` before the first write, copy files
    (settings.json via its effective text), then persist final entries hashed
    from the deployed content and flip the manifest to ``complete``. A dry run
    only computes counts and writes nothing.
    """
    plan = list(plan)
    outcome = ApplyOutcome(
        components=list(dict.fromkeys(pf.component for pf in plan)),
        created=sum(1 for pf in plan if pf.status.state == "NEW"),
        updated=sum(1 for pf in plan if pf.status.state == "CHANGED"),
        unchanged=sum(1 for pf in plan if pf.status.state == "UNCHANGED"),
        manifest_file=install_manifest.manifest_path(),
    )
    if dry_run:
        return outcome
    overwrites = [
        pf for pf in plan if pf.status.state == "CHANGED" and pf.status.dst.exists()
    ]
    backup_root, refs = _create_backups(overwrites)
    outcome.backup_dir = backup_root
    outcome.backed_up = len(refs)
    manifest = InstallManifest(
        tool_version=cabal.__version__,
        source_mode=install_manifest.current_source_mode(),
        applied_at=datetime.now(UTC).isoformat(),
        status="in_progress",
        components=outcome.components,
        backup_dir=str(backup_root) if backup_root is not None else None,
        files=_manifest_entries(plan, refs, deployed=False),
    )
    install_manifest.begin_apply(manifest)
    apply_statuses([pf.status for pf in plan])
    manifest.files = _manifest_entries(plan, refs, deployed=True)
    outcome.files = manifest.files
    install_manifest.complete_apply(manifest)
    return outcome


def apply_components(keys: Sequence[str], *, dry_run: bool = False) -> ApplyOutcome:
    """Plan and apply whole components — the headless entry into the shared path."""
    return apply_plan(build_plan(keys), dry_run=dry_run)


def outcome_summary(outcome: ApplyOutcome) -> list[str]:
    """Plain-text post-apply verification lines shared by wizard and headless."""
    lines = [
        f"{outcome.created} created, {outcome.updated} updated, "
        f"{outcome.unchanged} unchanged, {outcome.backed_up} backed up"
    ]
    if outcome.backup_dir is not None:
        lines.append(f"Backups → {outcome.backup_dir}")
    lines.append(f"Manifest → {outcome.manifest_file}")
    return lines
