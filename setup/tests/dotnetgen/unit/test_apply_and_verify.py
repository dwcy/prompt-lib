# -*- coding: utf-8 -*-
"""Unit tests for edit application and for the .NET verification wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from cabal.dotnetgen.edits import applier
from cabal.dotnetgen.edits.model import EditOperation
from cabal.dotnetgen.verify import dotnet


def _create(file: str, content: str = "namespace Orders.Domain;\n") -> EditOperation:
    return EditOperation(
        file=file,
        anchor_kind="symbol",
        disposition="create-file",
        symbol="Orders.Domain.Thing",
        content=content,
    )


# --- applying create-file ------------------------------------------------------------------


def test_creating_a_file_writes_its_content(solution_dir: Path) -> None:
    applier.apply_operation(solution_dir, _create("src/Order.cs", "// order\n"))

    assert (solution_dir / "src/Order.cs").read_text(encoding="utf-8") == "// order\n"


def test_creating_a_file_reports_success(solution_dir: Path) -> None:
    record = applier.apply_operation(solution_dir, _create("src/Order.cs"))

    assert record.outcome is applier.ApplyOutcome.APPLIED


def test_creating_a_file_creates_missing_directories(solution_dir: Path) -> None:
    applier.apply_operation(solution_dir, _create("src/Features/Cancel/Handler.cs"))

    assert (solution_dir / "src/Features/Cancel/Handler.cs").is_file()


def test_content_is_written_with_unix_line_endings(solution_dir: Path) -> None:
    """Platform newline translation would make every generated file look modified."""
    applier.apply_operation(solution_dir, _create("src/Order.cs", "line one\nline two\n"))

    assert b"\r\n" not in (solution_dir / "src/Order.cs").read_bytes()


def test_creating_over_an_existing_file_is_refused(solution_dir: Path) -> None:
    (solution_dir / "src").mkdir()
    (solution_dir / "src/Order.cs").write_text("existing", encoding="utf-8")

    record = applier.apply_operation(solution_dir, _create("src/Order.cs"))

    assert record.outcome is applier.ApplyOutcome.FAILED


def test_refused_overwrite_leaves_the_original_intact(solution_dir: Path) -> None:
    (solution_dir / "src").mkdir()
    (solution_dir / "src/Order.cs").write_text("existing", encoding="utf-8")

    applier.apply_operation(solution_dir, _create("src/Order.cs"))

    assert (solution_dir / "src/Order.cs").read_text(encoding="utf-8") == "existing"


def test_path_escaping_the_project_is_refused(solution_dir: Path) -> None:
    record = applier.apply_operation(solution_dir, _create("../outside.cs"))

    assert record.outcome is applier.ApplyOutcome.FAILED


ORDER_CS = """namespace Orders.Domain;

public sealed class Order
{
    public void Cancel()
    {
        Status = "cancelled";
    }
}
"""


def _write_order(solution_dir: Path) -> Path:
    target = solution_dir / "src" / "Order.cs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(ORDER_CS, encoding="utf-8")
    return target


def test_replacing_a_member_by_symbol_rewrites_only_that_member(solution_dir: Path) -> None:
    target = _write_order(solution_dir)
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="replace",
        symbol="Orders.Domain.Order.Cancel",
        content='public void Cancel()\n{\n    Status = "void";\n}',
    )

    record = applier.apply_operation(solution_dir, operation)

    assert record.outcome is applier.ApplyOutcome.APPLIED
    updated = target.read_text(encoding="utf-8")
    assert '"void"' in updated
    assert "public sealed class Order" in updated, "the surrounding type must survive untouched"


def test_a_symbol_edit_survives_reformatting_between_write_and_apply(solution_dir: Path) -> None:
    """The anchor is re-resolved against current text, which is why `dotnet format` is harmless."""
    target = _write_order(solution_dir)
    target.write_text(ORDER_CS.replace("    ", "\t"), encoding="utf-8")
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="replace",
        symbol="Orders.Domain.Order.Cancel",
        content="public void Cancel() { }",
    )

    assert applier.apply_operation(solution_dir, operation).landed


def test_inserting_into_a_type_keeps_the_existing_member(solution_dir: Path) -> None:
    target = _write_order(solution_dir)
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="insert-into-type",
        symbol="Orders.Domain.Order",
        content='public string Status { get; private set; } = "open";',
    )

    record = applier.apply_operation(solution_dir, operation)

    assert record.landed
    updated = target.read_text(encoding="utf-8")
    assert "public string Status" in updated
    assert "public void Cancel" in updated


def test_deleting_a_member_removes_it(solution_dir: Path) -> None:
    target = _write_order(solution_dir)
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="delete",
        symbol="Orders.Domain.Order.Cancel",
    )

    assert applier.apply_operation(solution_dir, operation).landed
    assert "Cancel" not in target.read_text(encoding="utf-8")


def test_a_text_edit_records_the_relaxation_rung_it_needed(solution_dir: Path) -> None:
    """A drifting codebase must be visible, not silently absorbed."""
    target = solution_dir / "Program.cs"
    target.write_text("app.MapHealth();\napp.Run();\n", encoding="utf-8")
    operation = EditOperation(
        file="Program.cs",
        anchor_kind="text",
        disposition="replace",
        search="app . MapHealth ( ) ;",
        content="app.MapHealth();\napp.MapVersion();",
    )

    record = applier.apply_operation(solution_dir, operation)

    assert record.outcome is applier.ApplyOutcome.APPLIED_AFTER_RELAXATION
    assert record.relaxation_level > 0
    assert "app.MapVersion();" in target.read_text(encoding="utf-8")


def test_an_edit_against_a_missing_file_is_refused(solution_dir: Path) -> None:
    operation = EditOperation(
        file="src/Nope.cs",
        anchor_kind="symbol",
        disposition="replace",
        symbol="Orders.Domain.Order.Cancel",
        content="public void Cancel() { }",
    )

    record = applier.apply_operation(solution_dir, operation)

    assert record.outcome is applier.ApplyOutcome.FAILED
    assert "create-file" in record.failure_reason


def test_an_unresolvable_symbol_is_recorded_not_raised(solution_dir: Path) -> None:
    _write_order(solution_dir)
    operation = EditOperation(
        file="src/Order.cs",
        anchor_kind="symbol",
        disposition="replace",
        symbol="Orders.Domain.Order.Refund",
        content="public void Refund() { }",
    )

    assert applier.apply_operation(solution_dir, operation).outcome is applier.ApplyOutcome.FAILED


# --- the report ----------------------------------------------------------------------------


def test_a_failed_edit_is_recorded_not_swallowed(solution_dir: Path) -> None:
    """Failed application is a measured cost: it burns a turn and produces nothing."""
    report = applier.apply_all(solution_dir, (_create("../outside.cs"),))

    assert len(report.failed) == 1


def test_application_continues_past_a_failure(solution_dir: Path) -> None:
    report = applier.apply_all(solution_dir, (_create("../outside.cs"), _create("src/Ok.cs")))

    assert len(report.landed) == 1


def test_success_rate_reflects_partial_failure(solution_dir: Path) -> None:
    report = applier.apply_all(solution_dir, (_create("../outside.cs"), _create("src/Ok.cs")))

    assert report.success_rate == pytest.approx(0.5)


def test_empty_report_counts_as_fully_applied(solution_dir: Path) -> None:
    assert applier.apply_all(solution_dir, ()).all_landed is True


# --- verification wrapper ------------------------------------------------------------------


def _output(exit_code: int, timed_out: bool = False) -> dotnet.CommandOutput:
    return dotnet.CommandOutput(
        command=("dotnet", "build"), exit_code=exit_code, stdout="", stderr="", timed_out=timed_out
    )


def test_green_build_and_tests_pass(monkeypatch: pytest.MonkeyPatch, solution_dir: Path) -> None:
    monkeypatch.setattr(dotnet, "build", lambda project, **kw: _output(0))
    monkeypatch.setattr(dotnet, "test", lambda project, **kw: _output(0))

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.PASS


def _failed(text: str) -> dotnet.CommandOutput:
    return dotnet.CommandOutput(
        command=("dotnet", "build"), exit_code=1, stdout=text, stderr="", timed_out=False
    )


def test_compiler_error_is_a_code_defect(monkeypatch: pytest.MonkeyPatch, solution_dir: Path) -> None:
    monkeypatch.setattr(
        dotnet, "build", lambda project, **kw: _failed("src/Api/Program.cs(9,5): error CS1002: ; expected")
    )

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.CODE_DEFECT


def test_failing_tests_are_a_code_defect(monkeypatch: pytest.MonkeyPatch, solution_dir: Path) -> None:
    monkeypatch.setattr(dotnet, "build", lambda project, **kw: _output(0))
    monkeypatch.setattr(
        dotnet, "test", lambda project, **kw: _failed("Failed!  - Failed: 1, Passed: 3")
    )

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.CODE_DEFECT


def test_restore_failure_is_an_environment_failure(
    monkeypatch: pytest.MonkeyPatch, solution_dir: Path
) -> None:
    """Regenerating C# will never fix a NuGet feed, so it must not cost a repair attempt."""
    monkeypatch.setattr(
        dotnet,
        "build",
        lambda project, **kw: _failed("error NU1101: Unable to find package Foo. No sources."),
    )

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.ENVIRONMENT_FAILURE


def test_failure_with_no_parsed_diagnostics_is_an_environment_failure(
    monkeypatch: pytest.MonkeyPatch, solution_dir: Path
) -> None:
    """A crash the toolchain could not even describe (research R4).

    This reverses the provisional rule the pipeline shipped with, which called every non-zero
    exit a code defect. Spending the repair budget on output that names no diagnostic is the
    runaway loop the ceiling exists to prevent.
    """
    monkeypatch.setattr(dotnet, "build", lambda project, **kw: _output(1))

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.ENVIRONMENT_FAILURE


def test_msbuild_error_against_a_file_this_run_wrote_is_a_code_defect(
    monkeypatch: pytest.MonkeyPatch, solution_dir: Path
) -> None:
    """The tool broke the .csproj it authored - repairable, unlike a broken SDK install."""
    monkeypatch.setattr(
        dotnet,
        "build",
        lambda project, **kw: _failed("src/Api/Api.csproj : error MSB4025: invalid project file"),
    )

    ours = dotnet.verify(solution_dir, written_files=frozenset({"src/Api/Api.csproj"}))
    theirs = dotnet.verify(solution_dir, written_files=frozenset({"src/Api/Other.csproj"}))

    assert ours.classification is dotnet.Classification.CODE_DEFECT
    assert theirs.classification is dotnet.Classification.ENVIRONMENT_FAILURE


def test_build_timeout_is_an_environment_failure(
    monkeypatch: pytest.MonkeyPatch, solution_dir: Path
) -> None:
    monkeypatch.setattr(dotnet, "build", lambda project, **kw: _output(-1, timed_out=True))

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.ENVIRONMENT_FAILURE


def test_missing_toolchain_is_an_environment_failure(
    monkeypatch: pytest.MonkeyPatch, solution_dir: Path
) -> None:
    def missing(project, **kw):
        raise dotnet.ToolchainMissingError("dotnet not found")

    monkeypatch.setattr(dotnet, "build", missing)

    assert dotnet.verify(solution_dir).classification is dotnet.Classification.ENVIRONMENT_FAILURE


def test_tests_can_be_skipped(monkeypatch: pytest.MonkeyPatch, solution_dir: Path) -> None:
    monkeypatch.setattr(dotnet, "build", lambda project, **kw: _output(0))

    def unexpected(project, **kw):
        raise AssertionError("tests must not run when run_tests is False")

    monkeypatch.setattr(dotnet, "test", unexpected)

    assert dotnet.verify(solution_dir, run_tests=False).passed is True


def test_only_a_code_defect_is_repairable() -> None:
    defect = dotnet.VerificationResult(classification=dotnet.Classification.CODE_DEFECT)
    environment = dotnet.VerificationResult(classification=dotnet.Classification.ENVIRONMENT_FAILURE)

    assert (defect.repairable, environment.repairable) == (True, False)
