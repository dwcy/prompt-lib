# -*- coding: utf-8 -*-
"""Contract test (T066) for the `--json` surface every command exposes.

The `/dotnet-codegen` skill parses this output, which makes it a wire contract rather than a
convenience. Three rules hold for every command without exception:

  * exactly one JSON object on stdout, and nothing else there
  * every human-readable byte on stderr, so a caller can pipe stdout safely
  * a `status` field on every payload, success or failure alike

The run record has its own JSON Schema, so it is validated against it rather than spot-checked.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from cabal.dotnetgen import cli, intent, ledger
from cabal.dotnetgen.pipeline import ChangeIntent, RetryBudget, RunOutcome
from cabal.dotnetgen.providers import factory
from cabal.dotnetgen.providers.base import CompletionResult, Usage
from cabal.dotnetgen.verify import dotnet
from cabal.dotnetgen.verify.diagnostics import Classification

ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public void Cancel()
    {
    }
}
"""

APPROVED = ChangeIntent(summary="Add a cancel reason.", target_files=("src/Order.cs",))

EDIT = json.dumps(
    {
        "operations": [
            {
                "file": "src/Order.cs",
                "anchor_kind": "symbol",
                "symbol": "Orders.Domain.Order.Cancel",
                "disposition": "replace",
                "content": "public void Cancel(string reason)\n{\n}",
                "reason": "record the reason",
            }
        ]
    }
)


class EditingProvider:
    name = "editing"
    is_local = False

    def complete(self, request: object) -> CompletionResult:
        return CompletionResult(
            text=EDIT,
            usage=Usage(input_tokens=100, output_tokens=50, cached_input_tokens=40),
            model="claude-sonnet-4",
            provider=self.name,
        )


@pytest.fixture
def applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A solution with one completed run already recorded."""
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    monkeypatch.setattr(
        dotnet,
        "verify",
        lambda project, **kw: dotnet.VerificationResult(classification=Classification.PASS),
    )
    monkeypatch.setattr(factory, "provider_for", lambda binding: EditingProvider())
    pending = intent.propose(root, "add a cancel reason", APPROVED)
    assert cli.main(["apply", "--intent-token", pending.token, "--project", str(root)]) == cli.EXIT_OK
    return root


def _json_only(capsys: pytest.CaptureFixture[str]) -> dict:
    captured = capsys.readouterr()
    assert captured.out.count("\n") == 1, "exactly one line, so exactly one object"
    return json.loads(captured.out)


def test_apply_emits_one_object_with_a_status(
    applied: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["report", "--project", str(applied), "--json"])

    assert _json_only(capsys)["status"] == "ok"


def test_report_returns_the_recorded_run(applied: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["report", "--project", str(applied), "--json"])

    payload = _json_only(capsys)
    assert payload["summary"]["runs"] == 1
    assert payload["runs"][0]["outcome"] == RunOutcome.COMPLETED.value


def test_the_recorded_run_validates_against_the_schema(
    applied: Path, run_record_schema: dict
) -> None:
    """The record `apply` writes is the same shape the ledger's own tests validate."""
    for run in ledger_records(applied):
        jsonschema.validate(run, run_record_schema)


def ledger_records(project: Path) -> list[dict]:
    directory = project / ledger.RUNS_RELDIR
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


def test_a_completed_run_reconciles(applied: Path) -> None:
    """Token aggregates must tie out against the individual calls that produced them."""
    for run in ledger_records(applied):
        assert run["derived"]["reconciled"] is True


def test_report_on_an_unknown_run_id_is_a_usage_error(
    applied: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["report", "--run", "nope", "--project", str(applied), "--json"])

    assert code == cli.EXIT_USAGE
    assert _json_only(capsys)["status"] == "error"


def test_report_on_a_project_with_no_runs_still_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["report", "--project", str(tmp_path), "--json"])

    assert code == cli.EXIT_OK
    assert _json_only(capsys)["summary"]["runs"] == 0


def test_providers_emits_one_object(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["providers", "--project", str(tmp_path), "--json"])

    assert "stages" in _json_only(capsys)


def test_map_emits_one_object(applied: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["map", "--project", str(applied), "--json"])

    assert _json_only(capsys)["status"] == "ok"


def test_human_output_never_touches_stdout(applied: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["report", "--project", str(applied)])

    captured = capsys.readouterr()
    assert captured.out == "", "without --json, stdout stays empty for pipe safety"
    assert captured.err.strip() != ""


def test_a_halted_run_is_recorded_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run whose cost matters most must not be the one that goes unrecorded."""
    root = tmp_path / "solution"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Order.cs").write_text(ORDER_CS, encoding="utf-8")
    monkeypatch.setattr(
        dotnet,
        "verify",
        lambda project, **kw: dotnet.VerificationResult(
            classification=Classification.CODE_DEFECT,
            build=dotnet.CommandOutput(
                command=("dotnet", "build"),
                exit_code=1,
                stdout="src/Order.cs(1,1): error CS1002: ; expected",
                stderr="",
            ),
            detail="build failed: CS1002",
        ),
    )

    calls = {"n": 0}

    class Varying(EditingProvider):
        def complete(self, request: object) -> CompletionResult:
            calls["n"] += 1
            payload = json.loads(EDIT)
            payload["operations"][0]["content"] = (
                f"public void Cancel(string reason{'x' * calls['n']})\n{{\n}}"
            )
            return CompletionResult(
                text=json.dumps(payload),
                usage=Usage(input_tokens=10, output_tokens=5),
                model="claude-sonnet-4",
                provider="editing",
            )

    monkeypatch.setattr(factory, "provider_for", lambda binding: Varying())
    pending = intent.propose(root, "add a cancel reason", APPROVED)

    code = cli.main(
        ["apply", "--intent-token", pending.token, "--project", str(root), "--retry-ceiling", "1"]
    )

    assert code == cli.EXIT_HALTED_AT_CEILING
    records = ledger_records(root)
    assert len(records) == 1
    assert records[0]["outcome"] == RunOutcome.HALTED_AT_CEILING.value
    assert records[0]["retry_budget"]["consumed"] == 1
