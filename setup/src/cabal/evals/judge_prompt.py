# -*- coding: utf-8 -*-
"""Judge prompt assembly: task context + rubrics + per-cell evidence with per-file diff truncation.

Kept out of judge.py per the size discipline: judge.py owns pairing and verdict mechanics while
this module owns everything about what the judge model actually reads. Per FR-014 the loaders here
work from a recorded results dir plus the evals tree alone — no worktree, no repo, no agent.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cabal.evals.definitions_model import (
    PROMPT_FILENAME,
    RUBRICS_DIRNAME,
    TASK_FILENAME,
    TASKS_DIRNAME,
)
from cabal.evals.matrix import METRICS_FILENAME, OUTPUT_FILENAME, PATCH_FILENAME

TRUNCATION_MARKER: Final[str] = "\n[truncated]\n"
MISSING_DIFF_TEXT: Final[str] = "(no diff captured)"
MISSING_OUTPUT_TEXT: Final[str] = "(no agent output captured)"
MISSING_PROMPT_TEXT: Final[str] = "(task prompt unavailable in the evals tree)"

_DIFF_HEADER: Final[re.Pattern[str]] = re.compile(r"^(?=diff --git )", re.MULTILINE)

VERDICT_INSTRUCTIONS: Final[str] = (
    "Compare Solution A and Solution B against the task prompt and every rubric criterion. "
    "Weigh the deterministic check results heavily; they are ground truth. Answer ONLY with a "
    "single JSON object and nothing else — no markdown fences, no prose:\n"
    '{"winner": "A"|"B"|"tie", "confidence": <number between 0 and 1>, '
    '"criteria": [{"name": "<criterion>", "favored": "A"|"B"|"tie", "note": "<short reason>"}]}'
)


@dataclass(frozen=True)
class TaskContext:
    """Judge-relevant slice of one task definition, read leniently from the evals tree."""

    task_id: str
    prompt_text: str
    rubric_names: tuple[str, ...]
    rubric_texts: tuple[str, ...]


@dataclass(frozen=True)
class CellEvidence:
    """One recorded cell's artifacts, ready for embedding into the judge prompt."""

    diff_text: str
    output_text: str
    check_summary: str
    truncated: bool


def truncate_diff(patch_text: str, char_limit: int) -> tuple[str, bool]:
    """Truncate each per-file chunk of a unified diff at `char_limit` chars with a visible marker."""
    chunks = [chunk for chunk in _DIFF_HEADER.split(patch_text) if chunk]
    if not chunks:
        return patch_text, False
    truncated = False
    kept: list[str] = []
    for chunk in chunks:
        if len(chunk) > char_limit:
            kept.append(chunk[:char_limit] + TRUNCATION_MARKER)
            truncated = True
        else:
            kept.append(chunk)
    return "".join(kept), truncated


def _rubric_names(task_dir: Path) -> tuple[str, ...]:
    task_file = task_dir / TASK_FILENAME
    if not task_file.is_file():
        return ()
    try:
        data = tomllib.loads(task_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ()
    rubrics = data.get("rubrics")
    if not isinstance(rubrics, list):
        return ()
    return tuple(name for name in rubrics if isinstance(name, str) and name)


def load_task_context(evals_root: Path, task_id: str) -> TaskContext:
    """Read prompt.md and rubric files leniently — a judge run must not demand repo/ref validity."""
    evals_root = Path(evals_root)
    task_dir = evals_root / TASKS_DIRNAME / task_id
    prompt_file = task_dir / PROMPT_FILENAME
    prompt_text = (
        prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else MISSING_PROMPT_TEXT
    )
    names = _rubric_names(task_dir)
    texts: list[str] = []
    for name in names:
        rubric_file = evals_root / RUBRICS_DIRNAME / f"{name}.md"
        texts.append(
            rubric_file.read_text(encoding="utf-8")
            if rubric_file.is_file()
            else f"(rubric {name!r} not found)"
        )
    return TaskContext(
        task_id=task_id,
        prompt_text=prompt_text,
        rubric_names=names,
        rubric_texts=tuple(texts),
    )


def _check_summary(metrics: dict[str, Any]) -> str:
    status = metrics.get("status", "unknown")
    reason = metrics.get("failure_reason")
    lines = [f"run status: {status}" + (f" ({reason})" if reason else "")]
    checks = metrics.get("checks")
    if not isinstance(checks, list) or not checks:
        lines.append("checks: none recorded")
        return "\n".join(lines)
    for check in checks:
        if not isinstance(check, dict):
            continue
        counts = ""
        if check.get("passed_count") is not None or check.get("failed_count") is not None:
            counts = f", {check.get('passed_count')} passed / {check.get('failed_count')} failed"
        lines.append(
            f"- [{check.get('kind')}] {check.get('status')} (exit {check.get('exit_code')}{counts})"
        )
    return "\n".join(lines)


def _read_text(path: Path, fallback: str) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else fallback
    except OSError:
        return fallback


def load_cell_evidence(cell_dir: Path, diff_char_limit: int) -> CellEvidence:
    """Load one cell's diff/output/check summary; absent artifacts become explicit placeholders."""
    cell_dir = Path(cell_dir)
    raw_diff = _read_text(cell_dir / PATCH_FILENAME, MISSING_DIFF_TEXT)
    diff_text, truncated = truncate_diff(raw_diff, diff_char_limit)
    output_text = _read_text(cell_dir / OUTPUT_FILENAME, MISSING_OUTPUT_TEXT)
    metrics_text = _read_text(cell_dir / METRICS_FILENAME, "")
    try:
        metrics = json.loads(metrics_text) if metrics_text else {}
    except ValueError:
        metrics = {}
    summary = _check_summary(metrics if isinstance(metrics, dict) else {})
    return CellEvidence(
        diff_text=diff_text,
        output_text=output_text,
        check_summary=summary,
        truncated=truncated,
    )


def _solution_section(label: str, evidence: CellEvidence) -> str:
    return (
        f"# Solution {label}\n\n"
        f"## Diff\n```diff\n{evidence.diff_text}\n```\n\n"
        f"## Agent output\n{evidence.output_text}\n\n"
        f"## Deterministic checks\n{evidence.check_summary}\n"
    )


def build_judge_prompt(context: TaskContext, side_a: CellEvidence, side_b: CellEvidence) -> str:
    """Assemble the full judge prompt for one A/B ordering of a pair."""
    parts = [
        "You are an impartial judge comparing two AI coding agents' solutions to the same task.",
        f"# Task prompt\n\n{context.prompt_text}",
    ]
    for name, text in zip(context.rubric_names, context.rubric_texts, strict=True):
        parts.append(f"# Rubric: {name}\n\n{text}")
    parts.append(_solution_section("A", side_a))
    parts.append(_solution_section("B", side_b))
    parts.append(f"# Instructions\n\n{VERDICT_INSTRUCTIONS}")
    return "\n\n".join(parts)
