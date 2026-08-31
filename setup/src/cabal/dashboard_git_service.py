# -*- coding: utf-8 -*-
"""Local git collector for the dashboard — all `git` subprocess I/O lives here."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from cabal.dashboard_links import parse_github_remote
from cabal.models.dashboard import AvailabilityState, GitBranch, GitRemote, GitSection, GitWorktree

_GIT = "git"
_TIMEOUT = 10
_DETACHED_REF = "HEAD"
_FETCH_SUFFIX = "(fetch)"
_BRANCH_FIELD_SEP = "\t"

_HINT_NO_CLI = "git CLI not found"
_HINT_NOT_REPO = "not a git repository"
_HINT_TIMEOUT = "git command timed out"

_ARGS_IS_REPO = ("rev-parse", "--is-inside-work-tree")
_ARGS_BRANCH = ("rev-parse", "--abbrev-ref", "HEAD")
_ARGS_SHORT_SHA = ("rev-parse", "--short", "HEAD")
_ARGS_LOCAL_BRANCHES = (
    "branch",
    "--format="
    + _BRANCH_FIELD_SEP.join(
        ("%(refname:short)", "%(committerdate:iso-strict)", "%(upstream:remotename)")
    ),
)
_ARGS_REMOTES = ("remote", "-v")
_ARGS_WORKTREES = ("worktree", "list", "--porcelain")

_WORKTREE_PATH_PREFIX = "worktree "
_WORKTREE_BRANCH_PREFIX = "branch refs/heads/"
_WORKTREE_DETACHED_LINE = "detached"


def collect_current_branch(project: Path) -> str | None:
    """Single-call branch lookup for callers that only need the name (e.g. health polling) —
    skips the repo/local-branches/remotes checks `collect_git` does for the full dashboard section.
    """
    git = shutil.which(_GIT)
    if git is None:
        return None
    try:
        branch, _detached = _resolve_branch(git, project)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return branch


def collect_git(project: Path) -> GitSection:
    """Collect the local git state for `project`; never raises."""
    git = shutil.which(_GIT)
    if git is None:
        return GitSection(state=AvailabilityState.NO_CLI, hint=_HINT_NO_CLI)

    try:
        repo_check = _run_git(git, project, _ARGS_IS_REPO)
        if repo_check is None or repo_check.returncode != 0:
            return GitSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NOT_REPO)
        if (repo_check.stdout or "").strip() != "true":
            return GitSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NOT_REPO)

        current_branch, detached = _resolve_branch(git, project)
        local_branches = _resolve_local_branches(git, project)
        remotes = _resolve_remotes(git, project)
        worktrees = _resolve_worktrees(git, project, local_branches)
    except subprocess.TimeoutExpired:
        return GitSection(state=AvailabilityState.TIMEOUT, hint=_HINT_TIMEOUT)
    except OSError as exc:
        return GitSection(state=AvailabilityState.ERROR, hint=str(exc))

    return GitSection(
        state=AvailabilityState.OK,
        current_branch=current_branch,
        detached=detached,
        local_branches=local_branches,
        remotes=remotes,
        worktrees=worktrees,
    )


def _run_git(
    git: str, project: Path, args: tuple[str, ...]
) -> subprocess.CompletedProcess[str] | None:
    """Run `git -C <project> <args>`; return the completed process, or None on bad argv."""
    return subprocess.run(
        [git, "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
    )


def _resolve_branch(git: str, project: Path) -> tuple[str | None, bool]:
    result = _run_git(git, project, _ARGS_BRANCH)
    name = (result.stdout or "").strip() if result is not None else ""
    if not name:
        return None, False
    if name == _DETACHED_REF:
        sha_result = _run_git(git, project, _ARGS_SHORT_SHA)
        sha = (sha_result.stdout or "").strip() if sha_result is not None else ""
        return (sha or None), bool(sha)
    return name, False


def _resolve_local_branches(git: str, project: Path) -> list[GitBranch]:
    result = _run_git(git, project, _ARGS_LOCAL_BRANCHES)
    if result is None:
        return []
    branches: list[GitBranch] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        name, _, rest = line.partition(_BRANCH_FIELD_SEP)
        last_commit_at, _, upstream_remote = rest.partition(_BRANCH_FIELD_SEP)
        name = name.strip()
        if not name:
            continue
        branches.append(
            GitBranch(
                name=name,
                last_commit_at=last_commit_at.strip() or None,
                upstream_remote=upstream_remote.strip() or None,
            )
        )
    return branches


def _resolve_worktrees(
    git: str, project: Path, local_branches: list[GitBranch]
) -> list[GitWorktree]:
    """Parse `git worktree list --porcelain` — blank-line-separated blocks, one per worktree.

    `last_commit_at` for a worktree on a branch is looked up from `local_branches` (branches
    are shared refs visible from every worktree, so the primary worktree's branch list already
    covers branches checked out elsewhere); detached worktrees are left without a date rather
    than paying for an extra `git log` call per worktree.
    """
    result = _run_git(git, project, _ARGS_WORKTREES)
    if result is None:
        return []
    last_commit_by_branch = {b.name: b.last_commit_at for b in local_branches}
    worktrees: list[GitWorktree] = []
    path: str | None = None
    branch: str | None = None
    detached = False

    def flush() -> None:
        if path is not None:
            worktrees.append(
                GitWorktree(
                    path=path,
                    branch=branch,
                    detached=detached,
                    last_commit_at=last_commit_by_branch.get(branch) if branch else None,
                )
            )

    for line in (result.stdout or "").splitlines():
        if not line.strip():
            flush()
            path, branch, detached = None, None, False
            continue
        if line.startswith(_WORKTREE_PATH_PREFIX):
            path = line[len(_WORKTREE_PATH_PREFIX) :].strip()
        elif line.startswith(_WORKTREE_BRANCH_PREFIX):
            branch = line[len(_WORKTREE_BRANCH_PREFIX) :].strip()
        elif line.strip() == _WORKTREE_DETACHED_LINE:
            detached = True
    flush()
    return worktrees


def _resolve_remotes(git: str, project: Path) -> list[GitRemote]:
    result = _run_git(git, project, _ARGS_REMOTES)
    if result is None:
        return []
    seen: dict[str, str] = {}
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped.endswith(_FETCH_SUFFIX):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        seen.setdefault(name, url)
    return [
        GitRemote(name=name, url=url, is_github=parse_github_remote(url) is not None)
        for name, url in seen.items()
    ]
