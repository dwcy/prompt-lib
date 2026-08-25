# -*- coding: utf-8 -*-
"""The `report` subcommand body: reduce a recorded run into report.json/report.md + rich table.

Kept out of cli.py per the size discipline: cli.py stays the thin argparse surface while this
module owns results-dir resolution and the exit-code mapping (0 success, 2 usage/config
problems). Missing comparisons are a note, never a failure — judging is optional.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from rich.console import Console

from cabal.evals.definitions import DefinitionError, load_eval_config
from cabal.evals.definitions_model import CONFIG_FILENAME
from cabal.evals.report import ReportError, build_report, write_report
from cabal.evals.report_render import build_terminal_table, render_markdown

EXIT_OK: Final[int] = 0
EXIT_USAGE: Final[int] = 2

DEFAULT_EVALS_ROOT: Final[str] = "evals"


def _usage_error(message: str) -> int:
    print(f"cabal.evals report: {message}", file=sys.stderr)
    return EXIT_USAGE


def report_command(args: argparse.Namespace) -> int:
    """Exit codes: 0 report written, 2 usage/config problems."""
    evals_root = Path(DEFAULT_EVALS_ROOT)
    try:
        eval_config = load_eval_config(evals_root / CONFIG_FILENAME)
    except DefinitionError as exc:
        return _usage_error(str(exc))

    results_dir = Path(args.results_dir) if args.results_dir else eval_config.results_dir
    run_dir = results_dir / args.run_id
    if not run_dir.is_dir():
        return _usage_error(f"run directory not found: {run_dir}")

    try:
        bundle = build_report(run_dir)
    except ReportError as exc:
        return _usage_error(str(exc))

    markdown = render_markdown(bundle.payload, bundle.notes)
    json_path, md_path = write_report(run_dir, bundle, markdown)

    console = Console()
    console.print(build_terminal_table(bundle.payload))
    for note in bundle.notes:
        console.print(f"note: {note}")
    print(f"wrote {json_path} and {md_path}")
    return EXIT_OK
