# -*- coding: utf-8 -*-
"""Exit codes and the stdout/stderr split, per `contracts/cli-surface.md`.

Its own module so that `cli.py` (parser and dispatch) and `commands.py` (handler bodies) can both
depend on it without importing each other.

The channel rule is a wire contract, not a style choice: the `/dotnet-codegen` skill parses
stdout, so `--json` puts exactly one object there and every human-readable byte goes to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_HALTED_AT_CEILING = 3
EXIT_ENVIRONMENT_FAILURE = 4
EXIT_REJECTED_AT_GATE = 5


class NotWiredError(Exception):
    """Raised by a command whose implementation is scheduled in a later task."""

    def __init__(self, command: str, task: str) -> None:
        super().__init__(f"`{command}` is not wired yet - implemented in {task}")
        self.command = command
        self.task = task


def emit_error(args: argparse.Namespace, message: str) -> None:
    if getattr(args, "json", False):
        json.dump({"status": "error", "error": message}, sys.stdout)
        sys.stdout.write("\n")
    else:
        print(message, file=sys.stderr)


def emit_result(args: argparse.Namespace, payload: dict[str, object], summary: str) -> None:
    """`--json` puts one object on stdout; human output goes to stderr."""
    if getattr(args, "json", False):
        json.dump(payload, sys.stdout, default=str)
        sys.stdout.write("\n")
    else:
        print(summary, file=sys.stderr)


def zero_stage() -> dict[str, object]:
    """A stage that did not run. Reported as an explicit zero, never omitted."""
    return {"input_tokens": 0, "output_tokens": 0, "cost": 0}
