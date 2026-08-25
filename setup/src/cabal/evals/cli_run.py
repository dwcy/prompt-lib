# -*- coding: utf-8 -*-
"""The `run` subcommand body: definition loading, fail-fast validation, and matrix dispatch.

Kept out of cli.py per the size discipline: cli.py stays the thin argparse surface while this
module owns run-specific resolution (resume manifest, task selection, adapter probing).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

from cabal.evals.adapters import UnknownAdapterError, get_adapter
from cabal.evals.adapters.base import AgentAdapter
from cabal.evals.definitions import DefinitionError, load_eval_config, load_profile, load_task
from cabal.evals.definitions_model import (
    CONFIG_FILENAME,
    CONFIGS_DIRNAME,
    TASKS_DIRNAME,
    Task,
)
from cabal.evals.matrix import MANIFEST_FILENAME, mint_run_id, run_matrix

EXIT_OK: Final[int] = 0
EXIT_FAILURE: Final[int] = 1
EXIT_USAGE: Final[int] = 2

DEFAULT_EVALS_ROOT: Final[str] = "evals"


def _config_error(message: str) -> int:
    print(f"cabal.evals run: {message}", file=sys.stderr)
    return EXIT_USAGE


def _load_manifest(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _manifest_str(manifest: dict[str, Any] | None, key: str) -> str | None:
    if manifest is None:
        return None
    value = manifest.get(key)
    return value if isinstance(value, str) and value else None


def _manifest_int(manifest: dict[str, Any] | None, key: str) -> int | None:
    if manifest is None:
        return None
    value = manifest.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def _select_tasks(
    evals_root: Path, tasks_arg: str | None, manifest: dict[str, Any] | None
) -> list[Task]:
    tasks_dir = evals_root / TASKS_DIRNAME
    available = (
        sorted(child for child in tasks_dir.iterdir() if child.is_dir())
        if tasks_dir.is_dir()
        else []
    )
    selected: list[str] | None = None
    if tasks_arg:
        selected = [item.strip() for item in tasks_arg.split(",") if item.strip()]
    elif manifest is not None and isinstance(manifest.get("tasks"), list):
        selected = [str(item) for item in manifest["tasks"]]
    if selected is None:
        return [load_task(child) for child in available]
    by_id = {child.name: child for child in available}
    missing = [task_id for task_id in selected if task_id not in by_id]
    if missing:
        raise LookupError(f"unknown task id(s): {', '.join(missing)}")
    return [load_task(by_id[task_id]) for task_id in selected]


def _resolve_adapter(name: str) -> AgentAdapter | int:
    try:
        adapter = get_adapter(name)
    except UnknownAdapterError as exc:
        return _config_error(str(exc))
    status = adapter.check()
    if not status.available:
        return _config_error(f"adapter {name!r} is unavailable: {status.detail}")
    return adapter


def run_command(args: argparse.Namespace) -> int:
    """Exit codes: 0 all cells completed, 1 some cells failed, 2 configuration error."""
    evals_root = Path(DEFAULT_EVALS_ROOT)
    try:
        eval_config = load_eval_config(evals_root / CONFIG_FILENAME)
    except DefinitionError as exc:
        return _config_error(str(exc))

    manifest = _load_manifest(eval_config.results_dir / args.resume) if args.resume else None
    baseline_name = args.baseline or _manifest_str(manifest, "baseline")
    candidate_name = args.candidate or _manifest_str(manifest, "candidate")
    if not baseline_name or not candidate_name:
        return _config_error(
            "--baseline and --candidate are required (or --resume a run whose run.json manifest exists)"
        )

    adapter_name = args.adapter or _manifest_str(manifest, "adapter") or eval_config.adapter
    adapter = _resolve_adapter(adapter_name)
    if isinstance(adapter, int):
        return adapter

    runs = args.runs if args.runs is not None else (
        _manifest_int(manifest, "runs") or eval_config.runs_per_cell
    )
    if runs < 1:
        return _config_error("--runs must be >= 1")

    try:
        baseline = load_profile(evals_root / CONFIGS_DIRNAME / baseline_name)
        candidate = load_profile(evals_root / CONFIGS_DIRNAME / candidate_name)
        tasks = _select_tasks(evals_root, args.tasks, manifest)
    except DefinitionError as exc:
        return _config_error(str(exc))
    except LookupError as exc:
        return _config_error(str(exc))
    if not tasks:
        return _config_error(f"no tasks found under {evals_root / TASKS_DIRNAME}")

    run_id = args.resume or mint_run_id()
    print(
        f"run {run_id}: {baseline.name} vs {candidate.name} | "
        f"{len(tasks)} task(s) x 2 configs x {runs} run(s) | adapter {adapter_name}"
    )
    summary = run_matrix(
        eval_config,
        tasks,
        baseline,
        candidate,
        runs,
        eval_config.results_dir,
        adapter,
        resume_run_id=run_id,
        progress=print,
    )
    print(
        f"cells: {summary.completed} completed, {summary.failed} failed, "
        f"{summary.skipped} skipped -> {summary.run_dir}"
    )
    return EXIT_OK if summary.failed == 0 else EXIT_FAILURE
