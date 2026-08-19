# -*- coding: utf-8 -*-
"""Integration test (T052) for the repair loop: it fixes what it can and stops when it cannot.

SC-007 in full. A compile error the tool caused is repaired inside the budget. A failure it can
never fix halts, reports every attempt it made, and leaves the working tree alone so the partial
work can be inspected rather than silently discarded (FR-023).

The point of testing the whole loop rather than the budget arithmetic alone is the routing: the
diagnostic must reach the *writing* stage on the repair turn. If it reached the architect instead,
the design would be re-decided and the cached prefix thrown away on every repair.
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
    public void Cancel()
    {
        Status = "cancelled";
    }
}
"""

INTENT = ChangeIntent(
    summary="Record why an order was cancelled.",
    target_files=("src/Order.cs",),
    target_symbols=("Orders.Domain.Order.Cancel",),
)


def _edit(content: str) -> str:
    return json.dumps(
        {
            "operations": [
                {
                    "file": "src/Order.cs",
                    "anchor_kind": "symbol",
                    "symbol": "Orders.Domain.Order.Cancel",
                    "disposition": "replace",
                    "content": content,
                    "reason": "cancellation reason",
                }
            ]
        }
    )


BROKEN = _edit('public void Cancel(string reason)\n{\n    Status = "cancelled"\n}')
FIXED = _edit('public void Cancel(string reason)\n{\n    Status = "cancelled";\n}')


class ScriptedProvider:
    """Replies from a script, recording each prompt so routing can be asserted."""

    name = "scripted"

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, request: object) -> CompletionResult:
        index = min(len(self.prompts), len(self._replies) - 1)
        self.prompts.append("\n".join(m.content for m in request.messages))  # type: ignore[attr-defined]
        return CompletionResult(
            text=self._replies[index], usage=Usage(), model="scripted", provider=self.name
        )


@pytest.fixture
def solution(tmp_path: Path) -> Path:
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    return root


def _compile_error() -> dotnet.VerificationResult:
    return dotnet.VerificationResult(
        classification=Classification.CODE_DEFECT,
        build=dotnet.CommandOutput(
            command=("dotnet", "build"),
            exit_code=1,
            stdout="src/Order.cs(6,30): error CS1002: ; expected",
            stderr="",
        ),
        detail="build failed: CS1002",
    )


def test_an_injected_compile_error_is_repaired_within_budget(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcomes = iter([_compile_error(), dotnet.VerificationResult(classification=Classification.PASS)])
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: next(outcomes))
    provider = ScriptedProvider(BROKEN, FIXED)

    result = runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )

    assert result.outcome is RunOutcome.COMPLETED
    assert result.budget.consumed == 1, "one defect costs exactly one attempt"


def test_the_repair_turn_carries_the_diagnostic_to_the_writing_stage(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcomes = iter([_compile_error(), dotnet.VerificationResult(classification=Classification.PASS)])
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: next(outcomes))
    provider = ScriptedProvider(BROKEN, FIXED)

    runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )

    assert "CS1002" not in provider.prompts[0], "the first turn has no failure to report yet"
    assert "CS1002" in provider.prompts[1]


def test_the_repaired_file_is_correct_on_disk(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcomes = iter([_compile_error(), dotnet.VerificationResult(classification=Classification.PASS)])
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: next(outcomes))

    runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=ScriptedProvider(BROKEN, FIXED),
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )

    assert 'Status = "cancelled";' in (solution / "src" / "Order.cs").read_text(encoding="utf-8")


def test_an_unfixable_failure_halts_and_reports_every_attempt(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _compile_error())
    # Vary the content each turn so the applier never rejects a repeat as a no-op.
    provider = ScriptedProvider(
        _edit("public void Cancel(string a)\n{\n}"),
        _edit("public void Cancel(string ab)\n{\n}"),
        _edit("public void Cancel(string abc)\n{\n}"),
        _edit("public void Cancel(string abcd)\n{\n}"),
    )

    result = runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )

    assert result.outcome is RunOutcome.HALTED_AT_CEILING
    assert len(result.history()) == 4, "the initial attempt plus three repairs"
    assert all("CS1002" in line for line in result.history())


def test_the_halt_report_says_the_tree_was_left_for_inspection(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _compile_error())
    provider = ScriptedProvider(
        _edit("public void Cancel(string a)\n{\n}"),
        _edit("public void Cancel(string ab)\n{\n}"),
        _edit("public void Cancel(string abc)\n{\n}"),
        _edit("public void Cancel(string abcd)\n{\n}"),
    )

    result = runner.run_approved(
        project=solution,
        intent=INTENT,
        provider=provider,
        model="scripted",
        budget=RetryBudget(ceiling=3),
    )

    assert "inspected" in result.report()
    assert (solution / "src" / "Order.cs").is_file(), "the partial work is not rolled back"
