# -*- coding: utf-8 -*-
"""Manifest-aware doctor checks: install manifest vs on-disk state of ~/.claude.

A file whose on-disk content still matches its manifest hash while the bundled
SOURCE has moved on is a pending update, not ill health — the update screen and
`cabal apply` drift preview already own that case, so no finding is emitted for
it here (T015 documented choice; ``Finding`` has no info severity to waste on a
duplicate of the diff view).

All paths resolve lazily (``cabal._paths.TARGET`` via ``install_manifest`` and
the component registry) so tests can sandbox HOME.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cabal
from cabal import _paths, install_manifest
from cabal.apply_service import source_sha
from cabal.components import COMPONENTS
from cabal.config_doctor import Finding, _rel, finding_order
from cabal.install_manifest import InstallManifest, ManagedFile, ManifestError

ManifestStatus = Literal["present-complete", "present-in-progress", "absent"]
FileHealth = Literal["ok", "missing", "stale", "user-modified"]

# Per-file finding categories a targeted repair re-deploys safely.
FILE_REPAIR_CATEGORIES: frozenset[str] = frozenset(
    {"missing-managed-file", "stale-manifest"}
)
# Everything `cabal apply --yes` resolves (repair superset + resume).
REPAIRABLE_CATEGORIES: frozenset[str] = FILE_REPAIR_CATEGORIES | {"interrupted-apply"}


@dataclass(frozen=True)
class ManagedFileState:
    """Classification of one manifest entry against the disk and bundled source."""

    entry: ManagedFile
    health: FileHealth
    dest: Path


@dataclass(frozen=True)
class ManifestReport:
    """Presence, raw journal status, and findings — all a doctor surface needs."""

    present: bool
    status: str | None  # "complete" | "in_progress" | None when absent/tampered
    tool_version: str | None
    findings: list[Finding] = field(default_factory=list)


def _source_and_dest(entry: ManagedFile) -> tuple[Path, Path] | None:
    comp = next((c for c in COMPONENTS if c.key == entry.component), None)
    if comp is None:
        return None
    if comp.type == "file":
        return comp.src_path, comp.dst_path
    return comp.src_path / entry.rel, comp.dst_path / entry.rel


def _health(entry: ManagedFile, src: Path, dest: Path) -> FileHealth:
    if not dest.is_file():
        return "missing"
    on_disk = install_manifest.sha256_file(dest)
    if on_disk == entry.sha256:
        return "ok"
    if src.is_file() and source_sha(src) == on_disk:
        return "stale"
    return "user-modified"


def classify_files(manifest: InstallManifest) -> list[ManagedFileState]:
    """Health of every manifest entry; entries of unregistered components are skipped
    (the component left the registry — uninstall owns that cleanup, not doctor)."""
    states: list[ManagedFileState] = []
    for entry in manifest.files:
        located = _source_and_dest(entry)
        if located is None:
            continue
        src, dest = located
        states.append(ManagedFileState(entry, _health(entry, src, dest), dest))
    return states


def _file_finding(state: ManagedFileState, target: Path) -> Finding | None:
    path = _rel(state.dest, target)
    if state.health == "missing":
        return Finding(
            "error", "missing-managed-file", path,
            "File is recorded in the install manifest but missing from disk.",
            "Repair from the wizard doctor panel or run `cabal apply --yes` to restore it.",
        )
    if state.health == "stale":
        return Finding(
            "warning", "stale-manifest", path,
            "Content matches the current bundled source but not the manifest record "
            "— the file was redeployed outside cabal, so the record is stale.",
            "Repair from the wizard doctor panel or run `cabal apply --yes` "
            "to refresh the manifest record.",
        )
    if state.health == "user-modified":
        return Finding(
            "warning", "user-modified", path,
            "Content matches neither the install manifest nor the bundled source "
            "— the file was modified by hand.",
            "Repair skips this file; review it and resolve by hand "
            "(a full apply would overwrite your edits).",
        )
    return None


def manifest_findings(manifest: InstallManifest) -> list[Finding]:
    """All manifest health findings: journal state, version skew, per-file drift."""
    target = _paths.TARGET
    manifest_rel = _rel(install_manifest.manifest_path(), target)
    findings: list[Finding] = []
    if manifest.status == "in_progress":
        findings.append(Finding(
            "error", "interrupted-apply", manifest_rel,
            "A previous apply was interrupted mid-write (manifest status: in_progress).",
            "Resume or roll back from the wizard recovery dialog, "
            "or run `cabal apply --yes` to resume.",
        ))
    if manifest.tool_version != cabal.__version__:
        findings.append(Finding(
            "warning", "version-skew", manifest_rel,
            f"Manifest was written by cabal {manifest.tool_version}, "
            f"but cabal {cabal.__version__} is running.",
            "Run `cabal apply --yes` so the deployment and manifest match this version.",
        ))
    for state in classify_files(manifest):
        finding = _file_finding(state, target)
        if finding is not None:
            findings.append(finding)
    findings.sort(key=finding_order)
    return findings


def manifest_report() -> ManifestReport:
    """Load and check the manifest; a tampered manifest (unsafe file paths) is not
    silently degraded to "absent" — it surfaces as a single error finding."""
    try:
        manifest = install_manifest.load_manifest()
    except ManifestError as exc:
        finding = Finding(
            "error", "manifest-tampered",
            _rel(install_manifest.manifest_path(), _paths.TARGET),
            f"Install manifest cannot be trusted: {exc}",
            "Restore a snapshot from ~/.claude/.cabal/history/ "
            "or run `cabal apply --yes` to rewrite it.",
        )
        return ManifestReport(
            present=True, status=None, tool_version=None, findings=[finding]
        )
    if manifest is None:
        return ManifestReport(present=False, status=None, tool_version=None)
    return ManifestReport(
        present=True,
        status=manifest.status,
        tool_version=manifest.tool_version,
        findings=manifest_findings(manifest),
    )


def manifest_status() -> ManifestStatus:
    """Presence classification for the doctor exit-code logic (exit 5 on "absent").

    A tampered manifest counts as present — it must halt with an error finding,
    not fall through to the legacy no-manifest path.
    """
    report = manifest_report()
    if not report.present:
        return "absent"
    return (
        "present-in-progress"
        if report.status == "in_progress"
        else "present-complete"
    )
