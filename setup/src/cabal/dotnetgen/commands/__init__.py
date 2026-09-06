# -*- coding: utf-8 -*-
"""The command registry. An absent entry is a deferral naming its task, never a silent stub."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from cabal.dotnetgen.commands.generate import cmd_apply, cmd_change, cmd_new, cmd_plan
from cabal.dotnetgen.commands.inspect import cmd_map, cmd_providers, cmd_report

__all__ = [
    "HANDLERS",
    "TASK_OWNERS",
    "cmd_apply",
    "cmd_change",
    "cmd_map",
    "cmd_new",
    "cmd_plan",
    "cmd_providers",
    "cmd_report",
]

HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "new": cmd_new,
    "plan": cmd_plan,
    "apply": cmd_apply,
    "change": cmd_change,
    "map": cmd_map,
    "providers": cmd_providers,
    "report": cmd_report,
}

TASK_OWNERS: dict[str, str] = {
    "new": "T029",
    "change": "T044",
    "plan": "T032",
    "apply": "T035",
    "map": "T041",
    "report": "T065",
    "providers": "T056",
}
