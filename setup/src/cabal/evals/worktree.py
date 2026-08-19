# -*- coding: utf-8 -*-
"""Git worktree lifecycle per run: detached add at a pinned ref, diff collection, forced removal.

Per research.md R4: detached checkouts create no named branches, `add -N` makes untracked files
appear in the diff without staging content, and forced removal is safe because every artifact is
copied out before the worktree dies.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT_SECONDS = 120
_STATUS_PATH_OFFSET = 3  # porcelain v1: two status chars + one space


class WorktreeError(RuntimeError):
    """A git worktree operation failed; the message carries the command and stderr context."""


@dataclass(frozen=True)
class DiffResult:
    """The collected change set of one run's worktree."""

    patch_text: str
    changed_files: tuple[str, ...]
    insertions: int
    deletions: int
    empty_diff: bool


def _git(cwd: Path, *args: str, timeout: int = GIT_TIMEOUT_SECONDS) -> str:
    cmd = ["git", "-C", str(cwd), *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        raise WorktreeError(f"{' '.join(cmd)}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorktreeError(f"{' '.join(cmd)}: timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise WorktreeError(
            f"{' '.join(cmd)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def create_worktree(repo: Path, ref: str, dest: Path) -> Path:
    """`git worktree add --detach <dest> <ref>`; returns dest."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(Path(repo), "worktree", "add", "--detach", str(dest), ref)
    return dest


def collect_diff(worktree: Path) -> DiffResult:
    """Snapshot the worktree's changes: patch text, changed-file list, numstat totals."""
    worktree = Path(worktree)
    _git(worktree, "add", "-N", ".")
    patch_text = _git(worktree, "diff")
    status = _git(worktree, "status", "--porcelain")
    changed_files = tuple(
        line[_STATUS_PATH_OFFSET:].strip() for line in status.splitlines() if line.strip()
    )
    insertions = deletions = 0
    for line in _git(worktree, "diff", "--numstat").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            # numstat reports "-" for binary files; count only numeric entries.
            if parts[0].isdigit():
                insertions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])
    return DiffResult(
        patch_text=patch_text,
        changed_files=changed_files,
        insertions=insertions,
        deletions=deletions,
        empty_diff=not patch_text.strip(),
    )


def remove_worktree(repo: Path, dest: Path) -> None:
    """`worktree remove --force`; falls back to rmtree + `worktree prune` when git refuses."""
    repo = Path(repo)
    dest = Path(dest)
    try:
        _git(repo, "worktree", "remove", "--force", str(dest))
    except WorktreeError:
        shutil.rmtree(dest, ignore_errors=True)
        _git(repo, "worktree", "prune")
