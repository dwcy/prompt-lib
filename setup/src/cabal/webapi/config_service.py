# -*- coding: utf-8 -*-
"""Read models for the config-deployment lifecycle: component tree + drift digest,
per-file unified diff, target-only extras, and backup sets — over both the primary
(`claude`) and `codex` deploy targets. Wraps cabal.components/diff_apply/cleanup_service
and their codex twins; performs no mutation (that path is the action registry)."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cabal._paths import TARGET
from cabal.cleanup_service import collect_extras, group_by_component, list_cleanup_backups
from cabal.codex_setup.components import CODEX_COMPONENTS
from cabal.codex_setup.diff_apply import diff_codex_component, find_codex_extras
from cabal.components import COMPONENTS, FileStatus
from cabal.diff_apply import diff_component, find_extras
from cabal.settings_helpers import _effective_settings_text, _is_settings_json
from cabal.webapi.envelope import ApiError, compute_precondition_digest, utc_now_iso

CONFIG_TARGETS = ("claude", "codex")

# Human-facing tree groups so the deploy tree renders as labelled sections rather than a
# flat file list. Keyed by component key; unknown keys fall back to "Other".
_CLAUDE_GROUPS = {
    "settings": "Core files",
    "claude_md": "Core files",
    "design_md": "Core files",
    "keybindings": "Core files",
    "statusline": "Core files",
    "statusline_segments": "Core files",
    "agents": "Agents",
    "hooks": "Hooks",
    "skills": "Skills",
    "rules": "Rules",
    "output_styles": "Output styles",
    "project_templates": "Templates",
    "git_templates": "Templates",
}
_CODEX_GROUPS = {
    "skills": "Skills",
    "references": "References",
    "project_templates": "Templates",
    "readme": "Core files",
    "manifest": "Core files",
}

_STATE_WIRE = {"NEW": "new", "CHANGED": "changed", "UNCHANGED": "unchanged"}


@dataclass(frozen=True)
class _TargetSpec:
    components: list
    diff: Callable[[Any], list[FileStatus]]
    find_extras: Callable[[Any], list[Path]]
    groups: dict[str, str]


def _spec(target: str) -> _TargetSpec:
    if target == "claude":
        return _TargetSpec(COMPONENTS, diff_component, find_extras, _CLAUDE_GROUPS)
    if target == "codex":
        return _TargetSpec(CODEX_COMPONENTS, diff_codex_component, find_codex_extras, _CODEX_GROUPS)
    raise ApiError(422, "params_invalid", f"Unknown config target {target!r}")


def _file_target_path(component: Any, status: FileStatus) -> str:
    """Path identifying a file within its target, stable across components (diff lookup key)."""
    base = Path(component.dst)
    rel = base / status.rel if component.type == "dir" else base
    return rel.as_posix()


def build_config_tree(target: str) -> dict[str, Any]:
    """`/api/config/tree` data: grouped component tree + DriftReport with precondition digest."""
    spec = _spec(target)
    components_payload: list[dict[str, Any]] = []
    counts = {"new": 0, "changed": 0, "unchanged": 0}
    digest_rows: list[tuple[str, str]] = []

    for component in spec.components:
        if not component.src_path.exists():
            continue
        files: list[dict[str, Any]] = []
        for status in spec.diff(component):
            wire_state = _STATE_WIRE[status.state]
            counts[wire_state] += 1
            path = _file_target_path(component, status)
            digest_rows.append(
                (
                    path,
                    wire_state,
                    _file_fingerprint(status.src, source=True),
                    _file_fingerprint(status.dst, source=False),
                )
            )
            files.append(
                {
                    "rel_path": path,
                    "state": wire_state,
                    "diff_available": wire_state != "unchanged",
                }
            )
        components_payload.append(
            {
                "key": component.key,
                "label": component.label,
                "group": spec.groups.get(component.key, "Other"),
                "files": files,
            }
        )

    extras_count = sum(len(spec.find_extras(component)) for component in spec.components)
    digest = compute_precondition_digest({"target": target, "files": sorted(digest_rows)})
    drift = {
        "target": target,
        "changed_count": counts["changed"],
        "new_count": counts["new"],
        "unchanged_count": counts["unchanged"],
        "extras_count": extras_count,
        "computed_at": utc_now_iso(),
        "digest": digest,
    }
    return {"target": target, "components": components_payload, "drift": drift, "digest": digest}


def _status_by_target_path(target: str) -> dict[str, tuple[Any, FileStatus]]:
    spec = _spec(target)
    index: dict[str, tuple[Any, FileStatus]] = {}
    for component in spec.components:
        if not component.src_path.exists():
            continue
        for status in spec.diff(component):
            index[_file_target_path(component, status)] = (component, status)
    return index


def config_diff(target: str, path: str) -> dict[str, Any]:
    """`/api/config/diff` data: unified diff of the deployed file vs the repo source."""
    match = _status_by_target_path(target).get(path)
    if match is None:
        raise ApiError(404, "path_not_found", f"No deployable file at {path!r} for target {target!r}")
    _component, status = match
    diff_text = _unified_diff(status)
    return {"target": target, "rel_path": path, "state": _STATE_WIRE[status.state], "diff_text": diff_text}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _file_fingerprint(path: Path, *, source: bool) -> str | None:
    if not path.exists():
        return None
    try:
        if source and _is_settings_json(path):
            data = _effective_settings_text(path).encode("utf-8")
        else:
            data = path.read_bytes()
    except OSError:
        return "unreadable"
    return hashlib.sha256(data).hexdigest()


def _unified_diff(status: FileStatus) -> str:
    rel = Path(status.rel).as_posix()
    deployed_text = _read_text(status.dst) if status.dst.exists() else ""
    source_text = (
        _effective_settings_text(status.src) if _is_settings_json(status.src) else _read_text(status.src)
    )
    lines = difflib.unified_diff(
        deployed_text.splitlines(keepends=True),
        source_text.splitlines(keepends=True),
        fromfile=f"deployed/{rel}",
        tofile=f"repo/{rel}",
    )
    return "".join(lines)


def config_extras(target: str) -> dict[str, Any]:
    """`/api/config/extras` data: deployed files that did not originate from the repo, grouped."""
    if target == "claude":
        groups = [
            {
                "component": extras[0].component_key,
                "label": label,
                "extras": [
                    {
                        "rel_path": extra.path.relative_to(TARGET).as_posix(),
                        "classification": extra.classification,
                        "reason": extra.reason,
                    }
                    for extra in extras
                ],
            }
            for label, extras in group_by_component(collect_extras())
        ]
        return {"target": target, "groups": groups}

    spec = _spec(target)
    groups = []
    for component in spec.components:
        extra_paths = spec.find_extras(component)
        if not extra_paths:
            continue
        groups.append(
            {
                "component": component.key,
                "label": component.label,
                "extras": [
                    {
                        "rel_path": rel.as_posix(),
                        "classification": "unknown",
                        "reason": "Present in the Codex target but not in the repo source.",
                    }
                    for rel in extra_paths
                ],
            }
        )
    return {"target": target, "groups": groups}


def config_backups(kind: str) -> dict[str, Any]:
    """`/api/config/backups` data: cleanup backup sets or settings.json backups, newest-first."""
    if kind == "cleanup":
        backups = [
            {
                "id": info.path.name,
                "kind": "cleanup",
                "created_at": info.timestamp,
                "files_count": info.entry_count,
                "restorable": True,
            }
            for info in list_cleanup_backups(TARGET)
        ]
        return {"kind": kind, "backups": backups}
    if kind == "settings":
        candidates = sorted(
            TARGET.glob("settings.json.bak*"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        backups = [
            {
                "id": path.name,
                "kind": "settings",
                "created_at": utc_now_iso_from_mtime(path),
                "files_count": 1,
                "restorable": True,
            }
            for path in candidates
        ]
        return {"kind": kind, "backups": backups}
    raise ApiError(422, "params_invalid", f"Unknown backup kind {kind!r}")


def utc_now_iso_from_mtime(path: Path) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


# --- action-side helpers (precondition digests + path resolution) -----------


def deploy_digest(target: str) -> str:
    """Precondition digest for config.apply / codex.apply — the tree's drift digest."""
    return build_config_tree(target)["digest"]


def extras_digest(target: str) -> str:
    """Precondition digest for config.cleanup — over the current extras set."""
    return compute_precondition_digest({"target": target, "extras": config_extras(target)})


def resolve_statuses(target: str, paths: list[str]) -> list[tuple[FileStatus, str]]:
    """Resolve requested target-relative paths to (FileStatus, path) pairs from live state."""
    index = _status_by_target_path(target)
    resolved: list[tuple[FileStatus, str]] = []
    for path in paths:
        match = index.get(path)
        if match is None:
            raise ApiError(422, "params_invalid", f"No deployable file at {path!r} for target {target!r}")
        resolved.append((match[1], path))
    return resolved
