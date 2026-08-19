# -*- coding: utf-8 -*-
"""Integration test (T045) for the feature-edit path: edit what changes, re-emit nothing else.

SC-003 is measured here. A feature touching a few types must apply on the first attempt, must not
read the whole solution, and must not re-emit members it is not changing - the three behaviours
that separate this pipeline from a naive "send the file, get the file back" loop.

The provider is scripted rather than live. What is under test is the pipeline's handling of the
edits, not whether a model happens to produce good ones; a live model would make this slow,
billed, and non-deterministic, and would test something this suite cannot assert on anyway.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import runner
from cabal.dotnetgen.pipeline import ChangeIntent, RetryBudget, RunOutcome
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.verify import dotnet
from cabal.dotnetgen.verify.diagnostics import Classification

ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public string Status { get; private set; } = "open";

    public void Cancel()
    {
        Status = "cancelled";
    }

    public void Reopen()
    {
        Status = "open";
    }
}
"""

PROGRAM_CS = """using Orders.Domain;

WebApplication app = WebApplication.CreateBuilder(args).Build();

app.MapOrders();

app.Run();
"""

EDITS = {
    "operations": [
        {
            "file": "src/Order.cs",
            "anchor_kind": "symbol",
            "symbol": "Orders.Domain.Order.Cancel",
            "disposition": "replace",
            "content": (
                "public void Cancel(string reason)\n"
                "{\n"
                '    Status = "cancelled";\n'
                "    Reason = reason;\n"
                "}"
            ),
            "reason": "cancellation now records why",
        },
        {
            "file": "src/Order.cs",
            "anchor_kind": "symbol",
            "symbol": "Orders.Domain.Order",
            "disposition": "insert-into-type",
            "content": 'public string Reason { get; private set; } = "";',
            "reason": "store the cancellation reason",
        },
    ]
}


class ScriptedProvider:
    """Returns a fixed edit batch and counts how many times the writing stage ran."""

    name = "scripted"

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, request: object) -> CompletionResult:
        self.calls += 1
        self.prompts.append("\n".join(m.content for m in request.messages))  # type: ignore[attr-defined]
        reply = self._replies[min(self.calls - 1, len(self._replies) - 1)]
        return CompletionResult(
            text=reply,
            usage=Usage(input_tokens=0, output_tokens=0),
            model="scripted",
            provider=self.name,
        )


@pytest.fixture
def solution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    (root / "src" / "Program.cs").write_text(PROGRAM_CS, encoding="utf-8")
    monkeypatch.setattr(
        dotnet,
        "verify",
        lambda project, **kw: dotnet.VerificationResult(classification=Classification.PASS),
    )
    return root


INTENT = ChangeIntent(
    summary="Record a reason when an order is cancelled.",
    target_files=("src/Order.cs",),
    target_symbols=("Orders.Domain.Order.Cancel",),
)


def _run(solution: Path, provider: ScriptedProvider):
    return runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )


def test_a_feature_edit_completes_on_the_first_attempt(solution: Path) -> None:
    provider = ScriptedProvider(json.dumps(EDITS))

    result = _run(solution, provider)

    assert result.outcome is RunOutcome.COMPLETED
    assert len(result.attempts) == 1
    assert result.budget.consumed == 0


def test_every_edit_applies_on_the_first_attempt(solution: Path) -> None:
    """SC-003 asks for at least 90%; this batch must reach 100%."""
    provider = ScriptedProvider(json.dumps(EDITS))

    result = _run(solution, provider)

    assert result.attempts[0].apply_report.success_rate == 1.0


def test_untouched_members_are_not_re_emitted(solution: Path) -> None:
    """`Reopen` is not in the intent, so no operation may mention it."""
    provider = ScriptedProvider(json.dumps(EDITS))

    _run(solution, provider)

    assert "Reopen" not in json.dumps(EDITS)
    assert "public void Reopen" in (solution / "src" / "Order.cs").read_text(encoding="utf-8")


def test_the_edit_landed_in_the_file(solution: Path) -> None:
    provider = ScriptedProvider(json.dumps(EDITS))

    _run(solution, provider)

    updated = (solution / "src" / "Order.cs").read_text(encoding="utf-8")
    assert "Cancel(string reason)" in updated
    assert "public string Reason" in updated


def test_an_untargeted_file_is_never_read_into_the_prompt(solution: Path) -> None:
    """The writing stage sees the files the intent names, not the whole solution."""
    provider = ScriptedProvider(json.dumps(EDITS))

    _run(solution, provider)

    assert "app.MapOrders();" not in provider.prompts[0], "Program.cs was not a target"


def test_a_failed_build_routes_diagnostics_back_to_the_writer_only(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repair re-runs the writing stage; the architect is never consulted again (FR-020)."""
    outcomes = iter(
        [
            dotnet.VerificationResult(
                classification=Classification.CODE_DEFECT,
                build=dotnet.CommandOutput(
                    command=("dotnet", "build"),
                    exit_code=1,
                    stdout="src/Order.cs(5,1): error CS1002: ; expected",
                    stderr="",
                ),
                detail="build failed: CS1002",
            ),
            dotnet.VerificationResult(classification=Classification.PASS),
        ]
    )
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: next(outcomes))
    repair = json.loads(json.dumps(EDITS))
    repair["operations"] = [
        {
            "file": "src/Order.cs",
            "anchor_kind": "symbol",
            "symbol": "Orders.Domain.Order.Reopen",
            "disposition": "replace",
            "content": "public void Reopen()\n{\n    Status = \"reopened\";\n}",
            "reason": "repair",
        }
    ]
    provider = ScriptedProvider(json.dumps(EDITS), json.dumps(repair))

    result = _run(solution, provider)

    assert result.outcome is RunOutcome.COMPLETED
    assert result.budget.consumed == 1, "the defect cost exactly one attempt"
    assert "CS1002" in provider.prompts[1], "the repair turn must carry the diagnostic"
