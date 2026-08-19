# -*- coding: utf-8 -*-
"""Command bodies for the headless CLI. One function per subcommand, registered in `HANDLERS`.

Split out of `cli.py` so that module stays what its name promises - parser, dispatch, exit map -
while the work each command does lives here. An absent entry in `HANDLERS` is a deferral naming
its task, never a silent stub.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from cabal.dotnetgen import intent, ledger, map_cache, pipeline, reporting, runner, scaffold, state
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
from cabal.dotnetgen.stages import architect, route, write
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
    record = ledger.RunRecord(
        run_id=ledger.new_run_id(),
        project_path=str(project),
        template_id=state.load(project).template_id if state.exists(project) else "",
    )
    started = time.monotonic()
    try:
        run = runner.run_approved(
            project=project,
            intent=pending.intent,
            provider=provider,
            model=binding.model,
            budget=budget,
            record=record,
        )
    except (write.WriteError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_FAILURE
    except applier.UnsupportedDispositionError as exc:
        # Every disposition in the schema is now applied; this catches a disposition the schema
        # would have to grow to produce. Reported as a failure rather than an uncaught traceback.
        emit_error(args, str(exc))
        return EXIT_FAILURE

    if run.outcome is RunOutcome.COMPLETED:
        intent.clear(project)

    # Recorded for every outcome, not just success: a halted run is exactly the one whose cost a
    # developer needs to see, and dropping it would make repairs invisible in the totals.
    record.outcome = run.outcome.value
    record.wall_clock_seconds = time.monotonic() - started
    record.retry_budget = run.budget
    record.repair_attempts = ledger.repairs_from(run)
    record.edit_applications = [
        a for attempt in run.attempts for a in attempt.apply_report.applications
    ]
    record.first_attempt_build_green = bool(run.attempts) and run.attempts[0].passed
    written = ledger.write(project, record, provider_reported_usd=record.total_cost_usd)

    payload = _describe_run(run, pending.token)
    payload["run_id"] = record.run_id
    payload["record_path"] = str(written)
    payload["cost_usd"] = round(record.total_cost_usd, 6)
    emit_result(args, payload, _summarise_run(run))
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
        "history": list(run.history()),
        "detail": run.detail,
    }


def _summarise_run(run: pipeline.RunResult) -> str:
    tail = f"{run.budget.consumed}/{run.budget.ceiling} repair attempts consumed"
    if run.outcome is RunOutcome.COMPLETED:
        return f"applied and verified; {tail}"
    if run.outcome is RunOutcome.ABORTED_ENVIRONMENT:
        return (
            f"aborted on an environment failure; {tail} (none spent on it, by design)\n"
            + run.report()
        )
    # A halt is the case where the developer has to take over, so it gets the full history.
    return run.report()


def cmd_map(args: argparse.Namespace) -> int:
    """T041: render the structural map, reusing the cache when the solution has not changed."""
    project = Path(args.project)
    try:
        # `map` only reads the solution, but it does persist a cache file. Under --dry-run even
        # that is skipped, so the flag means the same thing everywhere: nothing on disk changes.
        rendered, built = map_cache.rendered_map(
            project, token_budget=args.budget, write_cache=not args.dry_run
        )
    except state.StateError as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    payload: dict[str, object] = {
        "status": "ok",
        "dry_run": bool(args.dry_run),
        "fingerprint": built.fingerprint,
        "token_budget": built.token_budget,
        "estimated_tokens": built.estimated_tokens,
        "types": len(built.entries),
        "omitted_count": built.omitted_count,
        "omitted_summary": built.omitted_summary,
        "map": rendered,
    }
    emit_result(args, payload, rendered)
    return EXIT_OK


def cmd_change(args: argparse.Namespace) -> int:
    """T044: route, then architect, then the gate, then write and verify.

    The route stage is why this is not just `plan` plus `apply`. Most turns are questions, and
    paying full pipeline cost to answer "what does this handler do?" is where naive tools burn
    money (SC-009). A question is answered and the pipeline never starts.

    A change still stops at the gate. `change` is the convenient front door, not a way around
    approval - FR-010e applies the gate uniformly, so this prints the intent and its token and
    leaves the decision to the developer.
    """
    project = Path(args.project)
    try:
        bindings = config.load_bindings(project)
        route_binding = bindings.for_stage("route")
        route_provider = factory.provider_for(route_binding)
    except (config.BindingsError, ProviderError) as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    decision = route.classify(args.request, route_provider, route_binding.model)
    if not decision.enters_pipeline:
        payload = {
            "status": "answered",
            "intent": decision.value,
            "request": args.request,
            "stages": {"architect": zero_stage(), "write": zero_stage()},
        }
        emit_result(
            args,
            payload,
            "This reads as a question, so nothing was written and the pipeline did not run. "
            "Re-run with a change request if that is wrong.",
        )
        return EXIT_OK

    return cmd_plan(args)


def cmd_providers(args: argparse.Namespace) -> int:
    """T056: show what each stage is bound to, and with --check whether it answers.

    Probing costs one token per provider and answers the question that otherwise only surfaces
    halfway through a run: is this configuration actually usable on this machine right now?
    """
    project = Path(args.project)
    try:
        bindings = config.load_bindings(project)
    except config.BindingsError as exc:
        emit_error(args, str(exc))
        return EXIT_USAGE

    stages: list[dict[str, object]] = []
    unreachable = 0
    for stage, binding in sorted(bindings.stages.items()):
        entry: dict[str, object] = {
            "stage": stage,
            "provider": binding.provider,
            "model": binding.model,
            "fallback": binding.fallback.provider if binding.fallback else None,
            "missing_api_key": binding.missing_key(),
        }
        if args.check:
            try:
                status = factory.provider_for(binding).check()
            except ProviderError as exc:
                entry["reachable"] = False
                entry["detail"] = str(exc)
            else:
                entry["reachable"] = status.reachable
                entry["detail"] = status.detail
            if not entry["reachable"]:
                unreachable += 1
        stages.append(entry)

    emit_result(
        args,
        {
            "status": "ok",
            "dry_run": bool(args.dry_run),
            "stages": stages,
            "unreachable": unreachable,
        },
        "\n".join(_provider_line(entry, args.check) for entry in stages),
    )
    # Reporting is the job; an unreachable provider is a finding, not a crash of this command.
    return EXIT_OK if not unreachable else EXIT_FAILURE


def _provider_line(entry: dict[str, object], checked: bool) -> str:
    parts = [f"{entry['stage']:<10} {entry['provider']}/{entry['model']}"]
    if entry["fallback"]:
        parts.append(f"(fallback: {entry['fallback']})")
    if entry["missing_api_key"]:
        parts.append("[api key not set]")
    if checked:
        parts.append("ok" if entry.get("reachable") else f"UNREACHABLE - {entry.get('detail', '')}")
    return " ".join(parts)


def cmd_report(args: argparse.Namespace) -> int:
    """T065: read back recorded runs and show what they cost."""
    project = Path(args.project)
    runs = reporting.load_runs(project)
    selected = reporting.select(runs, run_id=args.run, last=args.last)

    if args.run is not None and not selected:
        emit_error(args, f"no run recorded with id {args.run!r} in {project}")
        return EXIT_USAGE

    emit_result(
        args,
        {
            "status": "ok",
            "dry_run": bool(args.dry_run),
            "runs": [{"run_id": r.run_id, **r.payload} for r in selected],
            "summary": reporting.summarise(selected),
        },
        reporting.render(selected),
    )
    return EXIT_OK


HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "new": cmd_new,
    "plan": cmd_plan,
    "apply": cmd_apply,
    "map": cmd_map,
    "change": cmd_change,
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
