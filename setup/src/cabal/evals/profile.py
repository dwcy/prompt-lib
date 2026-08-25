# -*- coding: utf-8 -*-
"""Materialize a config profile into a per-run scratch CLAUDE_CONFIG_DIR, and clean it up after.

Per research.md R2: materializing per run (not per profile) means a crashed run can never poison
the next one, and the user's real ~/.claude/ is never read as config or written during a run.
"""

from __future__ import annotations

import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path

from cabal.evals.definitions_model import ConfigProfile

CONFIG_DIRNAME = "config"
CREDENTIALS_FILENAME = ".credentials.json"
USER_CLAUDE_DIRNAME = ".claude"


@dataclass(frozen=True)
class MaterializedProfile:
    """A profile realized on disk for one run: relocated config root, settings file, extra env."""

    config_dir: Path
    settings_file: Path | None
    env: dict[str, str]


def materialize(profile: ConfigProfile, run_scratch_dir: Path, worktree: Path) -> MaterializedProfile:
    """Build `<run_scratch_dir>/config` from the profile overlay; copy the project overlay into the worktree.

    Copies `~/.claude/.credentials.json` into the scratch config dir when it exists — REQUIRED,
    not optional: auth does not resolve under a relocated CLAUDE_CONFIG_DIR (research.md R2,
    T010-verified live), so without the copy every run fails "Not logged in". `cleanup()` must
    delete the scratch dir after the run so credentials never outlive it.
    """
    config_dir = Path(run_scratch_dir) / CONFIG_DIRNAME
    config_dir.mkdir(parents=True, exist_ok=True)
    if profile.user_overlay is not None:
        shutil.copytree(profile.user_overlay, config_dir, dirs_exist_ok=True)
    if profile.project_overlay is not None:
        shutil.copytree(profile.project_overlay, Path(worktree), dirs_exist_ok=True)
    credentials = Path.home() / USER_CLAUDE_DIRNAME / CREDENTIALS_FILENAME
    if credentials.is_file():
        shutil.copy2(credentials, config_dir / CREDENTIALS_FILENAME)
    settings_file = profile.settings_file.resolve() if profile.settings_file is not None else None
    return MaterializedProfile(config_dir=config_dir, settings_file=settings_file, env=dict(profile.env))


def cleanup(run_scratch_dir: Path) -> bool:
    """Delete the scratch tree (credentials must never outlive the run). Never raises."""
    run_scratch_dir = Path(run_scratch_dir)
    if not run_scratch_dir.exists():
        return True
    shutil.rmtree(run_scratch_dir, ignore_errors=True)
    if run_scratch_dir.exists():
        warnings.warn(f"could not fully remove scratch dir {run_scratch_dir}", stacklevel=2)
        return False
    return True


def profiles_identical(a: MaterializedProfile, b: MaterializedProfile) -> bool:
    """Byte-compare two materialized profiles, for the `no-op comparison` warning (rule 4)."""
    if a.env != b.env:
        return False
    if not _same_file_bytes(a.settings_file, b.settings_file):
        return False
    return _dir_fingerprint(a.config_dir) == _dir_fingerprint(b.config_dir)


def _same_file_bytes(a: Path | None, b: Path | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return a.read_bytes() == b.read_bytes()


def _dir_fingerprint(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
