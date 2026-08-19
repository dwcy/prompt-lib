# -*- coding: utf-8 -*-
"""The `validate` subcommand body: whole-tree validation over `definitions.validate_tree`.

Kept out of cli.py per the size discipline: cli.py stays the thin argparse surface while this
module owns root resolution, the --tasks filter, per-error formatting, and the exit-code mapping
(0 clean, 1 definition errors, 2 usage problems).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from cabal.evals.adapters import registered_names
from cabal.evals.definitions import DefinitionError, load_eval_config, validate_tree
from cabal.evals.definitions_model import (
    CONFIG_FILENAME,
    CONFIGS_DIRNAME,
    RUBRICS_DIRNAME,
    TASKS_DIRNAME,
)

EXIT_OK: Final[int] = 0
EXIT_FAILURE: Final[int] = 1
EXIT_USAGE: Final[int] = 2

RUBRIC_SUFFIX: Final[str] = ".md"


def _usage_error(message: str) -> int:
    print(f"cabal.evals validate: {message}", file=sys.stderr)
    return EXIT_USAGE


def _dir_names(parent: Path) -> list[str]:
    if not parent.is_dir():
        return []
    return sorted(child.name for child in parent.iterdir() if child.is_dir())


def _parse_task_filter(tasks_arg: str | None, available: list[str]) -> list[str] | None:
    if not tasks_arg:
        return None
    selected = [item.strip() for item in tasks_arg.split(",") if item.strip()]
    if not selected:
        raise ValueError("--tasks was given but contains no task ids")
    missing = [task_id for task_id in selected if task_id not in available]
    if missing:
        raise ValueError(f"unknown task id(s): {', '.join(missing)}")
    return selected


def _adapter_error(evals_root: Path) -> str | None:
    """Unknown adapter names fail at validate time, before any run ever touches a worktree."""
    config_file = evals_root / CONFIG_FILENAME
    if not config_file.is_file():
        return None
    try:
        eval_config = load_eval_config(config_file)
    except DefinitionError:
        return None
    if eval_config.adapter in registered_names():
        return None
    known = ", ".join(registered_names()) or "(none registered)"
    return f"{config_file}: adapter: unknown adapter {eval_config.adapter!r}; registered: {known}"


def validate_command(args: argparse.Namespace) -> int:
    """Exit codes: 0 tree is valid, 1 definition errors found, 2 usage problem."""
    evals_root = Path(args.root)
    if not evals_root.is_dir():
        return _usage_error(f"evals root is not a directory: {evals_root}")

    task_dirs = _dir_names(evals_root / TASKS_DIRNAME)
    try:
        task_ids = _parse_task_filter(args.tasks, task_dirs)
    except ValueError as exc:
        return _usage_error(str(exc))

    errors = validate_tree(evals_root, task_ids)
    if errors:
        for error in errors:
            print(f"{error.file}: {error.field}: {error.message}")
        print(f"{len(errors)} error(s) found under {evals_root}", file=sys.stderr)
        return EXIT_FAILURE

    adapter_error = _adapter_error(evals_root)
    if adapter_error is not None:
        print(adapter_error)
        print(f"1 error(s) found under {evals_root}", file=sys.stderr)
        return EXIT_FAILURE

    tasks_validated = len(task_ids) if task_ids is not None else len(task_dirs)
    profiles = len(_dir_names(evals_root / CONFIGS_DIRNAME))
    rubrics_dir = evals_root / RUBRICS_DIRNAME
    rubrics = (
        len(sorted(rubrics_dir.glob(f"*{RUBRIC_SUFFIX}"))) if rubrics_dir.is_dir() else 0
    )
    print(
        f"ok: {tasks_validated} task(s), {profiles} profile(s), "
        f"{rubrics} rubric(s) validated under {evals_root}"
    )
    return EXIT_OK
