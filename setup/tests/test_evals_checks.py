# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.checks: real-subprocess check execution and output parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.checks import CheckResult, _parse_dotnet, run_checks
from cabal.evals.definitions_model import CheckSpec, Task
from cabal.evals.metrics import TranscriptMetrics, build_metrics, unrequested_changes

_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "019-agent-eval-harness" / "contracts"
)

# Shared helpers --------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _task(checks: list[CheckSpec]) -> Task:
    return Task(
        id="sample-task",
        title="Sample task",
        repo=Path("."),
        ref="HEAD",
        prompt="do the thing",
        checks=checks,
        expected_files=[],
        rubrics=[],
        timeout_seconds=None,
        skip_permissions=False,
    )


@pytest.fixture(scope="module")
def metrics_schema() -> dict:
    return json.loads((_CONTRACTS_DIR / "metrics.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def two_check_results(tmp_path: Path) -> list[CheckResult]:
    """One failing check followed by one passing check, run for real via run_checks."""
    fail_spec = CheckSpec(
        kind="test", cmd=[sys.executable, "-c", "raise SystemExit(1)"], parser="exit-code", timeout_seconds=30
    )
    pass_spec = CheckSpec(
        kind="build", cmd=[sys.executable, "-c", "pass"], parser="exit-code", timeout_seconds=30
    )
    return run_checks(_task([fail_spec, pass_spec]), tmp_path, default_timeout=30)


# run_checks: pytest parser -----------------------------------------------------


class TestRunChecksPytestParser:
    def test_run_checks_passing_pytest_file_reports_passed_with_count(self, tmp_path: Path) -> None:
        """A trivial passing pytest module must parse as `passed` with a real passed_count."""
        # Arrange
        _write(tmp_path / "test_sample.py", "def test_ok():\n    assert True\n")
        spec = CheckSpec(
            kind="test",
            cmd=[sys.executable, "-m", "pytest", "test_sample.py", "-q"],
            parser="pytest",
            timeout_seconds=60,
        )

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=60)

        # Assert
        assert (result.status, result.passed_count, result.exit_code) == ("passed", 1, 0)

    def test_run_checks_failing_pytest_file_reports_failed_with_count(self, tmp_path: Path) -> None:
        """A failing assertion must parse as `failed` with a nonzero failed_count."""
        # Arrange
        _write(tmp_path / "test_sample.py", "def test_bad():\n    assert False\n")
        spec = CheckSpec(
            kind="test",
            cmd=[sys.executable, "-m", "pytest", "test_sample.py", "-q"],
            parser="pytest",
            timeout_seconds=60,
        )

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=60)

        # Assert
        assert result.status == "failed"
        assert result.failed_count >= 1


# run_checks: exit-code parser default -------------------------------------------


class TestRunChecksExitCodeParser:
    def test_run_checks_zero_exit_reports_passed_with_no_counts(self, tmp_path: Path) -> None:
        """The exit-code parser is the default fallback: a clean exit is `passed`, counts stay None."""
        # Arrange
        spec = CheckSpec(kind="custom", cmd=[sys.executable, "-c", "pass"], parser="exit-code", timeout_seconds=30)

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=30)

        # Assert
        assert (result.status, result.exit_code, result.passed_count, result.failed_count) == (
            "passed",
            0,
            None,
            None,
        )

    def test_run_checks_nonzero_exit_reports_failed_with_exit_code_preserved(self, tmp_path: Path) -> None:
        """A nonzero exit must surface verbatim as `failed` with the exact exit code, no counts fabricated."""
        # Arrange
        spec = CheckSpec(
            kind="custom",
            cmd=[sys.executable, "-c", "raise SystemExit(3)"],
            parser="exit-code",
            timeout_seconds=30,
        )

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=30)

        # Assert
        assert (result.status, result.exit_code, result.passed_count, result.failed_count) == (
            "failed",
            3,
            None,
            None,
        )


# run_checks: timeout ------------------------------------------------------------


class TestRunChecksTimeout:
    def test_run_checks_exceeding_timeout_kills_the_process_tree(self, tmp_path: Path) -> None:
        """A hung check must be recorded as `timeout`, not left to run past its declared budget."""
        # Arrange
        spec = CheckSpec(
            kind="custom",
            cmd=[sys.executable, "-c", "import time; time.sleep(60)"],
            parser="exit-code",
            timeout_seconds=2,
        )

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=2)

        # Assert
        assert result.status == "timeout"
        assert result.exit_code is None
        assert result.duration_seconds < 15  # generous bound; proves the tree-kill actually fired


# run_checks: missing executable --------------------------------------------------


class TestRunChecksMissingExecutable:
    def test_run_checks_missing_executable_reports_error_without_raising(self, tmp_path: Path) -> None:
        """An unresolvable command must be recorded data (`error`), never an uncaught OSError."""
        # Arrange
        spec = CheckSpec(
            kind="custom",
            cmd=["definitely-not-a-real-executable-xyz"],
            parser="exit-code",
            timeout_seconds=30,
        )

        # Act
        [result] = run_checks(_task([spec]), tmp_path, default_timeout=30)

        # Assert
        assert result.status == "error"
        assert result.exit_code is None


# run_checks: declaration order and failure isolation -----------------------------


class TestRunChecksOrderedExecution:
    def test_run_checks_runs_every_check_even_after_an_earlier_failure(
        self, two_check_results: list[CheckResult]
    ) -> None:
        """A failing check must not short-circuit the ones declared after it (checks.py's real contract)."""
        # Assert
        assert [result.status for result in two_check_results] == ["failed", "passed"]


# _parse_dotnet: real captured dotnet test output styles ---------------------------


class TestParseDotnetOutputStyles:
    def test_parse_dotnet_bang_style_summary_line_extracts_counts(self) -> None:
        """`Passed!` terse VSTest summaries still carry `Passed:`/`Failed:` substrings the regex needs."""
        # Arrange
        output = (
            "Starting test execution, please wait...\n"
            "Passed!  - Failed:     0, Passed:    12, Skipped:     0, Total:    12, "
            "Duration: 340 ms - MyProject.Tests.dll\n"
        )

        # Act
        passed, failed = _parse_dotnet(output)

        # Assert
        assert (passed, failed) == (12, 0)

    def test_parse_dotnet_labelled_count_style_extracts_counts(self) -> None:
        """The older multi-line `Passed: N` / `Failed: N` console summary must parse the same way."""
        # Arrange
        output = "Total tests: 12\n     Passed: 10\n     Failed: 2\n     Skipped: 0\n"

        # Act
        passed, failed = _parse_dotnet(output)

        # Assert
        assert (passed, failed) == (10, 2)


# CheckResult -> metrics.json schema conformance -----------------------------------


class TestCheckResultSchemaConformance:
    def test_check_results_embedded_in_metrics_json_validate_against_check_result_schema(
        self, two_check_results: list[CheckResult], metrics_schema: dict
    ) -> None:
        """Real CheckResults, serialized via build_metrics, must satisfy $defs.check_result exactly."""
        # Act
        payload = build_metrics(
            run_id="evalrun-20260819T000000Z",
            task_id="sample-task",
            config_name="baseline",
            repetition=1,
            adapter_name="claude-code",
            status="completed",
            failure_reason=None,
            wall_seconds=1.0,
            started_at="2026-08-19T10:00:00Z",
            finished_at="2026-08-19T10:00:01Z",
            capabilities=AdapterCapabilities(tokens=False, tool_calls=False, cost=False),
            transcript=TranscriptMetrics(),
            diff=None,
            expected_files=[],
            checks=two_check_results,
        )

        # Assert
        jsonschema.validate(payload, metrics_schema)
        assert len(payload["checks"]) == 2


# metrics.unrequested_changes: Windows path-separator scope regression ----------------


class TestUnrequestedChangesSeparatorScope:
    def test_unrequested_changes_treats_backslash_and_forward_slash_paths_equivalently(self) -> None:
        """Windows-reported backslash paths must match the same forward-slash glob an author writes."""
        # Act
        backslash_count, backslash_files = unrequested_changes(
            ["setup\\src\\x.py"], ["setup/src/x.py"]
        )
        forward_count, forward_files = unrequested_changes(
            ["setup/src/x.py"], ["setup\\src\\x.py"]
        )

        # Assert
        assert (backslash_count, backslash_files) == (0, [])
        assert (forward_count, forward_files) == (0, [])
