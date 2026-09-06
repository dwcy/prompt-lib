# -*- coding: utf-8 -*-
"""Confirmation-guarded mutations for the Project Dashboard's Git health card: switching branch,
deleting a local branch, and removing a worktree. All shell out to `git -C <project>`; none touch
the network. Digests are recomputed over the exact state each action's precondition depends on, so
a concurrent branch move or worktree change invalidates a stale ticket (FR-014 re-review flow)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from cabal.webapi.actions import ActionDescriptor, ActionOutcome, effect_preview
from cabal.webapi.envelope import ApiError, compute_precondition_digest

_GIT = "git"
_TIMEOUT = 15

GIT_SWITCH_BRANCH_ACTION_ID = "git.switch_branch"
GIT_DELETE_BRANCH_ACTION_ID = "git.delete_branch"
GIT_REMOVE_WORKTREE_ACTION_ID = "git.remove_worktree"

_BRANCH_SCHEMA = {
    "type": "object",
    "properties": {"branch": {"type": "string", "minLength": 1}},
    "required": ["branch"],
    "additionalProperties": False,
}
_WORKTREE_SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string", "minLength": 1}},
    "required": ["path"],
    "additionalProperties": False,
}


def _require_project(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(422, "params_invalid", "Select a project before changing its git state")
    return Path(project)


def _run_git(project: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [_GIT, "-C", str(project), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise ApiError(500, "git_timeout", f"git {' '.join(args)} timed out") from exc
    except OSError as exc:
        raise ApiError(500, "git_unavailable", str(exc)) from exc


def _git_or_raise(project: Path, args: list[str], *, error_code: str) -> str:
    result = _run_git(project, args)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise ApiError(422, error_code, message)
    return result.stdout or ""


def _current_branch(project: Path) -> str | None:
    result = _run_git(project, ["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        return None
    name = (result.stdout or "").strip()
    return name or None


def _branch_sha(project: Path, branch: str) -> str | None:
    result = _run_git(project, ["rev-parse", "--verify", "--quiet", branch])
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def _worktree_paths(project: Path) -> list[str]:
    result = _run_git(project, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return []
    paths = []
    for line in (result.stdout or "").splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree ") :].strip())
    return sorted(paths)


# --- git.switch_branch -------------------------------------------------------


def _switch_prepare(params: dict, _state: Any) -> dict:
    return effect_preview(
        f"Switch to branch '{params['branch']}'",
        commands=[f"git checkout {params['branch']}"],
        scopes=["git"],
    )


def _switch_digest(_params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    current = _current_branch(Path(project)) if project is not None else None
    return compute_precondition_digest({"current_branch": current})


def _switch_execute(params: dict, state: Any) -> ActionOutcome:
    project = _require_project(state)
    branch = params["branch"]
    _git_or_raise(project, ["checkout", branch], error_code="git_checkout_failed")
    return ActionOutcome(data={"branch": branch})


# --- git.delete_branch -------------------------------------------------------


def _delete_branch_prepare(params: dict, state: Any) -> dict:
    branch = params["branch"]
    project = getattr(state, "project", None)
    current = _current_branch(Path(project)) if project is not None else None
    if branch == current:
        raise ApiError(422, "params_invalid", f"Cannot delete '{branch}': it is the checked-out branch")
    return effect_preview(
        f"Delete local branch '{branch}'",
        commands=[f"git branch -d {branch}"],
        scopes=["git"],
        backup="No backup; the branch ref is removed (git keeps unreachable commits until gc)",
        removals=[branch],
    )


def _delete_branch_digest(params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    sha = _branch_sha(Path(project), params["branch"]) if project is not None else None
    return compute_precondition_digest({"branch": params.get("branch"), "sha": sha})


def _delete_branch_execute(params: dict, state: Any) -> ActionOutcome:
    project = _require_project(state)
    branch = params["branch"]
    _git_or_raise(project, ["branch", "-d", branch], error_code="git_delete_branch_failed")
    return ActionOutcome(data={"branch": branch})


# --- git.remove_worktree ------------------------------------------------------


def _remove_worktree_prepare(params: dict, state: Any) -> dict:
    path = params["path"]
    project = getattr(state, "project", None)
    if project is not None and Path(path) == Path(project):
        raise ApiError(422, "params_invalid", "Cannot remove the project's primary worktree")
    return effect_preview(
        f"Remove worktree at '{path}'",
        commands=[f"git worktree remove {path}"],
        scopes=["git"],
        backup="No backup; the worktree's working directory is deleted (its branch ref is kept)",
        removals=[path],
    )


def _remove_worktree_digest(_params: dict, state: Any) -> str:
    project = getattr(state, "project", None)
    paths = _worktree_paths(Path(project)) if project is not None else []
    return compute_precondition_digest({"worktrees": paths})


def _remove_worktree_execute(params: dict, state: Any) -> ActionOutcome:
    project = _require_project(state)
    path = params["path"]
    _git_or_raise(project, ["worktree", "remove", path], error_code="git_remove_worktree_failed")
    return ActionOutcome(data={"path": path})


GIT_SWITCH_BRANCH_DESCRIPTOR = ActionDescriptor(
    action_id=GIT_SWITCH_BRANCH_ACTION_ID,
    module="project_dashboard",
    destructive=False,
    params_schema=_BRANCH_SCHEMA,
    prepare=_switch_prepare,
    execute=_switch_execute,
    compute_digest=_switch_digest,
)

GIT_DELETE_BRANCH_DESCRIPTOR = ActionDescriptor(
    action_id=GIT_DELETE_BRANCH_ACTION_ID,
    module="project_dashboard",
    destructive=True,
    params_schema=_BRANCH_SCHEMA,
    prepare=_delete_branch_prepare,
    execute=_delete_branch_execute,
    compute_digest=_delete_branch_digest,
)

GIT_REMOVE_WORKTREE_DESCRIPTOR = ActionDescriptor(
    action_id=GIT_REMOVE_WORKTREE_ACTION_ID,
    module="project_dashboard",
    destructive=True,
    params_schema=_WORKTREE_SCHEMA,
    prepare=_remove_worktree_prepare,
    execute=_remove_worktree_execute,
    compute_digest=_remove_worktree_digest,
)

GIT_HEALTH_DESCRIPTORS = (
    GIT_SWITCH_BRANCH_DESCRIPTOR,
    GIT_DELETE_BRANCH_DESCRIPTOR,
    GIT_REMOVE_WORKTREE_DESCRIPTOR,
)
