# -*- coding: utf-8 -*-
"""Headless CLI for the dotnet-codegen pipeline, per `specs/018-dotnet-codegen/contracts/cli-surface.md`.

The `--json` output of these commands is a wire contract consumed by the `/dotnet-codegen` skill,
so the parser, the argument validation and the exit-code map are authoritative here.

Command bodies land in their own tasks. Until each is wired, invoking it raises `NotWiredError`
naming the task that implements it — an explicit, discoverable deferral rather than a silent stub.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from cabal.dotnetgen import __version__
from cabal.dotnetgen.templates.registry import DEFAULT_TEMPLATE, TEMPLATE_IDS

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_HALTED_AT_CEILING = 3
EXIT_ENVIRONMENT_FAILURE = 4
EXIT_REJECTED_AT_GATE = 5

DEFAULT_RETRY_CEILING = 3
DEFAULT_MAP_BUDGET = 1024


class NotWiredError(Exception):
    """Raised by a command whose implementation is scheduled in a later task."""

    def __init__(self, command: str, task: str) -> None:
        super().__init__(f"`{command}` is not wired yet - implemented in {task}")
        self.command = command
        self.task = task


def version_line() -> str:
    return f"cabal.dotnetgen {__version__}"


def _add_global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a single JSON object on stdout; human output goes to stderr",
    )
    parser.add_argument(
        "--project",
        metavar="PATH",
        default=".",
        help="solution root (default: current directory)",
    )
    parser.add_argument(
        "--retry-ceiling",
        type=int,
        metavar="N",
        default=DEFAULT_RETRY_CEILING,
        help=f"hard repair-attempt ceiling (default: {DEFAULT_RETRY_CEILING})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plan only; never write and never call a writing model",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabal.dotnetgen",
        description="Fast, cheap C# backend generation.",
    )
    parser.add_argument("--version", action="version", version=version_line())
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    new = subparsers.add_parser("new", help="create a project from a locked template")
    new.add_argument(
        "--template",
        choices=TEMPLATE_IDS,
        default=DEFAULT_TEMPLATE,
        help=f"architecture template, chosen once and locked (default: {DEFAULT_TEMPLATE})",
    )
    new.add_argument("--description", required=True, help="one-sentence service description")
    new.add_argument("--out", metavar="DIR", help="target directory (default: --project)")
    _add_global_options(new)

    change = subparsers.add_parser("change", help="request a change to an existing project")
    change.add_argument("--request", required=True, help="what to change, in prose")
    _add_global_options(change)

    plan = subparsers.add_parser("plan", help="architect stage only; emits an intent and stops")
    plan.add_argument("--request", required=True, help="what to change, in prose")
    _add_global_options(plan)

    apply_ = subparsers.add_parser("apply", help="execute a previously approved intent")
    apply_.add_argument("--intent-token", required=True, help="token from a prior `plan` run")
    _add_global_options(apply_)

    map_ = subparsers.add_parser("map", help="inspect the structural map")
    map_.add_argument(
        "--budget",
        type=int,
        metavar="TOKENS",
        default=DEFAULT_MAP_BUDGET,
        help=f"hard token budget for the map (default: {DEFAULT_MAP_BUDGET})",
    )
    _add_global_options(map_)

    report = subparsers.add_parser("report", help="run history and cost records")
    report.add_argument("--run", metavar="ID", help="a single run id")
    report.add_argument("--last", type=int, metavar="N", help="the N most recent runs")
    _add_global_options(report)

    providers = subparsers.add_parser("providers", help="inspect stage bindings")
    providers.add_argument(
        "--check",
        action="store_true",
        help="probe each bound provider for reachability without running a pipeline",
    )
    _add_global_options(providers)

    return parser


_TASK_OWNERS = {
    "new": "T029",
    "change": "T044",
    "plan": "T032",
    "apply": "T035",
    "map": "T041",
    "report": "T065",
    "providers": "T056",
}


# Command handlers register here as their tasks land; an absent entry is a deferral, not a bug.
_HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {}


def _dispatch(args: argparse.Namespace) -> int:
    handler = _HANDLERS.get(args.command)
    if handler is None:
        raise NotWiredError(args.command, _TASK_OWNERS[args.command])
    return handler(args)


def _emit_error(args: argparse.Namespace, message: str) -> None:
    if getattr(args, "json", False):
        json.dump({"status": "error", "error": message}, sys.stdout)
        sys.stdout.write("\n")
    else:
        print(message, file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    if getattr(args, "retry_ceiling", DEFAULT_RETRY_CEILING) < 0:
        _emit_error(args, "--retry-ceiling must be zero or greater")
        return EXIT_USAGE

    try:
        return _dispatch(args)
    except NotWiredError as exc:
        _emit_error(args, str(exc))
        return EXIT_FAILURE
