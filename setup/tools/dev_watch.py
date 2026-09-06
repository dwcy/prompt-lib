#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Source-change detection for the dev backend supervisor: which files to watch, and what
changed between two passes.

Polls mtimes with the stdlib rather than taking a `watchfiles` dependency: this is
launcher-only tooling that must work with no extra setup, and stat-ing a few hundred files
once a second costs nothing.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from pathlib import Path

WATCH_SUFFIXES = frozenset({".py"})
SKIP_DIRECTORIES = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
    }
)


def iter_watched_files(roots: Sequence[Path]) -> Iterator[Path]:
    """Every watched source file under `roots`, skipping generated and dependency trees."""
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRECTORIES]
            for filename in filenames:
                if Path(filename).suffix in WATCH_SUFFIXES:
                    yield Path(dirpath) / filename


def snapshot(roots: Sequence[Path]) -> dict[Path, float]:
    """Modification times for every watched file; unreadable files are simply absent."""
    stamps: dict[Path, float] = {}
    for path in iter_watched_files(roots):
        try:
            stamps[path] = path.stat().st_mtime
        except OSError:
            continue
    return stamps


def changed_paths(previous: dict[Path, float], current: dict[Path, float]) -> list[Path]:
    """Files added, removed, or modified between two snapshots, sorted for stable output."""
    changed = {path for path, stamp in current.items() if previous.get(path) != stamp}
    changed |= set(previous) - set(current)
    return sorted(changed)


def describe(paths: Sequence[Path], root: Path, limit: int = 3) -> str:
    """A short "a.py, b.py (+2 more)" summary, relative to `root` where possible."""
    names: list[str] = []
    for path in paths[:limit]:
        try:
            names.append(path.relative_to(root).as_posix())
        except ValueError:
            names.append(path.name)
    remaining = len(paths) - len(names)
    if remaining > 0:
        names.append(f"(+{remaining} more)")
    return ", ".join(names)
