# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.judge artifacts: comparison.json schema/atomicity and FR-014 standalone.

Split out of test_evals_judge.py per the size-discipline hard cap; shares the same helper shapes.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.judge import judge_run
from cabal.evals.matrix import (
    MANIFEST_FILENAME,
    METRICS_FILENAME,
    OUTPUT_FILENAME,
    PATCH_FILENAME,
    write_json_atomic,
)
from cabal.evals.metrics import TranscriptMetrics, build_metrics

_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "019-agent-eval-harness" / "contracts"
)

RUN_ID = "evalrun-20260819T000000Z"
JUDGE_MODEL = "claude-judge-model"


@pytest.fixture(scope="module")
def comparison_schema() -> dict:
    return json.loads((_CONTRACTS_DIR / "comparison.schema.json").read_text(encoding="utf-8"))


# Shared helpers --------------------------------------------------------------


def _build_cell(
    cell_dir: Path, *, task_id: str, config_name: str, repetition: int
) -> Path:
    cell_dir.mkdir(parents=True, exist_ok=True)
    payload = build_metrics(
        run_id=RUN_ID,
        task_id=task_id,
        config_name=config_name,
        repetition=repetition,
        adapter_name="fake-adapter",
        status="completed",
        failure_reason=None,
        wall_seconds=1.0,
        started_at="2026-08-19T00:00:00Z",
        finished_at="2026-08-19T00:01:00Z",
        capabilities=AdapterCapabilities(tokens=True, tool_calls=True, cost=True),
        transcript=TranscriptMetrics(),
        diff=None,
        expected_files=[],
    )
    write_json_atomic(cell_dir / METRICS_FILENAME, payload)
    (cell_dir / PATCH_FILENAME).write_text("diff --git a/x b/x\n+hello\n", encoding="utf-8")
    (cell_dir / OUTPUT_FILENAME).write_text("agent final output", encoding="utf-8")
    return cell_dir


def _answer(winner: str) -> str:
    return json.dumps({"winner": winner, "confidence": 0.7, "criteria": []})


def _queued_judge(*responses: str) -> Callable[[str, str], str]:
    queue = list(responses)

    def _call(prompt: str, model: str) -> str:
        return queue.pop(0)

    return _call


def _build_run_dir(tmp_path: Path, *, tasks: list[str]) -> Path:
    run_dir = tmp_path / "results" / RUN_ID
    run_dir.mkdir(parents=True)
    write_json_atomic(
        run_dir / MANIFEST_FILENAME,
        {
            "run_id": RUN_ID,
            "baseline": "baseline",
            "candidate": "candidate",
            "runs": 1,
            "tasks": tasks,
            "adapter": "fake-adapter",
            "created_at": "2026-08-19T00:00:00Z",
        },
    )
    return run_dir


def _build_evals_root(tmp_path: Path, task_id: str) -> Path:
    evals_root = tmp_path / "evals"
    (evals_root / "tasks" / task_id).mkdir(parents=True)
    (evals_root / "tasks" / task_id / "prompt.md").write_text("Do the thing.", encoding="utf-8")
    return evals_root


@pytest.fixture
def judged_run(tmp_path: Path) -> tuple[Path, Path]:
    """One fully populated cell pair plus its evals tree, ready for judge_run."""
    run_dir = _build_run_dir(tmp_path, tasks=["sample-task"])
    _build_cell(run_dir / "sample-task" / "baseline" / "1", task_id="sample-task", config_name="baseline", repetition=1)
    _build_cell(run_dir / "sample-task" / "candidate" / "1", task_id="sample-task", config_name="candidate", repetition=1)
    evals_root = _build_evals_root(tmp_path, "sample-task")
    return run_dir, evals_root


# comparison.json: schema validation and atomicity ------------------------------


class TestComparisonArtifact:
    def test_judge_run_writes_a_schema_valid_comparison_json(
        self, judged_run: tuple[Path, Path], comparison_schema: dict
    ) -> None:
        """Every produced comparison.json must validate against contracts/comparison.schema.json."""
        # Arrange
        run_dir, evals_root = judged_run
        judge_call = _queued_judge(_answer("B"), _answer("A"))

        # Act
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=judge_call)

        # Assert
        comparison = json.loads((run_dir / "sample-task" / "comparison.json").read_text(encoding="utf-8"))
        jsonschema.validate(comparison, comparison_schema)

    def test_judge_run_rejudging_overwrites_the_previous_verdict(self, judged_run: tuple[Path, Path]) -> None:
        """Re-judging the same run must overwrite comparison.json, not append or leave stale data."""
        # Arrange
        run_dir, evals_root = judged_run
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=_queued_judge(_answer("B"), _answer("A")))

        # Act
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=_queued_judge(_answer("A"), _answer("B")))

        # Assert
        comparison = json.loads((run_dir / "sample-task" / "comparison.json").read_text(encoding="utf-8"))
        assert comparison["pairs"][0]["winner"] == "baseline"

    def test_judge_run_rejudging_leaves_no_tmp_files(self, judged_run: tuple[Path, Path]) -> None:
        """The atomic-write dance must never leave a `.tmp` artifact behind after either judge pass."""
        # Arrange
        run_dir, evals_root = judged_run
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=_queued_judge(_answer("B"), _answer("A")))

        # Act
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=_queued_judge(_answer("tie"), _answer("tie")))

        # Assert
        assert list(run_dir.rglob("*.tmp")) == []


# FR-014: judging is standalone -- results dir + evals tree only ---------------


class TestJudgeRunIsStandalone:
    def test_judge_run_signature_takes_no_repo_or_worktree_argument(self) -> None:
        """FR-014: judging must be expressible without any repo/worktree concept in its API."""
        # Arrange & Act
        params = inspect.signature(judge_run).parameters

        # Assert
        assert not any("repo" in name or "worktree" in name for name in params)

    def test_judge_run_never_touches_an_unrelated_scratch_directory(self, judged_run: tuple[Path, Path], tmp_path: Path) -> None:
        """Judging must only read the results dir and evals tree -- nothing else may be touched."""
        # Arrange
        run_dir, evals_root = judged_run
        scratch_repo = tmp_path / "unrelated-repo"
        scratch_repo.mkdir()
        marker = scratch_repo / "tracked.txt"
        marker.write_text("original\n", encoding="utf-8")

        # Act
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=_queued_judge(_answer("tie"), _answer("tie")))

        # Assert
        assert marker.read_text(encoding="utf-8") == "original\n"
