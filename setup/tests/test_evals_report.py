# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.report: per-metric aggregation math, variance, failures inventory.

Missing-comparison behavior and the report.json/report.md artifact live in
test_evals_report_artifact.py (size discipline); both files share the same helper shapes.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import pytest

from cabal.evals.judge import COMPARISON_FILENAME
from cabal.evals.matrix import MANIFEST_FILENAME, METRICS_FILENAME, write_json_atomic
from cabal.evals.report import build_report

RUN_ID = "evalrun-20260819T000000Z"


# Shared helpers ----------------------------------------------------------------


def _manifest(
    run_dir: Path, tasks: list[str], *, baseline: str = "baseline", candidate: str = "candidate", runs: int = 1
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        run_dir / MANIFEST_FILENAME,
        {
            "run_id": RUN_ID,
            "baseline": baseline,
            "candidate": candidate,
            "runs": runs,
            "tasks": tasks,
            "adapter": "fake-adapter",
            "created_at": "2026-08-19T00:00:00Z",
        },
    )


def _cell(
    run_dir: Path,
    task_id: str,
    config_name: str,
    repetition: int,
    *,
    status: str = "completed",
    failure_reason: str | None = None,
    checks: list[dict[str, Any]] | None = None,
    unrequested_changes_count: int | None = None,
    tool_calls_total: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    wall_seconds: float = 0.0,
) -> Path:
    """Write one metrics.json with exactly the fields the report reducer reads."""
    cell_dir = run_dir / task_id / config_name / str(repetition)
    cell_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "task_id": task_id,
        "config_name": config_name,
        "repetition": repetition,
        "adapter": "fake-adapter",
        "status": status,
        "failure_reason": failure_reason,
        "started_at": "2026-08-19T00:00:00Z",
        "finished_at": "2026-08-19T00:01:00Z",
        "agent": {
            "tool_calls_total": tool_calls_total,
            "tool_calls_by_name": None,
            "num_turns": None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": None,
            "cost_usd": None,
            "wall_seconds": wall_seconds,
        },
        "diff": {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "unrequested_changes_count": unrequested_changes_count,
            "unrequested_files": None,
            "empty_diff": False,
        },
        "checks": checks or [],
    }
    write_json_atomic(cell_dir / METRICS_FILENAME, payload)
    return cell_dir


def _comparison(run_dir: Path, task_id: str, winners: list[str], *, baseline: str = "baseline", candidate: str = "candidate") -> None:
    pairs = [
        {
            "repetition": index + 1,
            "winner": winner,
            "confidence": None,
            "order_agreement": True,
            "criteria": [],
            "truncated": False,
            "error_detail": "boom" if winner == "judge_error" else None,
        }
        for index, winner in enumerate(winners)
    ]
    write_json_atomic(
        run_dir / task_id / COMPARISON_FILENAME,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "task_id": task_id,
            "baseline_config": baseline,
            "candidate_config": candidate,
            "judge_model": "judge-model",
            "rubrics": [],
            "pairs": pairs,
        },
    )


def _row(report: dict[str, Any], metric: str) -> dict[str, Any]:
    return next(row for row in report["metrics_rows"] if row["metric"] == metric)


# task_pass_rate ------------------------------------------------------------------


class TestTaskPassRate:
    def test_task_pass_rate_denominator_includes_failed_runs(self, tmp_path: Path) -> None:
        """A failed run must still occupy a slot in the pass-rate denominator, not be dropped."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"])
        _cell(run_dir, "task-a", "baseline", 1, checks=[{"kind": "custom", "status": "passed"}])
        _cell(run_dir, "task-a", "baseline", 2, status="failed", failure_reason="agent_timeout")
        _cell(run_dir, "task-a", "baseline", 3, checks=[{"kind": "custom", "status": "failed"}])
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "task_pass_rate")
        assert row["per_config"]["baseline"] == {
            "mean": pytest.approx(round(1 / 3, 4)),
            "min": pytest.approx(0.0),
            "max": pytest.approx(1.0),
            "stddev": pytest.approx(round(statistics.stdev([1.0, 0.0, 0.0]), 4)),
            "n": 3,
        }

    def test_task_pass_rate_completed_run_with_failed_check_does_not_pass(self, tmp_path: Path) -> None:
        """A completed run whose deterministic check failed must count as 0, not 1, toward pass rate."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"])
        _cell(run_dir, "task-a", "baseline", 1, checks=[{"kind": "custom", "status": "failed"}])
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "task_pass_rate")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(0.0)


# test_pass_rate --------------------------------------------------------------------


class TestTestPassRate:
    def test_test_pass_rate_averages_the_per_cell_rate_from_parsed_counts(self, tmp_path: Path) -> None:
        """Each cell's own passed/failed counts become one sample rate; the row means those rates."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=2)
        _cell(run_dir, "task-a", "baseline", 1, checks=[{"kind": "test", "passed_count": 8, "failed_count": 2}])
        _cell(run_dir, "task-a", "baseline", 2, checks=[{"kind": "test", "passed_count": 5, "failed_count": 0}])
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "test_pass_rate")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(0.9)


# build_success_rate ------------------------------------------------------------------


class TestBuildSuccessRate:
    def test_build_success_rate_averages_per_cell_build_kind_pass_proportion(self, tmp_path: Path) -> None:
        """Only `build`-kind checks feed this metric; a mixed pass/fail cell yields its own proportion."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=2)
        _cell(run_dir, "task-a", "baseline", 1, checks=[{"kind": "build", "status": "passed"}])
        _cell(
            run_dir, "task-a", "baseline", 2,
            checks=[{"kind": "build", "status": "passed"}, {"kind": "build", "status": "failed"}],
        )
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "build_success_rate")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(0.75)


# unrequested_changes -----------------------------------------------------------------


class TestUnrequestedChanges:
    def test_unrequested_changes_mean_only_counts_completed_runs_with_scope(self, tmp_path: Path) -> None:
        """A failed cell's unrequested-changes figure is meaningless and must be excluded from the mean."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=3)
        _cell(run_dir, "task-a", "baseline", 1, unrequested_changes_count=3)
        _cell(run_dir, "task-a", "baseline", 2, unrequested_changes_count=1)
        _cell(run_dir, "task-a", "baseline", 3, status="failed", failure_reason="agent_crash", unrequested_changes_count=99)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "unrequested_changes")
        assert row["per_config"]["baseline"] == {"mean": pytest.approx(2.0), "min": pytest.approx(1.0), "max": pytest.approx(3.0), "stddev": None, "n": 2}


# tool_calls / tokens_total / wall_seconds ---------------------------------------------


class TestAgentMeans:
    @pytest.fixture
    def run_dir(self, tmp_path: Path) -> Path:
        """Two completed cells with known agent figures, plus one failed cell that must be excluded."""
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=3)
        _cell(run_dir, "task-a", "baseline", 1, tool_calls_total=10, input_tokens=100, output_tokens=50, wall_seconds=5.0)
        _cell(run_dir, "task-a", "baseline", 2, tool_calls_total=20, input_tokens=200, output_tokens=100, wall_seconds=7.0)
        _cell(run_dir, "task-a", "baseline", 3, status="failed", failure_reason="agent_timeout", tool_calls_total=999, input_tokens=999, output_tokens=999, wall_seconds=999.0)
        _cell(run_dir, "task-a", "candidate", 1)
        return run_dir

    def test_tool_calls_mean_excludes_the_failed_run(self, run_dir: Path) -> None:
        """A failed run's tool-call count is agent noise from an incomplete session -- must be excluded."""
        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "tool_calls")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(15.0)

    def test_tokens_total_mean_sums_input_and_output_then_excludes_the_failed_run(self, run_dir: Path) -> None:
        """tokens_total is input+output per cell, averaged only across completed cells."""
        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "tokens_total")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(225.0)

    def test_wall_seconds_mean_excludes_the_failed_run(self, run_dir: Path) -> None:
        """wall_seconds averages must not be dragged up by a timed-out run's inflated duration."""
        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "wall_seconds")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(6.0)


# pairwise_win_rate ---------------------------------------------------------------------


class TestPairwiseWinRate:
    def test_pairwise_win_rate_excludes_ties_and_judge_errors_from_the_denominator(self, tmp_path: Path) -> None:
        """Only decisive baseline/candidate verdicts may count toward either config's win rate."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=5)
        for repetition in range(1, 6):
            _cell(run_dir, "task-a", "baseline", repetition)
            _cell(run_dir, "task-a", "candidate", repetition)
        _comparison(run_dir, "task-a", ["baseline", "candidate", "candidate", "tie", "judge_error"])

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "pairwise_win_rate")
        assert row["per_config"]["baseline"]["mean"] == pytest.approx(round(1 / 3, 4))
        assert row["per_config"]["candidate"]["mean"] == pytest.approx(round(2 / 3, 4))
        assert row["per_config"]["baseline"]["n"] == 3

    def test_pairwise_win_rate_is_null_when_no_decisive_pairs(self, tmp_path: Path) -> None:
        """An all-tie/error comparison must report a null mean, not a division-by-zero or a fake 0."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=2)
        _cell(run_dir, "task-a", "baseline", 1)
        _cell(run_dir, "task-a", "candidate", 1)
        _comparison(run_dir, "task-a", ["tie", "judge_error"])

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "pairwise_win_rate")
        assert row["per_config"]["baseline"]["mean"] is None
        assert row["per_config"]["candidate"]["mean"] is None


# Variance ------------------------------------------------------------------------------


class TestVariance:
    def test_three_or_more_samples_reports_hand_computed_stddev(self, tmp_path: Path) -> None:
        """n>=3 must report a real stddev, matching statistics.stdev on the same sample set."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=3)
        for repetition, value in enumerate((2, 4, 6), start=1):
            _cell(run_dir, "task-a", "baseline", repetition, unrequested_changes_count=value)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "unrequested_changes")
        assert row["per_config"]["baseline"]["stddev"] == pytest.approx(round(statistics.stdev([2, 4, 6]), 4))

    def test_fewer_than_three_samples_reports_null_stddev(self, tmp_path: Path) -> None:
        """n<3 must report a null stddev -- a two-point spread is not a meaningful variance."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=2)
        _cell(run_dir, "task-a", "baseline", 1, unrequested_changes_count=2)
        _cell(run_dir, "task-a", "baseline", 2, unrequested_changes_count=6)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "unrequested_changes")
        assert row["per_config"]["baseline"]["stddev"] is None

    def test_min_and_max_reflect_the_sample_extremes(self, tmp_path: Path) -> None:
        """min/max must be the literal extremes of the sample set, independent of the mean/stddev path."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=3)
        for repetition, value in enumerate((2, 4, 6), start=1):
            _cell(run_dir, "task-a", "baseline", repetition, unrequested_changes_count=value)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "unrequested_changes")
        assert (row["per_config"]["baseline"]["min"], row["per_config"]["baseline"]["max"]) == (pytest.approx(2.0), pytest.approx(6.0))


# All-null metric -------------------------------------------------------------------------


class TestAllNullMetric:
    def test_metric_with_no_matching_checks_yields_null_mean_and_zero_n(self, tmp_path: Path) -> None:
        """A metric no cell can supply (no build-kind checks anywhere) must report null mean, n=0."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=1)
        _cell(run_dir, "task-a", "baseline", 1, checks=[{"kind": "custom", "status": "passed"}])
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "build_success_rate")
        assert row["per_config"]["baseline"] == {"mean": None, "min": None, "max": None, "stddev": None, "n": 0}


# Failures inventory ------------------------------------------------------------------------


class TestFailuresInventory:
    def test_failures_lists_every_failed_cell_with_its_machine_readable_reason(self, tmp_path: Path) -> None:
        """The failures inventory must be a complete, per-cell record for triage -- none dropped."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a", "task-b"], runs=1)
        _cell(run_dir, "task-a", "baseline", 1, status="failed", failure_reason="agent_timeout")
        _cell(run_dir, "task-a", "candidate", 1)
        _cell(run_dir, "task-b", "baseline", 1)
        _cell(run_dir, "task-b", "candidate", 1, status="failed", failure_reason="worktree_error")

        # Act
        bundle = build_report(run_dir)

        # Assert
        failures = {(f["task_id"], f["config_name"], f["reason"]) for f in bundle.payload["failures"]}
        assert failures == {("task-a", "baseline", "agent_timeout"), ("task-b", "candidate", "worktree_error")}
