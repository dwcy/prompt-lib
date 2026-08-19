# -*- coding: utf-8 -*-
"""Contract test (T051) for the repair ceiling and its exit codes.

SC-007 is the promise that this tool cannot do what the frontend codegen tools are documented
doing - charging full price to fix their own breakage, indefinitely. Two numbers carry it, and
the skill reads both off the exit code:

  exit 3  the ceiling was reached; `consumed == ceiling`, and the run stopped rather than spending
  exit 4  the environment broke; `consumed == 0`, because regenerating C# cannot install an SDK

The second is the one that matters most. A tool that spent its budget retrying a missing NuGet
feed would burn the whole allowance and still fail, which is the runaway loop in a different hat.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, intent, runner
from cabal.dotnetgen.pipeline import ChangeIntent, RetryBudget, RunOutcome
from cabal.dotnetgen.providers import factory
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.verify import dotnet
from cabal.dotnetgen.verify.diagnostics import Classification

APPROVED = ChangeIntent(summary="Add a cancel reason.", target_files=("src/Order.cs",))

ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public void Cancel()
    {
    }
}
"""

EDIT = json.dumps(
    {
        "operations": [
            {
                "file": "src/Order.cs",
                "anchor_kind": "symbol",
                "symbol": "Orders.Domain.Order.Cancel",
                "disposition": "replace",
                "content": "public void Cancel(string reason)\n{\n}",
                "reason": "add a reason",
            }
        ]
    }
)


class LoopingProvider:
    """Always returns the same edit, so only the ceiling can end the run."""

    name = "looping"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: object) -> CompletionResult:
        self.calls += 1
        # Alternate the content so the applier never rejects it as a no-op rewrite.
        content = "public void Cancel(string reason" + ("s" * self.calls) + ")\n{\n}"
        payload = json.loads(EDIT)
        payload["operations"][0]["content"] = content
        payload["operations"][0]["symbol"] = "Orders.Domain.Order.Cancel"
        return CompletionResult(
            text=json.dumps(payload),
            usage=Usage(),
            model="looping",
            provider=self.name,
        )


@pytest.fixture
def solution(tmp_path: Path) -> Path:
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    return root


def _defect() -> dotnet.VerificationResult:
    return dotnet.VerificationResult(
        classification=Classification.CODE_DEFECT,
        build=dotnet.CommandOutput(
            command=("dotnet", "build"),
            exit_code=1,
            stdout="src/Order.cs(5,1): error CS1002: ; expected",
            stderr="",
        ),
        detail="build failed: CS1002",
    )


def _environment() -> dotnet.VerificationResult:
    return dotnet.VerificationResult(
        classification=Classification.ENVIRONMENT_FAILURE,
        build=dotnet.CommandOutput(
            command=("dotnet", "build"),
            exit_code=1,
            stdout="error NU1101: Unable to find package Foo",
            stderr="",
        ),
        detail="build failed: NU1101",
    )


def test_persistent_defects_halt_at_the_ceiling_having_spent_exactly_it(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _defect())

    result = runner.run_approved(
        project=solution,
        intent=APPROVED,
        provider=LoopingProvider(),
        model="looping",
        budget=RetryBudget(ceiling=3),
    )

    assert result.outcome is RunOutcome.HALTED_AT_CEILING
    assert result.budget.consumed == result.budget.ceiling == 3


def test_an_environment_failure_aborts_having_spent_nothing(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _environment())

    result = runner.run_approved(
        project=solution,
        intent=APPROVED,
        provider=LoopingProvider(),
        model="looping",
        budget=RetryBudget(ceiling=3),
    )

    assert result.outcome is RunOutcome.ABORTED_ENVIRONMENT
    assert result.budget.consumed == 0


def test_a_halted_run_exits_three(
    solution: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _defect())
    monkeypatch.setattr(factory, "provider_for", lambda binding: LoopingProvider())
    pending = intent.propose(solution, "add a cancel reason", APPROVED)

    code = cli.main(
        ["apply", "--intent-token", pending.token, "--project", str(solution), "--json"]
    )

    assert code == cli.EXIT_HALTED_AT_CEILING
    payload = json.loads(capsys.readouterr().out)
    assert payload["retry_budget"]["consumed"] == payload["retry_budget"]["ceiling"]


def test_an_environment_abort_exits_four(
    solution: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _environment())
    monkeypatch.setattr(factory, "provider_for", lambda binding: LoopingProvider())
    pending = intent.propose(solution, "add a cancel reason", APPROVED)

    code = cli.main(
        ["apply", "--intent-token", pending.token, "--project", str(solution), "--json"]
    )

    assert code == cli.EXIT_ENVIRONMENT_FAILURE
    payload = json.loads(capsys.readouterr().out)
    assert payload["retry_budget"]["consumed"] == 0


def test_a_halted_run_keeps_its_approval_so_the_work_is_not_lost(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The developer approved something real; a halt is not a reason to make them approve again."""
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _defect())
    monkeypatch.setattr(factory, "provider_for", lambda binding: LoopingProvider())
    intent.propose(solution, "add a cancel reason", APPROVED)

    cli.main(["apply", "--intent-token", intent.load_pending(solution).token, "--project", str(solution)])

    assert intent.load_pending(solution).intent.summary == APPROVED.summary


def test_a_zero_ceiling_allows_no_repair_at_all(
    solution: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dotnet, "verify", lambda project, **kw: _defect())

    result = runner.run_approved(
        project=solution,
        intent=APPROVED,
        provider=LoopingProvider(),
        model="looping",
        budget=RetryBudget(ceiling=0),
    )

    assert result.outcome is RunOutcome.HALTED_AT_CEILING
    assert len(result.attempts) == 1
