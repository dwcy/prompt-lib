# -*- coding: utf-8 -*-
"""Unit tests for cabal.evals.judge: pairwise both-orders verdicts, error handling, atomicity.

Diff-truncation tests live in test_evals_judge_prompt.py; comparison.json schema/atomicity and the
FR-014 standalone contract live in test_evals_judge_artifact.py (size discipline).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.judge import JudgeError, judge_pair, judge_run
from cabal.evals.judge_prompt import TaskContext
from cabal.evals.matrix import (
    MANIFEST_FILENAME,
    METRICS_FILENAME,
    OUTPUT_FILENAME,
    PATCH_FILENAME,
    write_json_atomic,
)
from cabal.evals.metrics import TranscriptMetrics, build_metrics

RUN_ID = "evalrun-20260819T000000Z"
JUDGE_MODEL = "claude-judge-model"


# Shared helpers --------------------------------------------------------------


def _context(task_id: str = "sample-task", rubric_names: tuple[str, ...] = ()) -> TaskContext:
    return TaskContext(
        task_id=task_id,
        prompt_text="Implement the thing exactly as described.",
        rubric_names=rubric_names,
        rubric_texts=tuple(f"Rubric text for {name}" for name in rubric_names),
    )


def _build_cell(
    cell_dir: Path,
    *,
    task_id: str,
    config_name: str,
    repetition: int,
    diff_text: str = "diff --git a/x b/x\n+hello\n",
    output_text: str = "agent final output",
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
    (cell_dir / OUTPUT_FILENAME).write_text(output_text, encoding="utf-8")
    return cell_dir


def _answer(winner: str, confidence: float | None = 0.7, criteria: list[dict] | None = None) -> str:
    return json.dumps({"winner": winner, "confidence": confidence, "criteria": criteria or []})


def _queued_judge(*responses: str | BaseException) -> Callable[[str, str], str]:
    """A JudgeCall stub that returns/raises each scripted response in call order."""
    queue = list(responses)

    def _call(prompt: str, model: str) -> str:
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    return _call


def _build_run_dir(
    tmp_path: Path, *, baseline: str, candidate: str, tasks: list[str], runs: int
) -> Path:
    run_dir = tmp_path / "results" / RUN_ID
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": RUN_ID,
        "baseline": baseline,
        "candidate": candidate,
        "runs": runs,
        "tasks": tasks,
        "adapter": "fake-adapter",
        "created_at": "2026-08-19T00:00:00Z",
    }
    write_json_atomic(run_dir / MANIFEST_FILENAME, manifest)
    return run_dir


def _build_evals_root(tmp_path: Path, task_id: str) -> Path:
    evals_root = tmp_path / "evals"
    (evals_root / "tasks" / task_id).mkdir(parents=True)
    (evals_root / "tasks" / task_id / "prompt.md").write_text("Do the thing.", encoding="utf-8")
    return evals_root


@pytest.fixture
def pair_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """One baseline and one candidate cell, each with a complete metrics.json + artifacts."""
    baseline_dir = _build_cell(
        tmp_path / "baseline" / "1", task_id="sample-task", config_name="baseline", repetition=1
    )
    candidate_dir = _build_cell(
        tmp_path / "candidate" / "1", task_id="sample-task", config_name="candidate", repetition=1
    )
    return baseline_dir, candidate_dir


# judge_pair: order agreement --------------------------------------------------


class TestJudgePairOrderAgreement:
    def test_judge_pair_both_orders_favor_candidate_yields_candidate_winner(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """Both A/B orderings must be resolved back to baseline/candidate terms before comparing."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        criteria = [{"name": "correctness", "favored": "B", "note": "matches spec"}]
        judge_call = _queued_judge(
            _answer("B", confidence=0.8, criteria=criteria),  # A=baseline, B=candidate
            _answer("A", confidence=0.6),  # A=candidate, B=baseline
        )

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["winner"] == "candidate"

    def test_judge_pair_both_orders_favor_candidate_confidence_is_the_mean(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """Confidence must average both orders' scores, not just report one of them."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("B", confidence=0.8), _answer("A", confidence=0.6))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["confidence"] == pytest.approx(0.7)

    def test_judge_pair_both_orders_favor_candidate_sets_order_agreement_true(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """A decisive winner is only trustworthy when both position orders agree."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("B"), _answer("A"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["order_agreement"] is True

    def test_judge_pair_both_orders_favor_candidate_maps_criteria_to_baseline_candidate(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """Criteria favored fields must be translated out of raw A/B terms, same as the winner."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        criteria = [{"name": "correctness", "favored": "B", "note": "matches spec"}]
        judge_call = _queued_judge(_answer("B", criteria=criteria), _answer("A"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["criteria"][0]["favored"] == "candidate"


# judge_pair: disagreement and ties --------------------------------------------


class TestJudgePairDisagreement:
    def test_judge_pair_orders_disagree_yields_tie_winner(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """Position bias means a decisive winner requires agreement -- disagreement must fall to tie."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("A"), _answer("A"))  # baseline, then candidate

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["winner"] == "tie"

    def test_judge_pair_orders_disagree_sets_order_agreement_false(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """order_agreement is the caller's signal that this tie was a disagreement, not a real tie."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("A"), _answer("A"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["order_agreement"] is False

    def test_judge_pair_orders_disagree_confidence_is_null(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """A disagreement tie has no meaningful confidence figure to report."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("A", confidence=0.9), _answer("A", confidence=0.9))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["confidence"] is None

    def test_judge_pair_both_orders_genuinely_tie_reports_order_agreement_true(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """A real tie (both orders answer 'tie') is agreement, unlike a disagreement tie."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(_answer("tie"), _answer("tie"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert (pair["winner"], pair["order_agreement"]) == ("tie", True)


# judge_pair: judge_call failures ----------------------------------------------


class TestJudgePairFailures:
    def test_judge_pair_judge_call_raising_records_judge_error(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """A raised JudgeError from the call itself must become a recorded judge_error, not propagate."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(JudgeError("simulated CLI crash"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["winner"] == "judge_error"

    def test_judge_pair_judge_call_raising_records_error_detail(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """error_detail must carry the failure reason so a human can triage without re-running."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge(JudgeError("simulated CLI crash"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert "simulated CLI crash" in pair["error_detail"]

    def test_judge_pair_malformed_json_answer_records_judge_error(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """A non-JSON answer must be caught by parse_verdict and recorded, not raised out of judge_pair."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        judge_call = _queued_judge("this is not json at all")

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["winner"] == "judge_error"

    def test_judge_pair_markdown_fenced_json_answer_still_parses(
        self, pair_dirs: tuple[Path, Path]
    ) -> None:
        """Models sometimes wrap the verdict in ```json fences despite instructions -- must still parse."""
        # Arrange
        baseline_dir, candidate_dir = pair_dirs
        fenced = "```json\n" + _answer("B") + "\n```"
        judge_call = _queued_judge(fenced, _answer("A"))

        # Act
        pair = judge_pair(_context(), baseline_dir, candidate_dir, 1, JUDGE_MODEL, 20000, judge_call)

        # Assert
        assert pair["winner"] == "candidate"


# judge_run: remaining pairs still judged after a failure ----------------------


class TestJudgeRunRemainingPairsStillJudged:
    def test_judge_run_first_repetition_raises_second_still_succeeds(self, tmp_path: Path) -> None:
        """One judge_error must not prevent later repetitions of the same task from being judged."""
        # Arrange
        run_dir = _build_run_dir(
            tmp_path, baseline="baseline", candidate="candidate", tasks=["sample-task"], runs=2
        )
        for repetition in (1, 2):
            _build_cell(
                run_dir / "sample-task" / "baseline" / str(repetition),
                task_id="sample-task",
                config_name="baseline",
                repetition=repetition,
            )
            _build_cell(
                run_dir / "sample-task" / "candidate" / str(repetition),
                task_id="sample-task",
                config_name="candidate",
                repetition=repetition,
            )
        evals_root = _build_evals_root(tmp_path, "sample-task")
        judge_call = _queued_judge(
            JudgeError("rep1 crash"),  # rep1: only one call made before the pair errors out
            _answer("B"), _answer("A"),  # rep2: both orders favor candidate
        )

        # Act
        summaries = judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=judge_call)

        # Assert
        comparison = json.loads((run_dir / "sample-task" / "comparison.json").read_text(encoding="utf-8"))
        pairs_by_repetition = {pair["repetition"]: pair for pair in comparison["pairs"]}
        assert pairs_by_repetition[1]["winner"] == "judge_error"
        assert pairs_by_repetition[2]["winner"] == "candidate"
        assert summaries[0].judge_errors == 1

    def test_judge_run_first_repetition_malformed_second_still_succeeds(self, tmp_path: Path) -> None:
        """A malformed-JSON judge_error on one repetition must not block a later repetition's verdict."""
        # Arrange
        run_dir = _build_run_dir(
            tmp_path, baseline="baseline", candidate="candidate", tasks=["sample-task"], runs=2
        )
        for repetition in (1, 2):
            _build_cell(
                run_dir / "sample-task" / "baseline" / str(repetition),
                task_id="sample-task",
                config_name="baseline",
                repetition=repetition,
            )
            _build_cell(
                run_dir / "sample-task" / "candidate" / str(repetition),
                task_id="sample-task",
                config_name="candidate",
                repetition=repetition,
            )
        evals_root = _build_evals_root(tmp_path, "sample-task")
        judge_call = _queued_judge(
            _answer("B"), "not valid json",  # rep1: second order malformed
            _answer("tie"), _answer("tie"),  # rep2: genuine tie
        )

        # Act
        judge_run(run_dir, evals_root, JUDGE_MODEL, 20000, judge_call=judge_call)

        # Assert
        comparison = json.loads((run_dir / "sample-task" / "comparison.json").read_text(encoding="utf-8"))
        pairs_by_repetition = {pair["repetition"]: pair for pair in comparison["pairs"]}
        assert pairs_by_repetition[1]["winner"] == "judge_error"
        assert pairs_by_repetition[2]["winner"] == "tie"
