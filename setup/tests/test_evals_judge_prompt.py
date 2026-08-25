# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.judge_prompt: diff truncation, prompt assembly, task context loading.

Split out of test_evals_judge.py per the size-discipline hard cap; shares the same helper shapes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.judge import judge_pair
from cabal.evals.judge_prompt import (
    TaskContext,
    build_judge_prompt,
    load_cell_evidence,
    load_task_context,
    truncate_diff,
)
from cabal.evals.matrix import METRICS_FILENAME, OUTPUT_FILENAME, PATCH_FILENAME, write_json_atomic
from cabal.evals.metrics import TranscriptMetrics, build_metrics

RUN_ID = "evalrun-20260819T000000Z"
JUDGE_MODEL = "claude-judge-model"


# Shared helpers ----------------------------------------------------------------


def _context(task_id: str = "sample-task") -> TaskContext:
    return TaskContext(
        task_id=task_id,
        prompt_text="Implement the thing exactly as described.",
        rubric_names=(),
        rubric_texts=(),
    )


def _build_cell(
    cell_dir: Path,
    *,
    task_id: str,
    config_name: str,
    repetition: int,
    diff_text: str = "diff --git a/x b/x\n+hello\n",
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
    (cell_dir / PATCH_FILENAME).write_text(diff_text, encoding="utf-8")
    (cell_dir / OUTPUT_FILENAME).write_text("agent final output", encoding="utf-8")
    return cell_dir


def _answer(winner: str) -> str:
    return json.dumps({"winner": winner, "confidence": 0.5, "criteria": []})


def _queued_judge(*responses: str) -> Callable[[str, str], str]:
    queue = list(responses)

    def _call(prompt: str, model: str) -> str:
        return queue.pop(0)

    return _call


def _build_evals_root(tmp_path: Path, task_id: str) -> Path:
    evals_root = tmp_path / "evals"
    (evals_root / "tasks" / task_id).mkdir(parents=True)
    (evals_root / "tasks" / task_id / "prompt.md").write_text("Do the thing.", encoding="utf-8")
    return evals_root


# truncate_diff ---------------------------------------------------------------


class TestTruncateDiff:
    def test_truncate_diff_under_limit_leaves_text_untouched(self) -> None:
        """A diff smaller than the limit must pass through byte-for-byte with truncated=False."""
        # Arrange
        patch_text = "diff --git a/x b/x\n+short\n"

        # Act
        text, truncated = truncate_diff(patch_text, char_limit=10000)

        # Assert
        assert (text, truncated) == (patch_text, False)

    def test_truncate_diff_over_limit_inserts_marker_and_flags_truncated(self) -> None:
        """A per-file chunk exceeding the char limit must be cut with a visible [truncated] marker."""
        # Arrange
        patch_text = "diff --git a/x b/x\n" + ("+" + "a" * 50 + "\n")

        # Act
        text, truncated = truncate_diff(patch_text, char_limit=10)

        # Assert
        assert truncated is True
        assert "[truncated]" in text


# build_judge_prompt: truncation surfaces in the assembled text -----------------


class TestBuildJudgePromptTruncation:
    def test_build_judge_prompt_embeds_the_truncation_marker_for_an_oversized_diff(
        self, tmp_path: Path
    ) -> None:
        """The assembled prompt text itself must surface the truncation, not just the CellEvidence flag."""
        # Arrange
        cell_dir = _build_cell(
            tmp_path / "oversized",
            task_id="sample-task",
            config_name="baseline",
            repetition=1,
            diff_text="diff --git a/x b/x\n" + ("+" + "b" * 50 + "\n"),
        )
        evidence = load_cell_evidence(cell_dir, diff_char_limit=10)
        other = load_cell_evidence(cell_dir, diff_char_limit=10000)

        # Act
        prompt = build_judge_prompt(_context(), evidence, other)

        # Assert
        assert "[truncated]" in prompt


# judge_pair: the truncated flag reflects load_cell_evidence -------------------


class TestJudgePairTruncationFlag:
    def test_judge_pair_oversized_diff_sets_truncated_true_on_the_pair(self, tmp_path: Path) -> None:
        """The pair's `truncated` field must reflect either side needing truncation."""
        # Arrange
        baseline_dir = _build_cell(
            tmp_path / "baseline" / "1",
            task_id="sample-task",
            config_name="baseline",
            repetition=1,
            diff_text="diff --git a/x b/x\n" + ("+" + "c" * 50 + "\n"),
        )
        candidate_dir = _build_cell(
            tmp_path / "candidate" / "1", task_id="sample-task", config_name="candidate", repetition=1
        )
        judge_call = _queued_judge(_answer("tie"), _answer("tie"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 10, judge_call)

        # Assert
        assert pair["truncated"] is True


# load_task_context: reads from the evals tree alone ----------------------------


class TestLoadTaskContext:
    def test_load_task_context_reads_prompt_from_the_evals_tree(self, tmp_path: Path) -> None:
        """The judge's task context must come from the evals tree, not a live repo checkout."""
        # Arrange
        evals_root = _build_evals_root(tmp_path, "sample-task")

        # Act
        context = load_task_context(evals_root, "sample-task")

        # Assert
        assert context.prompt_text == "Do the thing."

    def test_load_task_context_missing_prompt_file_uses_the_placeholder_text(self, tmp_path: Path) -> None:
        """FR-014's leniency: a task dir without prompt.md must not raise, just fall back visibly."""
        # Arrange
        evals_root = tmp_path / "evals"
        (evals_root / "tasks" / "sample-task").mkdir(parents=True)

        # Act
        context = load_task_context(evals_root, "sample-task")

        # Assert
        assert "unavailable" in context.prompt_text
