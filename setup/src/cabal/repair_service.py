# -*- coding: utf-8 -*-
"""Targeted repair: re-deploy only manifest-managed files that are missing or stale."""

from __future__ import annotations

from collections.abc import Sequence

from cabal import install_manifest
from cabal.apply_service import ApplyOutcome, apply_plan, build_plan
from cabal.install_manifest import InstallManifest, ManagedFile
from cabal.manifest_doctor import classify_files

_REPAIRABLE_HEALTH = ("missing", "stale")


def repair_plan() -> list[tuple[str, str]]:
    """(component, rel) pairs safe to re-deploy — missing or stale, never user-modified."""
    manifest = install_manifest.load_manifest()
    if manifest is None:
        return []
    return [
        (state.entry.component, state.entry.rel)
        for state in classify_files(manifest)
        if state.health in _REPAIRABLE_HEALTH
    ]


def repair(pairs: Sequence[tuple[str, str]] | None = None) -> ApplyOutcome:
    """Re-deploy only the given (component, rel) files through the shared apply path.

    ``apply_plan`` journals just the planned subset, so afterwards the untouched
    entries from the pre-repair manifest are merged back in: the manifest stays a
    complete inventory, and user-modified files keep their original recorded hash
    (doctor keeps flagging them instead of silently blessing the edit).
    """
    before = install_manifest.load_manifest()
    if pairs is None:
        pairs = repair_plan()
    if before is None or not pairs:
        return ApplyOutcome(
            components=[], manifest_file=install_manifest.manifest_path()
        )
    selected: dict[str, list[str]] = {}
    for component, rel in pairs:
        selected.setdefault(component, []).append(rel)
    outcome = apply_plan(build_plan(list(selected), selected=selected))
    outcome.files = _merge_untouched(before)
    return outcome


def _merge_untouched(before: InstallManifest) -> list[ManagedFile]:
    """Fold pre-repair manifest entries the repair did not touch into the new manifest."""
    after = install_manifest.load_manifest()
    if after is None:
        return []
    repaired = {(entry.component, entry.rel) for entry in after.files}
    after.files.extend(
        entry
        for entry in before.files
        if (entry.component, entry.rel) not in repaired
    )
    after.components = list(dict.fromkeys([*after.components, *before.components]))
    install_manifest.save_manifest(after)
    return after.files
