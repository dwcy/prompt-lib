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

from cabal.dotnetgen import intent, pipeline, runner, scaffold, state
from cabal.dotnetgen.edits import applier
from cabal.dotnetgen.exits import (
    EXIT_ENVIRONMENT_FAILURE,
    EXIT_FAILURE,
    EXIT_HALTED_AT_CEILING,
    EXIT_OK,
    EXIT_REJECTED_AT_GATE,
    EXIT_USAGE,
    emit_error,
    emit_result,
    zero_stage,
)
from cabal.dotnetgen.pipeline import IntentContainsCodeError, RetryBudget, RunOutcome
from cabal.dotnetgen.providers import config, factory
from cabal.dotnetgen.providers.base import ProviderError
from cabal.dotnetgen.stages import architect, write
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


def cmd_apply(args: argparse.Namespace) -> int:
    """T035: redeem an approved intent, write, verify, and repair under the ceiling.

    The gate is enforced first and unconditionally. A refused token returns before any provider
    is constructed, so a refused apply cannot spend a single token.
    """
    project = Path(args.project)
    try:
        pending = intent.redeem(project, args.intent_token)
    except intent.IntentError as exc:
        emit_error(args, str(exc))
        return EXIT_REJECTED_AT_GATE

    if args.dry_run:
        emit_result(
            args,
            {
                "status": "approved",
                "intent_token": pending.token,
                "intent": {"summary": pending.intent.summary},
                "stages": {"write": zero_stage()},
            },
            f"would apply: {pending.intent.summary}",
        )
        return EXIT_OK

    try:
        binding = config.load_bindings(project).for_stage("write")
        provider = factory.provider_for(binding)
    except (config.BindingsError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    budget = RetryBudget(ceiling=args.retry_ceiling)
    try:
        run = runner.run_approved(
            project=project,
            intent=pending.intent,
            provider=provider,
            model=binding.model,
            budget=budget,
        )
    except (write.WriteError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_FAILURE
    except applier.UnsupportedDispositionError as exc:
        # Phase 3 applies `create-file` only; the relaxation ladder and in-place edits are T042.
        # Surfaced as a plain failure naming the gap rather than an uncaught traceback.
        emit_error(args, f"{exc}; this run needed an edit kind Phase 3 cannot apply yet")
        return EXIT_FAILURE

    if run.outcome is RunOutcome.COMPLETED:
        intent.clear(project)

    emit_result(args, _describe_run(run, pending.token), _summarise_run(run))
    return _EXIT_FOR_OUTCOME[run.outcome]


_EXIT_FOR_OUTCOME: dict[RunOutcome, int] = {
    RunOutcome.COMPLETED: EXIT_OK,
    RunOutcome.HALTED_AT_CEILING: EXIT_HALTED_AT_CEILING,
    RunOutcome.ABORTED_ENVIRONMENT: EXIT_ENVIRONMENT_FAILURE,
    RunOutcome.REJECTED_AT_GATE: EXIT_REJECTED_AT_GATE,
}


def _describe_run(run: pipeline.RunResult, token: str) -> dict[str, object]:
    return {
        "status": run.outcome.value,
        "intent_token": token,
        "attempts": [
            {
                "number": a.number,
                "edits_landed": len(a.apply_report.landed),
                "edits_failed": len(a.apply_report.failed),
                "edit_success_rate": a.apply_report.success_rate,
                "verification": a.verification.classification.value,
                "detail": a.verification.detail,
            }
            for a in run.attempts
        ],
        "retry_budget": {
            "ceiling": run.budget.ceiling,
            "consumed": run.budget.consumed,
            "environment_aborts": run.budget.environment_aborts,
        },
    }


def _summarise_run(run: pipeline.RunResult) -> str:
    tail = f"{run.budget.consumed}/{run.budget.ceiling} repair attempts consumed"
    if run.outcome is RunOutcome.COMPLETED:
        return f"applied and verified; {tail}"
    if run.outcome is RunOutcome.ABORTED_ENVIRONMENT:
        return f"aborted on an environment failure; {tail} (none spent on it, by design)"
    return f"halted: {run.outcome.value}; {tail}"


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "new": cmd_new,
    "plan": cmd_plan,
    "apply": cmd_apply,
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
