# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.report artifacts: missing-comparison handling, report.json/report.md.

Split out of test_evals_report.py per the size-discipline hard cap; shares the same helper shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from rich.table import Table

from cabal.evals.judge import COMPARISON_FILENAME
from cabal.evals.matrix import MANIFEST_FILENAME, METRICS_FILENAME, write_json_atomic
from cabal.evals.report import REPORT_JSON_FILENAME, REPORT_MD_FILENAME, build_report, write_report
from cabal.evals.report_render import build_terminal_table, render_markdown

_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "019-agent-eval-harness" / "contracts"
)

RUN_ID = "evalrun-20260819T000000Z"


@pytest.fixture(scope="module")
def report_schema() -> dict:
    return json.loads((_CONTRACTS_DIR / "report.schema.json").read_text(encoding="utf-8"))


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
    tool_calls_total: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
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
        "status": "completed",
        "failure_reason": None,
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
            "wall_seconds": 1.0,
        },
        "diff": {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "unrequested_changes_count": None,
            "unrequested_files": None,
            "empty_diff": False,
        },
        "checks": [],
    }
    write_json_atomic(cell_dir / METRICS_FILENAME, payload)
    return cell_dir


def _comparison(run_dir: Path, task_id: str, winners: list[str]) -> None:
    pairs = [
        {
            "repetition": index + 1,
            "winner": winner,
            "confidence": None,
            "order_agreement": True,
            "criteria": [],
            "truncated": False,
            "error_detail": None,
        }
        for index, winner in enumerate(winners)
    ]
    write_json_atomic(
        run_dir / task_id / COMPARISON_FILENAME,
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "task_id": task_id,
            "baseline_config": "baseline",
            "candidate_config": "candidate",
            "judge_model": "judge-model",
            "rubrics": [],
            "pairs": pairs,
        },
    )


def _row(report: dict[str, Any], metric: str) -> dict[str, Any]:
    return next(row for row in report["metrics_rows"] if row["metric"] == metric)


# Missing comparison.json -----------------------------------------------------------------


class TestMissingComparison:
    def test_missing_comparison_json_leaves_pairwise_cells_null_but_report_still_builds(self, tmp_path: Path) -> None:
        """Judging is optional (FR-014); an unjudged run must still reduce to a complete report."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=1)
        _cell(run_dir, "task-a", "baseline", 1)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        row = _row(bundle.payload, "pairwise_win_rate")
        assert row["per_config"]["baseline"]["mean"] is None

    def test_missing_comparison_json_is_reported_through_the_notes_mechanism(self, tmp_path: Path) -> None:
        """The gap must surface as an advisory note, not silently disappear from the operator's view."""
        # Arrange
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a"], runs=1)
        _cell(run_dir, "task-a", "baseline", 1)
        _cell(run_dir, "task-a", "candidate", 1)

        # Act
        bundle = build_report(run_dir)

        # Assert
        assert any("task-a" in note for note in bundle.notes)


# report.json / report.md artifact --------------------------------------------------------


class TestReportArtifact:
    @pytest.fixture
    def bundle_and_markdown(self, tmp_path: Path):
        run_dir = tmp_path / RUN_ID
        _manifest(run_dir, ["task-a", "task-b"], runs=1)
        for task_id in ("task-a", "task-b"):
            _cell(run_dir, task_id, "baseline", 1, tool_calls_total=5, input_tokens=10, output_tokens=5)
            _cell(run_dir, task_id, "candidate", 1, tool_calls_total=8, input_tokens=20, output_tokens=10)
        _comparison(run_dir, "task-a", ["baseline"])
        _comparison(run_dir, "task-b", ["candidate"])
        bundle = build_report(run_dir)
        markdown = render_markdown(bundle.payload, bundle.notes)
        return run_dir, bundle, markdown

    def test_report_json_validates_against_the_contract_schema(
        self, bundle_and_markdown, report_schema: dict
    ) -> None:
        """report.json must satisfy report.schema.json: >=7 metric rows, exactly 2 configs."""
        # Arrange
        _, bundle, _ = bundle_and_markdown

        # Act & Assert
        jsonschema.validate(bundle.payload, report_schema)
        assert len(bundle.payload["metrics_rows"]) >= 7
        assert len(bundle.payload["configs"]) == 2

    def test_write_report_leaves_no_tmp_files(self, bundle_and_markdown) -> None:
        """The atomic-write dance for both report.json and report.md must not leak a `.tmp` file."""
        # Arrange
        run_dir, bundle, markdown = bundle_and_markdown

        # Act
        write_report(run_dir, bundle, markdown)

        # Assert
        assert list(run_dir.rglob("*.tmp")) == []

    def test_write_report_writes_both_artifacts_to_the_run_directory(self, bundle_and_markdown) -> None:
        """write_report must return the actual paths it wrote, both inside the run directory."""
        # Arrange
        run_dir, bundle, markdown = bundle_and_markdown

        # Act
        json_path, md_path = write_report(run_dir, bundle, markdown)

        # Assert
        assert (json_path, md_path) == (run_dir / REPORT_JSON_FILENAME, run_dir / REPORT_MD_FILENAME)

    def test_report_markdown_contains_both_config_columns(self, bundle_and_markdown) -> None:
        """report.md's table header must name both configs so a human can read it without report.json."""
        # Arrange
        _, _, markdown = bundle_and_markdown

        # Assert
        assert "| Metric | baseline | candidate |" in markdown

    def test_build_terminal_table_returns_a_rich_table_without_raising(self, bundle_and_markdown) -> None:
        """The CLI's terminal renderer must produce a real rich Table for any schema-valid report."""
        # Arrange
        _, bundle, _ = bundle_and_markdown

        # Act
        table = build_terminal_table(bundle.payload)

        # Assert
        assert isinstance(table, Table)
