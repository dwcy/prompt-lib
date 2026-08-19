# -*- coding: utf-8 -*-
"""Pairwise LLM judge over recorded results: both-orders position-bias control per research.md R6.

Repetition i of the baseline is judged against repetition i of the candidate, twice with A/B
swapped; order disagreement is recorded as a tie with `order_agreement: false`. Every judge-call
or parse failure becomes a `judge_error` verdict — the pair loop never propagates an exception.
The judge call is an injectable callable so tests stub it exactly like matrix's FakeAdapter.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cabal.evals import judge_prompt
from cabal.evals.matrix import MANIFEST_FILENAME, METRICS_FILENAME, write_json_atomic
from cabal.evals.metrics import SCHEMA_VERSION

COMPARISON_FILENAME: Final[str] = "comparison.json"
JUDGE_EXECUTABLE: Final[str] = "claude"
JUDGE_TIMEOUT_SECONDS: Final[int] = 300
_STDERR_TAIL_CHARS: Final[int] = 400

_SIDES: Final[frozenset[str]] = frozenset({"A", "B", "tie"})
_FENCE: Final[re.Pattern[str]] = re.compile(r"^\s*```[a-zA-Z]*\s*|\s*```\s*$")

JudgeCall = Callable[[str, str], str]


class JudgeError(Exception):
    """A judge invocation or verdict parse failed; recorded per pair, never propagated."""


@dataclass(frozen=True)
class RawVerdict:
    """One order's parsed model answer, still in A/B terms."""

    winner: str
    confidence: float | None
    criteria: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class TaskJudgeSummary:
    """What the CLI reports for one judged task."""

    task_id: str
    pairs_total: int
    judge_errors: int
    comparison_path: Path


def default_judge_call(prompt: str, model: str) -> str:
    """One-shot `claude -p` with the user's real login (no CLAUDE_CONFIG_DIR relocation)."""
    exe = shutil.which(JUDGE_EXECUTABLE)
    if exe is None:
        raise JudgeError(f"`{JUDGE_EXECUTABLE}` not found on PATH")
    try:
        # Prompt via stdin, never argv: the Windows .cmd shim re-parses argv and a multi-line
        # prompt silently drops every flag after it (same fix as adapters/claude_code.py).
        proc = subprocess.run(
            [exe, "-p", "--output-format", "json", "--model", model],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=prompt,
            timeout=JUDGE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise JudgeError(f"judge call failed: {exc}") from exc
    if proc.returncode != 0:
        raise JudgeError(
            f"judge exited {proc.returncode}: {proc.stderr.strip()[:_STDERR_TAIL_CHARS]}"
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge CLI envelope is not JSON: {exc}") from exc
    # `--output-format json` emits a single result object in some CLI versions and an array of
    # events (init, ..., result) in others — accept both by extracting the result-type event.
    if isinstance(envelope, list):
        envelope = next(
            (e for e in envelope if isinstance(e, dict) and e.get("type") == "result"), None
        )
    if not isinstance(envelope, dict):
        raise JudgeError("judge CLI envelope carried no result object")
    result = envelope.get("result")
    if envelope.get("is_error") or not isinstance(result, str):
        raise JudgeError(f"judge CLI reported an error: {str(result)[:_STDERR_TAIL_CHARS]}")
    return result


def _parse_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0.0 <= float(value) <= 1.0 else None


def parse_verdict(text: str) -> RawVerdict:
    """Parse the model's JSON-only answer, stripping markdown fences defensively."""
    stripped = _FENCE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise JudgeError("judge answer contains no JSON object")
    try:
        data = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge answer is not valid JSON: {exc}") from exc
    winner = data.get("winner") if isinstance(data, dict) else None
    if winner not in _SIDES:
        raise JudgeError(f"judge winner must be A|B|tie, got {winner!r}")
    criteria: list[dict[str, str]] = []
    raw_criteria = data.get("criteria")
    if isinstance(raw_criteria, list):
        for item in raw_criteria:
            if not isinstance(item, dict):
                continue
            name, favored = item.get("name"), item.get("favored")
            if isinstance(name, str) and name and favored in _SIDES:
                note = item.get("note")
                criteria.append(
                    {"name": name, "favored": favored, "note": note if isinstance(note, str) else ""}
                )
    return RawVerdict(
        winner=winner,
        confidence=_parse_confidence(data.get("confidence")),
        criteria=tuple(criteria),
    )


def _map_side(side: str, a_is_baseline: bool) -> str:
    if side == "tie":
        return "tie"
    if side == "A":
        return "baseline" if a_is_baseline else "candidate"
    return "candidate" if a_is_baseline else "baseline"


def _map_criteria(verdict: RawVerdict, a_is_baseline: bool) -> list[dict[str, str]]:
    return [
        {**item, "favored": _map_side(item["favored"], a_is_baseline)}
        for item in verdict.criteria
    ]


def _error_pair(repetition: int, truncated: bool, detail: str) -> dict[str, Any]:
    return {
        "repetition": repetition,
        "winner": "judge_error",
        "confidence": None,
        "order_agreement": False,
        "criteria": [],
        "truncated": truncated,
        "error_detail": detail[:_STDERR_TAIL_CHARS],
    }


def _combine(
    repetition: int, first: RawVerdict, second: RawVerdict, truncated: bool
) -> dict[str, Any]:
    """Map both orders back to baseline/candidate; only agreement yields a decisive winner."""
    winner_first = _map_side(first.winner, a_is_baseline=True)
    winner_second = _map_side(second.winner, a_is_baseline=False)
    criteria = _map_criteria(first, a_is_baseline=True)
    if winner_first != winner_second:
        winner, agreement, confidence = "tie", False, None
    else:
        winner, agreement = winner_first, True
        confidences = [c for c in (first.confidence, second.confidence) if c is not None]
        confidence = (
            round(sum(confidences) / len(confidences), 4)
            if winner != "tie" and confidences
            else None
        )
    return {
        "repetition": repetition,
        "winner": winner,
        "confidence": confidence,
        "order_agreement": agreement,
        "criteria": criteria,
        "truncated": truncated,
        "error_detail": None,
    }


def judge_pair(
    context: judge_prompt.TaskContext,
    baseline_dir: Path,
    candidate_dir: Path,
    repetition: int,
    judge_model: str,
    diff_char_limit: int,
    judge_call: JudgeCall,
) -> dict[str, Any]:
    """Judge one repetition pairing in both orders; any failure becomes a judge_error verdict."""
    if not (baseline_dir / METRICS_FILENAME).is_file() or not (
        candidate_dir / METRICS_FILENAME
    ).is_file():
        return _error_pair(repetition, False, "cell artifacts missing (no metrics.json)")
    baseline = judge_prompt.load_cell_evidence(baseline_dir, diff_char_limit)
    candidate = judge_prompt.load_cell_evidence(candidate_dir, diff_char_limit)
    truncated = baseline.truncated or candidate.truncated
    try:
        first = parse_verdict(
            judge_call(judge_prompt.build_judge_prompt(context, baseline, candidate), judge_model)
        )
        second = parse_verdict(
            judge_call(judge_prompt.build_judge_prompt(context, candidate, baseline), judge_model)
        )
    except JudgeError as exc:
        return _error_pair(repetition, truncated, str(exc))
    return _combine(repetition, first, second, truncated)


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / MANIFEST_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeError(f"cannot read run manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgeError(f"run manifest {path} is not a JSON object")
    for key in ("run_id", "baseline", "candidate", "runs", "tasks"):
        if key not in data:
            raise JudgeError(f"run manifest {path} is missing {key!r}")
    return data


def _select_tasks(manifest: dict[str, Any], task_filter: Sequence[str] | None) -> list[str]:
    tasks = [str(task) for task in manifest["tasks"]]
    if task_filter is None:
        return tasks
    missing = [task for task in task_filter if task not in tasks]
    if missing:
        raise JudgeError(f"task id(s) not in this run: {', '.join(missing)}")
    return list(task_filter)


def judge_run(
    run_dir: Path,
    evals_root: Path,
    judge_model: str,
    diff_char_limit: int,
    task_filter: Sequence[str] | None = None,
    judge_call: JudgeCall = default_judge_call,
    progress: Callable[[str], None] | None = None,
) -> list[TaskJudgeSummary]:
    """Judge every repetition pair per task; re-judging overwrites comparison.json atomically."""
    run_dir = Path(run_dir)
    manifest = _load_manifest(run_dir)
    run_id = str(manifest["run_id"])
    baseline_name, candidate_name = str(manifest["baseline"]), str(manifest["candidate"])
    runs = int(manifest["runs"])
    summaries: list[TaskJudgeSummary] = []
    for task_id in _select_tasks(manifest, task_filter):
        context = judge_prompt.load_task_context(evals_root, task_id)
        pairs = [
            judge_pair(
                context,
                run_dir / task_id / baseline_name / str(repetition),
                run_dir / task_id / candidate_name / str(repetition),
                repetition,
                judge_model,
                diff_char_limit,
                judge_call,
            )
            for repetition in range(1, runs + 1)
        ]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": task_id,
            "baseline_config": baseline_name,
            "candidate_config": candidate_name,
            "judge_model": judge_model,
            "rubrics": list(context.rubric_names),
            "pairs": pairs,
        }
        comparison_path = run_dir / task_id / COMPARISON_FILENAME
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(comparison_path, payload)
        summary = TaskJudgeSummary(
            task_id=task_id,
            pairs_total=len(pairs),
            judge_errors=sum(1 for pair in pairs if pair["winner"] == "judge_error"),
            comparison_path=comparison_path,
        )
        summaries.append(summary)
        if progress is not None:
            progress(
                f"{task_id}: {summary.pairs_total} pair(s) judged, "
                f"{summary.judge_errors} judge error(s)"
            )
    return summaries
