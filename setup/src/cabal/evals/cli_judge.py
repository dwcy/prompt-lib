# -*- coding: utf-8 -*-
"""The `judge` subcommand body: pairwise-judge a recorded run's results, standalone per FR-014.

Kept out of cli.py per the size discipline: cli.py stays the thin argparse surface while this
module owns config resolution (judge model, results dir default) and the exit-code mapping
(0 all pairs judged, 1 any judge_error, 2 usage/config problems). Needs only the results dir
and the evals tree — no worktrees, no agent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from cabal.evals.definitions import DefinitionError, load_eval_config
from cabal.evals.definitions_model import CONFIG_FILENAME
from cabal.evals.judge import JudgeError, judge_run

EXIT_OK: Final[int] = 0
EXIT_FAILURE: Final[int] = 1
EXIT_USAGE: Final[int] = 2

DEFAULT_EVALS_ROOT: Final[str] = "evals"


def _usage_error(message: str) -> int:
    print(f"cabal.evals judge: {message}", file=sys.stderr)
    return EXIT_USAGE


def _parse_task_filter(tasks_arg: str | None) -> list[str] | None:
    if not tasks_arg:
        return None
    selected = [item.strip() for item in tasks_arg.split(",") if item.strip()]
    if not selected:
        raise ValueError("--tasks was given but contains no task ids")
    return selected


def judge_command(args: argparse.Namespace) -> int:
    """Exit codes: 0 all pairs judged (ties fine), 1 any judge_error, 2 usage/config problems."""
    evals_root = Path(DEFAULT_EVALS_ROOT)
    try:
        eval_config = load_eval_config(evals_root / CONFIG_FILENAME)
    except DefinitionError as exc:
        return _usage_error(str(exc))
    if eval_config.judge_model is None:
        return _usage_error(
            f"[judge] model is required in {evals_root / CONFIG_FILENAME} for the judge phase"
        )

    results_dir = Path(args.results_dir) if args.results_dir else eval_config.results_dir
    run_dir = results_dir / args.run_id
    if not run_dir.is_dir():
        return _usage_error(f"run directory not found: {run_dir}")
    try:
        task_filter = _parse_task_filter(args.tasks)
    except ValueError as exc:
        return _usage_error(str(exc))

    try:
        summaries = judge_run(
            run_dir,
            evals_root,
            eval_config.judge_model,
            eval_config.judge_diff_char_limit,
            task_filter=task_filter,
            progress=print,
        )
    except JudgeError as exc:
        return _usage_error(str(exc))

    pairs = sum(summary.pairs_total for summary in summaries)
    errors = sum(summary.judge_errors for summary in summaries)
    print(
        f"judged {pairs} pair(s) across {len(summaries)} task(s), "
        f"{errors} judge error(s) -> {run_dir}"
    )
    return EXIT_OK if errors == 0 else EXIT_FAILURE
