# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.metrics: transcript parsing and metrics.json assembly."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.metrics import (
    TranscriptMetrics,
    build_metrics,
    parse_transcript,
    unrequested_changes,
)
from cabal.evals.worktree import DiffResult

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "evals"
_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "019-agent-eval-harness" / "contracts"
)


@pytest.fixture(scope="module")
def metrics_schema() -> dict:
    return json.loads((_CONTRACTS_DIR / "metrics.schema.json").read_text(encoding="utf-8"))


def _full_capabilities() -> AdapterCapabilities:
    return AdapterCapabilities(tokens=True, tool_calls=True, cost=True)


def _diff(changed_files: tuple[str, ...]) -> DiffResult:
    return DiffResult(
        patch_text="diff --git a/x b/x\n+changed\n",
        changed_files=changed_files,
        insertions=10,
        deletions=2,
        empty_diff=False,
    )


# parse_transcript: success transcript --------------------------------------


class TestParseTranscriptSuccess:
    def test_parse_transcript_with_mixed_tool_uses_counts_totals_and_buckets(self) -> None:
        """Tool calls must accumulate across every assistant event, not just the last one seen."""
        # Arrange
        path = _FIXTURES_DIR / "success_transcript.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert result.tool_calls_total == 4
        assert result.tool_calls_by_name == {"Read": 1, "Edit": 2, "Bash": 1}

    def test_parse_transcript_with_mixed_tool_uses_extracts_terminal_result_figures(self) -> None:
        """Tokens, cost and turn count come only from the terminal result event."""
        # Arrange
        path = _FIXTURES_DIR / "success_transcript.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert (result.input_tokens, result.output_tokens, result.cache_read_tokens) == (
            15000,
            2200,
            8000,
        )
        assert result.cost_usd == 0.1234
        assert result.num_turns == 4


# parse_transcript: result event missing usage -------------------------------


class TestParseTranscriptMissingUsage:
    def test_parse_transcript_result_without_usage_reports_none_not_zero(self) -> None:
        """FR-006: a figure the transcript never reported must be None, never a fabricated 0."""
        # Arrange
        path = _FIXTURES_DIR / "no_usage_result.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert (
            result.input_tokens,
            result.output_tokens,
            result.cache_read_tokens,
            result.cost_usd,
        ) == (None, None, None, None)

    def test_parse_transcript_result_without_usage_still_reports_num_turns(self) -> None:
        """num_turns lives outside the usage dict, so a missing usage block must not blank it out."""
        # Arrange
        path = _FIXTURES_DIR / "no_usage_result.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert result.num_turns == 1


# parse_transcript: error result ---------------------------------------------


class TestParseTranscriptErrorResult:
    def test_parse_transcript_error_result_still_extracts_reported_figures(self) -> None:
        """is_error is the adapter's own classification signal; metrics.py still parses whatever the result carries."""
        # Arrange
        path = _FIXTURES_DIR / "error_result.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert result.num_turns == 10
        assert result.input_tokens == 5000
        assert result.cost_usd == 0.02


# parse_transcript: malformed / missing input --------------------------------


class TestParseTranscriptMalformedLines:
    def test_parse_transcript_skips_malformed_json_lines_without_raising(self) -> None:
        """A garbled or truncated line mid-stream must never crash the parser."""
        # Arrange
        path = _FIXTURES_DIR / "malformed_lines.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert result.tool_calls_total == 1
        assert result.num_turns == 1

    def test_parse_transcript_missing_file_returns_default_metrics(self) -> None:
        """A cell that crashed before any transcript existed reports 'nothing observed', not an error."""
        # Arrange
        path = _FIXTURES_DIR / "does-not-exist.jsonl"

        # Act
        result = parse_transcript(path)

        # Assert
        assert result == TranscriptMetrics()


# unrequested_changes ----------------------------------------------------------


class TestUnrequestedChanges:
    def test_unrequested_changes_with_no_expected_files_disables_scope_tracking(self) -> None:
        """No expected_files means scope tracking is off: (None, None), not (0, [])."""
        # Arrange & Act
        count, files = unrequested_changes(["a.py", "b.py"], [])

        # Assert
        assert (count, files) == (None, None)

    def test_unrequested_changes_flags_files_outside_the_expected_glob(self) -> None:
        """Only files that fail every expected_files glob pattern count as unrequested."""
        # Arrange & Act
        count, files = unrequested_changes(["src/foo.py", "docs/readme.md"], ["src/*.py"])

        # Assert
        assert (count, files) == (1, ["docs/readme.md"])


# build_metrics: end-to-end schema validation ---------------------------------


class TestBuildMetricsEndToEnd:
    def test_build_metrics_completed_run_with_expected_files_validates_and_scopes(
        self, metrics_schema: dict
    ) -> None:
        """A completed run with expected_files must produce a schema-valid artifact with scope computed."""
        # Arrange
        transcript = parse_transcript(_FIXTURES_DIR / "success_transcript.jsonl")
        diff = _diff(("src/foo.py", "docs/readme.md"))

        # Act
        payload = build_metrics(
            run_id="evalrun-20260819T000000Z",
            task_id="sample-task",
            config_name="baseline",
            repetition=1,
            adapter_name="claude-code",
            status="completed",
            failure_reason=None,
            wall_seconds=12.5,
            started_at="2026-08-19T10:00:00Z",
            finished_at="2026-08-19T10:05:00Z",
            capabilities=_full_capabilities(),
            transcript=transcript,
            diff=diff,
            expected_files=["src/*.py"],
        )

        # Assert
        jsonschema.validate(payload, metrics_schema)
        assert payload["diff"]["unrequested_changes_count"] == 1
        assert payload["diff"]["unrequested_files"] == ["docs/readme.md"]
        assert isinstance(payload["checks"], list)

    def test_build_metrics_failed_run_validates_with_nullable_agent_fields(
        self, metrics_schema: dict
    ) -> None:
        """A run that failed before any transcript existed must still assemble a schema-valid artifact."""
        # Arrange
        transcript = TranscriptMetrics()

        # Act
        payload = build_metrics(
            run_id="evalrun-20260819T000000Z",
            task_id="sample-task",
            config_name="candidate",
            repetition=2,
            adapter_name="claude-code",
            status="failed",
            failure_reason="agent_timeout",
            wall_seconds=900.0,
            started_at="2026-08-19T10:00:00Z",
            finished_at="2026-08-19T10:15:00Z",
            capabilities=_full_capabilities(),
            transcript=transcript,
            diff=None,
            expected_files=["src/*.py"],
        )

        # Assert
        jsonschema.validate(payload, metrics_schema)
        assert payload["agent"]["tool_calls_total"] is None
        assert payload["agent"]["input_tokens"] is None

    def test_build_metrics_task_without_expected_files_disables_scope_fields(
        self, metrics_schema: dict
    ) -> None:
        """A task.toml with no expected_files must produce None scope fields, not an empty list/zero."""
        # Arrange
        transcript = parse_transcript(_FIXTURES_DIR / "success_transcript.jsonl")
        diff = _diff(("src/foo.py",))

        # Act
        payload = build_metrics(
            run_id="evalrun-20260819T000000Z",
            task_id="sample-task",
            config_name="baseline",
            repetition=1,
            adapter_name="claude-code",
            status="completed",
            failure_reason=None,
            wall_seconds=5.0,
            started_at="2026-08-19T10:00:00Z",
            finished_at="2026-08-19T10:01:00Z",
            capabilities=_full_capabilities(),
            transcript=transcript,
            diff=diff,
            expected_files=[],
        )

        # Assert
        jsonschema.validate(payload, metrics_schema)
        assert (
            payload["diff"]["unrequested_changes_count"],
            payload["diff"]["unrequested_files"],
        ) == (None, None)
