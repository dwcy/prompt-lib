# -*- coding: utf-8 -*-
"""Headless CLI for the eval harness: `validate | run | judge | report` subcommands.

Each command body lives in its own cli_<name>.py module per the size discipline; this module is
only the argparse surface and the command dispatch table.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from cabal.evals import __version__
from cabal.evals.cli_judge import judge_command
from cabal.evals.cli_report import report_command
from cabal.evals.cli_run import (
    DEFAULT_EVALS_ROOT,
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    run_command,
)
from cabal.evals.cli_validate import validate_command

__all__ = ["DEFAULT_EVALS_ROOT", "EXIT_FAILURE", "EXIT_OK", "EXIT_USAGE", "main"]


def version_line() -> str:
    return f"cabal.evals {__version__}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabal.evals",
        description="Agent eval & regression harness: A/B compare config profiles on pinned tasks.",
    )
    parser.add_argument("--version", action="version", version=version_line())
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    validate = subparsers.add_parser("validate", help="validate the evals/ definition tree")
    validate.add_argument(
        "--root",
        "--evals-root",
        dest="root",
        metavar="DIR",
        default=DEFAULT_EVALS_ROOT,
        help=f"root of the eval definition tree (default: {DEFAULT_EVALS_ROOT})",
    )
    validate.add_argument(
        "--tasks", metavar="ID[,ID...]", help="comma-separated task ids to validate (default: all)"
    )

    run = subparsers.add_parser("run", help="execute the task x config x N matrix")
    run.add_argument("--baseline", metavar="PROFILE", help="baseline config profile name")
    run.add_argument("--candidate", metavar="PROFILE", help="candidate config profile name")
    run.add_argument("--runs", type=int, metavar="N", help="repetitions per cell")
    run.add_argument("--tasks", metavar="ID[,ID...]", help="comma-separated task ids (default: all)")
    run.add_argument("--resume", metavar="RUN_ID", help="resume an interrupted run id")
    run.add_argument("--adapter", metavar="NAME", help="agent adapter override")

    judge = subparsers.add_parser("judge", help="pairwise-judge previously recorded results")
    judge.add_argument("run_id", metavar="RUN_ID", help="results run id to judge")
    judge.add_argument(
        "--tasks", metavar="ID[,ID...]", help="comma-separated task ids (default: all in the run)"
    )
    judge.add_argument(
        "--results-dir",
        metavar="DIR",
        help="results directory override (default: eval.config.toml results_dir)",
    )

    report = subparsers.add_parser("report", help="reduce a run's artifacts into the report")
    report.add_argument("run_id", metavar="RUN_ID", help="results run id to report on")
    report.add_argument(
        "--results-dir",
        metavar="DIR",
        help="results directory override (default: eval.config.toml results_dir)",
    )

    return parser


_HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "run": run_command,
    "validate": validate_command,
    "judge": judge_command,
    "report": report_command,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    return _HANDLERS[args.command](args)
