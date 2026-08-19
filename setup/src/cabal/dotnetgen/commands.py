# -*- coding: utf-8 -*-
"""Command bodies for the headless CLI. One function per subcommand, registered in `HANDLERS`.

Split out of `cli.py` so that module stays what its name promises - parser, dispatch, exit map -
while the work each command does lives here. An absent entry in `HANDLERS` is a deferral naming
its task, never a silent stub.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from cabal.dotnetgen import intent, scaffold, state
from cabal.dotnetgen.exits import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    emit_error,
    emit_result,
    zero_stage,
)
from cabal.dotnetgen.pipeline import IntentContainsCodeError
from cabal.dotnetgen.providers import config, factory
from cabal.dotnetgen.providers.base import ProviderError
from cabal.dotnetgen.stages import architect
from cabal.dotnetgen.templates import registry


def cmd_new(args: argparse.Namespace) -> int:
    """T029: scaffold from the locked template so the solution builds before any model writes."""
    target = Path(args.out or args.project)
    try:
        plan = scaffold.plan(target, args.template)
    except registry.TemplateError as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    if args.dry_run:
        emit_result(
            args,
            plan.describe(),
            f"would scaffold {plan.template.display_name} into {plan.target} "
            f"({len(plan.template.project_layout)} projects); nothing written",
        )
        return EXIT_OK

    try:
        result = scaffold.execute(plan)
    except (scaffold.ScaffoldError, state.StateError) as exc:
        emit_error(args, str(exc))
        output = getattr(exc, "output", None)
        if output is not None and not getattr(args, "json", False):
            print(output.combined)
        return EXIT_FAILURE

    emit_result(
        args,
        result.describe(),
        f"created {plan.template.display_name} at {plan.target}; solution builds",
    )
    return EXIT_OK


def cmd_plan(args: argparse.Namespace) -> int:
    """T032: architect only. Proposes an intent, mints its token, and stops before writing."""
    project = Path(args.project)
    try:
        binding = config.load_bindings(project).for_stage("architect")
        provider = factory.provider_for(binding)
    except (config.BindingsError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    try:
        proposed = architect.propose(args.request, provider, binding.model)
    except (architect.ArchitectError, IntentContainsCodeError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_FAILURE

    payload: dict[str, object] = {
        "status": "planned",
        "request": args.request,
        "intent": {
            "summary": proposed.summary,
            "target_files": list(proposed.target_files),
            "target_symbols": list(proposed.target_symbols),
            "rationale": proposed.rationale,
        },
        # SC-011: a plan never reaches the writing stage, so its cost is zero by construction.
        "stages": {"architect": zero_stage(), "write": zero_stage()},
    }

    if args.dry_run:
        payload["intent_token"] = None
        emit_result(args, payload, f"would propose: {proposed.summary}")
        return EXIT_OK

    try:
        pending = intent.propose(project, args.request, proposed)
    except OSError as exc:
        emit_error(args, f"could not record the pending intent: {exc}")
        return EXIT_FAILURE

    payload["intent_token"] = pending.token
    payload["fingerprint"] = pending.fingerprint
    emit_result(
        args,
        payload,
        f"{proposed.summary}\n\napprove with: apply --intent-token {pending.token}",
    )
    return EXIT_OK


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {"new": cmd_new, "plan": cmd_plan}

TASK_OWNERS: dict[str, str] = {
    "new": "T029",
    "change": "T044",
    "plan": "T032",
    "apply": "T035",
    "map": "T041",
    "report": "T065",
    "providers": "T056",
}
