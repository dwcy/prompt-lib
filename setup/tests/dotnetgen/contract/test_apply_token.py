# -*- coding: utf-8 -*-
"""Contract test (T033) for `apply`: a mismatched or stale token is refused with no mutation.

The approval gate is only load-bearing if it cannot be walked around. Three ways it could be,
all closed here:

* applying with a token that authorises a *different* intent (replay)
* applying after the solution moved on under the approval (drift)
* applying when nothing was ever approved

In every case the refusal must happen **before** any write, so a refused apply is indistinguishable
from an apply that never ran.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cabal.dotnetgen import cli, intent
from cabal.dotnetgen.pipeline import ChangeIntent
from cabal.dotnetgen.providers import factory

APPROVED = ChangeIntent(
    summary="Add a cancel endpoint to the Orders slice.",
    target_files=("src/Api/Features/Orders/CancelOrder.cs",),
)


class ExplodingProvider:
    """Any call means the gate let a write through. Fails the test loudly rather than silently."""

    name = "exploding"

    def complete(self, request: object) -> object:
        raise AssertionError("the writing stage ran despite a refused token")


@pytest.fixture
def approved_solution(solution_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solution with one source file and a recorded, still-valid approval."""
    (solution_dir / "src").mkdir()
    (solution_dir / "src" / "Existing.cs").write_text("// original\n", encoding="utf-8")
    intent.propose(solution_dir, "add a cancel endpoint", APPROVED)
    monkeypatch.setattr(factory, "provider_for", lambda binding: ExplodingProvider())
    return solution_dir


def _snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*")
        if p.is_file() and p.suffix in (".cs", ".csproj", ".sln")
    }


def test_mismatched_token_is_refused_without_mutation(approved_solution: Path) -> None:
    before = _snapshot(approved_solution)

    code = cli.main(
        [
            "apply",
            "--intent-token",
            "sha256:" + "0" * 64,
            "--project",
            str(approved_solution),
        ]
    )

    assert code == cli.EXIT_REJECTED_AT_GATE
    assert _snapshot(approved_solution) == before


def test_stale_token_is_refused_after_the_solution_moves(approved_solution: Path) -> None:
    """The approval was given against code that no longer exists."""
    token = intent.load_pending(approved_solution).token
    (approved_solution / "src" / "Drift.cs").write_text("// hand edit\n", encoding="utf-8")
    before = _snapshot(approved_solution)

    code = cli.main(
        ["apply", "--intent-token", token, "--project", str(approved_solution)]
    )

    assert code == cli.EXIT_REJECTED_AT_GATE
    assert _snapshot(approved_solution) == before


def test_apply_without_any_approval_is_refused(solution_dir: Path) -> None:
    code = cli.main(
        ["apply", "--intent-token", "sha256:" + "0" * 64, "--project", str(solution_dir)]
    )

    assert code == cli.EXIT_REJECTED_AT_GATE
    assert list(solution_dir.iterdir()) == []


def test_refusal_reports_the_reason_on_the_json_channel(
    approved_solution: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(
        [
            "apply",
            "--intent-token",
            "sha256:" + "0" * 64,
            "--project",
            str(approved_solution),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "token" in payload["error"].lower()


def test_a_refused_apply_leaves_the_approval_intact(approved_solution: Path) -> None:
    """A bad token must not consume the approval - the developer approved something real."""
    cli.main(
        ["apply", "--intent-token", "sha256:" + "0" * 64, "--project", str(approved_solution)]
    )

    assert intent.load_pending(approved_solution).intent.summary == APPROVED.summary
