# -*- coding: utf-8 -*-
"""Assembles the concrete stages into a `Pipeline` and runs one approved intent.

`pipeline.py` deliberately knows nothing about providers, C#, or the filesystem - it holds the
loop, the gate and the ceiling, and takes its stages as callables. This module is where the real
writer, applier and verifier are bound to it, so that separation survives contact with the
concrete implementations.

The repair path is the reason this is worth stating explicitly: diagnostics from a failed build
are fed back to the **writing** stage only (FR-020). The architect is never re-run, so a repair
cannot re-decide the design, and cache bands 1-3 stay valid across every attempt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from cabal.dotnetgen import ledger, pipeline, state
from cabal.dotnetgen.edits import applier
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.pipeline import ChangeIntent, GateDecision, RetryBudget, RunResult
from cabal.dotnetgen.providers.base import Provider
from cabal.dotnetgen.stages import write
from cabal.dotnetgen.templates import registry
from cabal.dotnetgen.verify import dotnet

MAX_DIAGNOSTIC_CHARS: Final[int] = 4000
"""Build output is truncated before it reaches the model.

An unbounded MSBuild log would dominate the volatile band and cost more than the repair it is
meant to enable. The tail is kept because that is where the error summary lands.
"""


def run_approved(
    *,
    project: Path,
    intent: ChangeIntent,
    provider: Provider,
    model: str,
    budget: RetryBudget,
    record: ledger.RunRecord | None = None,
) -> RunResult:
    """Write, apply and verify an approved intent, repairing up to the ceiling.

    When a `record` is supplied every write-stage call is metered into it, and calls after the
    first are attributed as repair cost - that split is what stops a run that repairs three times
    from averaging out to look cheap (FR-029).
    """
    contract = _template_contract(project)
    write_calls = 0

    def writer(
        approved: ChangeIntent, last_failure: dotnet.VerificationResult | None
    ) -> tuple[EditOperation, ...]:
        nonlocal write_calls
        request = write.build_request(
            approved,
            model,
            template_contract=contract,
            diagnostics=_diagnostics(last_failure),
        )
        completion = provider.complete(request)
        write_calls += 1
        if record is not None:
            record.record_stage(
                ledger.StageCost(
                    stage="write",
                    provider=getattr(provider, "name", "unknown"),
                    model=completion.model or model,
                    usage=completion.usage,
                    wall_clock_seconds=completion.wall_clock_seconds,
                    priced=not ledger.prices_nothing(provider),
                    reported_cost_usd=completion.reported_cost_usd,
                ),
                is_repair=write_calls > 1,
            )
        return write.parse(completion.text, _read_targets(project, approved))

    written: set[str] = set()

    def apply(operations) -> applier.ApplyReport:
        report = applier.apply_all(project, tuple(operations))
        # Track what this run authored: `verify` needs it to tell "the tool broke the .csproj"
        # (repairable) from "the SDK is broken" (never repairable). Accumulates across attempts,
        # because a file written on attempt 1 is still this run's work on attempt 3.
        written.update(a.operation.file for a in report.landed)
        return report

    def verify() -> dotnet.VerificationResult:
        return dotnet.verify(project, written_files=frozenset(written))

    return pipeline.Pipeline(
        writer=writer, applier=apply, verifier=verify, budget=budget
    ).run(intent, GateDecision.APPROVED)


def _template_contract(project: Path) -> str | None:
    """The band-2 constant for this project, read from its locked template."""
    if not state.exists(project):
        return None
    return registry.get(state.load(project).template_id).contract_text()


def _read_targets(project: Path, intent: ChangeIntent) -> dict[str, str]:
    """Current contents of the files the intent names, for the no-op rewrite check."""
    contents: dict[str, str] = {}
    for relative in intent.target_files:
        path = project / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def _diagnostics(result: dotnet.VerificationResult | None) -> str | None:
    """Render a failed verification for the repair turn, truncated to its informative tail."""
    if result is None:
        return None
    combined = "\n\n".join(output.combined for output in result.outputs() if output.combined)
    if not combined:
        return result.detail or None
    if len(combined) > MAX_DIAGNOSTIC_CHARS:
        combined = "...[earlier output truncated]...\n" + combined[-MAX_DIAGNOSTIC_CHARS:]
    return combined
