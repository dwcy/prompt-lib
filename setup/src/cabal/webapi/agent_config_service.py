# -*- coding: utf-8 -*-
"""Read-only folder/file tree and file preview for the Agent Setup module: browses the real
global (~/.claude, ~/.codex, ~/.gemini) and per-project local config directories for Claude,
Codex, and Antigravity. Performs no mutation — pure filesystem reads behind path-containment
and size/depth caps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cabal._paths import CODEX_DIR, GEMINI_DIR, TARGET
from cabal.webapi.envelope import ApiError

AGENTS = ("claude", "codex", "antigravity")
SCOPES = ("global", "local")

MAX_WALK_DEPTH = 8
MAX_ENTRIES = 2000
MAX_PREVIEW_BYTES = 256 * 1024

# Codex and Antigravity share the cross-tool AGENTS.md convention for project-local config;
# neither gets a full project-tree walk, only these known top-level entries.
_SHARED_LOCAL_ROOTS = (".agents", "AGENTS.md")


@dataclass(frozen=True)
class _ScopeSpec:
    base_dir: Path
    # None => list every immediate child of base_dir; else an allow-list of top-level names.
    allowed_roots: tuple[str, ...] | None


def _require_project(project: Path | None) -> Path:
    if project is None:
        raise ApiError(404, "no_project_selected", "Select a project before browsing its local config")
    return project


def _scope_spec(
    agent: str,
    scope: str,
    project: Path | None,
    *,
    claude_target: Path,
    codex_dir: Path,
    gemini_dir: Path,
) -> _ScopeSpec:
    if agent not in AGENTS:
        raise ApiError(422, "params_invalid", f"Unknown agent {agent!r}")
    if scope not in SCOPES:
        raise ApiError(422, "params_invalid", f"Unknown scope {scope!r}")

    if agent == "claude":
        if scope == "global":
            return _ScopeSpec(claude_target, None)
        return _ScopeSpec(_require_project(project) / ".claude", None)

    global_dir = codex_dir if agent == "codex" else gemini_dir
    if scope == "global":
        return _ScopeSpec(global_dir, None)
    return _ScopeSpec(_require_project(project), _SHARED_LOCAL_ROOTS)


def _iso(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def _file_entry(path: Path, name: str, rel_path: str) -> dict[str, Any]:
    try:
        stat = path.stat()
        size_bytes: int | None = stat.st_size
        modified_at: str | None = _iso(stat.st_mtime)
    except OSError:
        size_bytes, modified_at = None, None
    return {
        "name": name,
        "rel_path": rel_path,
        "kind": "file",
        "size_bytes": size_bytes,
        "modified_at": modified_at,
        "children": None,
    }


def _walk_dir(path: Path, rel: str, depth: int, budget: list[int]) -> list[dict[str, Any]]:
    if depth > MAX_WALK_DEPTH or budget[0] <= 0:
        return []
    try:
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError:
        return []

    entries: list[dict[str, Any]] = []
    for child in children:
        if budget[0] <= 0:
            break
        budget[0] -= 1
        child_rel = f"{rel}/{child.name}" if rel else child.name
        if child.is_dir() and not child.is_symlink():
            entries.append(
                {
                    "name": child.name,
                    "rel_path": child_rel,
                    "kind": "dir",
                    "size_bytes": None,
                    "modified_at": None,
                    "children": _walk_dir(child, child_rel, depth + 1, budget),
                }
            )
        else:
            entries.append(_file_entry(child, child.name, child_rel))
    return entries


def build_agent_config_tree(
    agent: str,
    scope: str,
    project: Path | None,
    *,
    claude_target: Path = TARGET,
    codex_dir: Path = CODEX_DIR,
    gemini_dir: Path = GEMINI_DIR,
) -> dict[str, Any]:
    spec = _scope_spec(
        agent, scope, project, claude_target=claude_target, codex_dir=codex_dir, gemini_dir=gemini_dir
    )
    if not spec.base_dir.exists():
        return {
            "agent": agent,
            "scope": scope,
            "base_path": str(spec.base_dir),
            "exists": False,
            "roots": [],
            "truncated": False,
        }

    budget = [MAX_ENTRIES]
    if spec.allowed_roots is None:
        roots = _walk_dir(spec.base_dir, "", 0, budget)
    else:
        roots = []
        for name in spec.allowed_roots:
            child = spec.base_dir / name
            if not child.exists():
                continue
            budget[0] -= 1
            if child.is_dir() and not child.is_symlink():
                roots.append(
                    {
                        "name": name,
                        "rel_path": name,
                        "kind": "dir",
                        "size_bytes": None,
                        "modified_at": None,
                        "children": _walk_dir(child, name, 1, budget),
                    }
                )
            else:
                roots.append(_file_entry(child, name, name))

    return {
        "agent": agent,
        "scope": scope,
        "base_path": str(spec.base_dir),
        "exists": True,
        "roots": roots,
        "truncated": budget[0] <= 0,
    }


def read_agent_config_file(
    agent: str,
    scope: str,
    project: Path | None,
    rel_path: str,
    *,
    claude_target: Path = TARGET,
    codex_dir: Path = CODEX_DIR,
    gemini_dir: Path = GEMINI_DIR,
) -> dict[str, Any]:
    spec = _scope_spec(
        agent, scope, project, claude_target=claude_target, codex_dir=codex_dir, gemini_dir=gemini_dir
    )
    if spec.allowed_roots is not None:
        top = rel_path.replace("\\", "/").split("/")[0]
        if top not in spec.allowed_roots:
            raise ApiError(400, "path_outside_root", "Path is outside the browsed roots")

    base_resolved = spec.base_dir.resolve()
    target = (spec.base_dir / rel_path).resolve()
    if target != base_resolved and not target.is_relative_to(base_resolved):
        raise ApiError(400, "path_outside_root", "Path escapes the config root")
    if not target.is_file():
        raise ApiError(404, "not_found", f"{rel_path} was not found")

    raw = target.read_bytes()
    truncated = len(raw) > MAX_PREVIEW_BYTES
    sample = raw[:MAX_PREVIEW_BYTES]
    binary = b"\x00" in sample[:8192]
    content: str | None = None
    if not binary:
        try:
            content = sample.decode("utf-8")
        except UnicodeDecodeError:
            binary = True

    return {
        "rel_path": rel_path,
        "content": content,
        "binary": binary,
        "truncated": truncated,
        "size_bytes": len(raw),
    }
