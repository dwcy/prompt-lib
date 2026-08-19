# -*- coding: utf-8 -*-
"""Contract test (T031) for the approval gate: `plan` mutates nothing and costs almost nothing.

SC-011 has two halves and both are pinned here. No run writes code before the developer approves
its stated intent, and **a rejected plan costs less than 10% of a completed run** - the second
half is what makes the gate worth having. A gate that cost as much as the change it prevents
would just be a slower way to spend the same money.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, intent
from cabal.dotnetgen.providers import factory
from cabal.dotnetgen.pipeline import ChangeIntent, IntentContainsCodeError
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.stages import architect

class RecordingProvider:
    """A provider that answers from a script and counts what it was asked to spend."""

    name = "recording"

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.requests: list[object] = []
        self.output_tokens = 0

    def complete(self, request: object) -> CompletionResult:
        self.requests.append(request)
        reply = self._replies.pop(0)
        self.output_tokens += len(reply.split())
        return CompletionResult(
            text=reply,
            usage=Usage(input_tokens=0, output_tokens=len(reply.split())),
            model="stub",
            provider=self.name,
        )


PROSE_INTENT = json.dumps(
    {
        "summary": "Add a cancel endpoint to the Orders slice and record the cancellation reason.",
        "target_files": ["src/Api/Features/Orders/CancelOrder.cs"],
        "target_symbols": ["Api.Features.Orders.CancelOrder"],
        "rationale": "Cancellation is a Command, so it gets its own handler beside the queries.",
    }
)


def test_architect_emits_prose_that_survives_the_gate() -> None:
    provider = RecordingProvider(PROSE_INTENT)

    proposed = architect.propose("add a cancel endpoint", provider, "stub")

    assert isinstance(proposed, ChangeIntent)
    assert "cancel" in proposed.summary.lower()
    assert proposed.target_files == ("src/Api/Features/Orders/CancelOrder.cs",)


def test_intent_containing_code_is_refused() -> None:
    """The gate approves a description. Code in the intent means the tokens were already spent."""
    with pytest.raises(IntentContainsCodeError):
        ChangeIntent(summary="Add this: public sealed class CancelOrder { }")


def test_architect_corrects_once_when_the_model_emits_code() -> None:
    """One bounded correction, then the prose intent - and the retry budget is never touched."""
    with_code = json.dumps({"summary": "Add public sealed class CancelOrder to the slice."})
    provider = RecordingProvider(with_code, PROSE_INTENT)

    proposed = architect.propose("add a cancel endpoint", provider, "stub")

    assert len(provider.requests) == 2, "exactly one correction, not an unbounded loop"
    assert "public sealed class" not in proposed.summary


def test_architect_does_not_retry_forever_on_persistent_code() -> None:
    with_code = json.dumps({"summary": "Add public sealed class CancelOrder to the slice."})
    provider = RecordingProvider(with_code, with_code)

    with pytest.raises(IntentContainsCodeError):
        architect.propose("add a cancel endpoint", provider, "stub")

    assert len(provider.requests) == 2, "the correction is attempted once and only once"


@pytest.fixture
def stub_architect(monkeypatch: pytest.MonkeyPatch) -> RecordingProvider:
    """Bind the architect stage to a scripted provider.

    Without this the contract test calls the live `claude` CLI - slow, non-deterministic, and
    billed. What is under test here is the gate's behaviour, not the model's.
    """
    provider = RecordingProvider(PROSE_INTENT)
    monkeypatch.setattr(factory, "provider_for", lambda binding: provider)
    return provider


def test_plan_writes_no_code(solution_dir: Path, stub_architect: RecordingProvider) -> None:
    """SC-011's first half: nothing is written before approval.

    `plan` does record the pending intent under `.dotnetgen/` - `apply` has to validate the token
    against *something*, and a token nothing can be checked against is not a gate. The rule the
    contract enforces is therefore precise: no source file is created, and none is modified.
    """
    (solution_dir / "src").mkdir()
    existing = solution_dir / "src" / "Untouched.cs"
    existing.write_text("// original\n", encoding="utf-8")

    cli.main(["plan", "--request", "add a cancel endpoint", "--project", str(solution_dir)])

    assert existing.read_text(encoding="utf-8") == "// original\n"
    written = {
        p.relative_to(solution_dir).as_posix()
        for p in solution_dir.rglob("*")
        if p.is_file() and p.suffix in (".cs", ".csproj", ".sln")
    }
    assert written == {"src/Untouched.cs"}, "plan must not author source"


def test_plan_reports_zero_write_stage_cost(
    solution_dir: Path, stub_architect: RecordingProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    """A plan that never reached the writing stage must report that stage's cost as zero."""
    code = cli.main(
        ["plan", "--request", "add a cancel endpoint", "--project", str(solution_dir), "--json"]
    )
    assert code == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["stages"]["write"]["output_tokens"] == 0
    assert payload["stages"]["write"]["cost"] == 0
    assert payload["intent_token"].startswith("sha256:")


def test_intent_token_is_bound_to_the_solution_and_cannot_be_replayed(
    solution_dir: Path, stub_architect: RecordingProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    """Approval authorises one change against one solution state - both, not either."""
    cli.main(
        ["plan", "--request", "add a cancel endpoint", "--project", str(solution_dir), "--json"]
    )
    token = json.loads(capsys.readouterr().out)["intent_token"]

    assert intent.redeem(solution_dir, token).token == token

    with pytest.raises(intent.StaleIntentError):
        intent.redeem(solution_dir, "sha256:" + "0" * 64)

    (solution_dir / "Drift.cs").write_text("// hand edit after approval\n", encoding="utf-8")
    with pytest.raises(intent.StaleIntentError):
        intent.redeem(solution_dir, token)
