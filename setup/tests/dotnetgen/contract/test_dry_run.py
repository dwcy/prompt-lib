# -*- coding: utf-8 -*-
"""Contract test (T069) for `--dry-run`: it must mean the same thing on every command.

The flag exists so a caller can rehearse without consequence. That is only useful if it is
absolute: nothing on disk changes, and no writing model is invoked. A flag that is honoured by
most commands is worse than no flag, because it invites trust it does not deserve.

Two separate promises, both pinned here:

  no writes   not the solution, not the pending intent, not the run ledger, not even the map cache
  no spend    the writing stage is never called, so a rehearsal cannot cost output tokens
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, intent
from cabal.dotnetgen.pipeline import ChangeIntent
from cabal.dotnetgen.providers import factory
from cabal.dotnetgen.providers.base import CompletionResult, Usage

ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public void Cancel()
    {
    }
}
"""

APPROVED = ChangeIntent(summary="Add a cancel reason.", target_files=("src/Order.cs",))

PROSE = json.dumps(
    {
        "summary": "Add a reason parameter to cancellation.",
        "target_files": ["src/Order.cs"],
        "target_symbols": ["Orders.Domain.Order.Cancel"],
        "rationale": "The reason belongs with the state change.",
    }
)


class CountingProvider:
    """Answers the architect, and records every call so a spend can be detected."""

    name = "counting"
    is_local = False
    calls = 0

    def complete(self, request: object) -> CompletionResult:
        type(self).calls += 1
        return CompletionResult(
            text=PROSE, usage=Usage(), model="counting", provider=self.name
        )


@pytest.fixture
def solution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    CountingProvider.calls = 0
    monkeypatch.setattr(factory, "provider_for", lambda binding: CountingProvider())
    return root


def _snapshot(root: Path) -> dict[str, float]:
    return {
        p.relative_to(root).as_posix(): p.stat().st_mtime
        for p in root.rglob("*")
        if p.is_file()
    }


def test_new_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "service"

    code = cli.main(
        ["new", "--description", "an order service", "--project", str(target), "--dry-run", "--json"]
    )

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "planned"
    assert not target.exists(), "a rehearsal must not even create the directory"


def test_plan_records_no_pending_intent(solution: Path) -> None:
    code = cli.main(
        ["plan", "--request", "add a reason", "--project", str(solution), "--dry-run"]
    )

    assert code == cli.EXIT_OK
    assert not intent.pending_path(solution).exists()


def test_plan_dry_run_returns_no_token(
    solution: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A rehearsal must not hand back something `apply` would accept."""
    cli.main(
        ["plan", "--request", "add a reason", "--project", str(solution), "--dry-run", "--json"]
    )

    assert json.loads(capsys.readouterr().out)["intent_token"] is None


def test_apply_changes_no_file_and_calls_no_writing_model(solution: Path) -> None:
    pending = intent.propose(solution, "add a reason", APPROVED)
    CountingProvider.calls = 0
    before = _snapshot(solution)

    code = cli.main(
        ["apply", "--intent-token", pending.token, "--project", str(solution), "--dry-run"]
    )

    assert code == cli.EXIT_OK
    assert _snapshot(solution) == before
    assert CountingProvider.calls == 0, "a rehearsal must not spend output tokens"


def test_apply_dry_run_writes_no_run_record(solution: Path) -> None:
    pending = intent.propose(solution, "add a reason", APPROVED)

    cli.main(["apply", "--intent-token", pending.token, "--project", str(solution), "--dry-run"])

    assert not (solution / ".dotnetgen" / "runs").exists()


def test_apply_dry_run_leaves_the_approval_unspent(solution: Path) -> None:
    """Rehearsing must not consume the approval the developer gave."""
    pending = intent.propose(solution, "add a reason", APPROVED)

    cli.main(["apply", "--intent-token", pending.token, "--project", str(solution), "--dry-run"])

    assert intent.load_pending(solution).token == pending.token


def test_map_writes_no_cache_file(solution: Path) -> None:
    cli.main(["map", "--project", str(solution), "--dry-run"])

    assert not (solution / ".dotnetgen" / "map-cache").exists()


def test_map_still_produces_the_map(solution: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No writes is not the same as no answer - a rehearsal still has to be useful."""
    cli.main(["map", "--project", str(solution), "--dry-run", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert "Order" in payload["map"]


def test_the_flag_is_reported_so_a_caller_can_prove_it_was_a_rehearsal(
    solution: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["report", "--project", str(solution), "--dry-run", "--json"])

    assert json.loads(capsys.readouterr().out)["dry_run"] is True


@pytest.mark.parametrize(
    "argv",
    [
        ["new", "--description", "x"],
        ["plan", "--request", "x"],
        ["change", "--request", "x"],
        ["apply", "--intent-token", "sha256:0"],
        ["map"],
        ["report"],
        ["providers"],
    ],
)
def test_every_command_accepts_the_flag(argv: list[str]) -> None:
    """A flag honoured by most commands invites trust it does not deserve."""
    parsed = cli.build_parser().parse_args([*argv, "--dry-run"])

    assert parsed.dry_run is True
