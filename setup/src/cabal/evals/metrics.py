# -*- coding: utf-8 -*-
"""Transcript parsing and metrics.json assembly per contracts/metrics.schema.json.

Mirrors `dotnetgen.providers.usage.parse_usage` semantics locally (that helper returns a
zero-defaulting `Usage`, which cannot express "unavailable"): a field the transcript did not
report is `None`, never a fabricated 0.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final

from cabal.evals.adapters.base import AdapterCapabilities
from cabal.evals.checks import CheckResult
from cabal.evals.worktree import DiffResult

SCHEMA_VERSION: Final[int] = 1

_USAGE_INPUT: Final[str] = "input_tokens"
_USAGE_OUTPUT: Final[str] = "output_tokens"
_USAGE_CACHE_READ: Final[str] = "cache_read_input_tokens"


@dataclass(frozen=True)
class TranscriptMetrics:
    """Agent-reported figures from one transcript.jsonl; None = the transcript did not report it."""

    tool_calls_total: int | None = None
    tool_calls_by_name: dict[str, int] | None = None
    num_turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cost_usd: float | None = None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _iter_events(path: Path) -> Iterator[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed


def _count_tool_uses(event: dict[str, Any], totals: dict[str, int]) -> None:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = block.get("name")
            key = name if isinstance(name, str) and name else "unknown"
            totals[key] = totals.get(key, 0) + 1


def parse_transcript(path: Path) -> TranscriptMetrics:
    """Extract tool-call counts and the terminal result event's figures from a transcript.jsonl."""
    path = Path(path)
    if not path.is_file():
        return TranscriptMetrics()
    tool_totals: dict[str, int] = {}
    saw_assistant = False
    result_event: dict[str, Any] | None = None
    for event in _iter_events(path):
        kind = event.get("type")
        if kind == "assistant":
            saw_assistant = True
            _count_tool_uses(event, tool_totals)
        elif kind == "result":
            result_event = event
    raw_usage = result_event.get("usage") if result_event is not None else None
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    return TranscriptMetrics(
        tool_calls_total=sum(tool_totals.values()) if saw_assistant else None,
        tool_calls_by_name=dict(tool_totals) if saw_assistant else None,
        num_turns=_as_int(result_event.get("num_turns")) if result_event is not None else None,
        input_tokens=_as_int(usage.get(_USAGE_INPUT)),
        output_tokens=_as_int(usage.get(_USAGE_OUTPUT)),
        cache_read_tokens=_as_int(usage.get(_USAGE_CACHE_READ)),
        cost_usd=_as_float(result_event.get("total_cost_usd")) if result_event is not None else None,
    )


def unrequested_changes(
    changed_files: Sequence[str], expected_files: Sequence[str]
) -> tuple[int | None, list[str] | None]:
    """Scope tracking is disabled — (None, None) — when the task declares no expected_files."""
    if not expected_files:
        return None, None
    unrequested = [
        path
        for path in changed_files
        if not any(fnmatch(path, pattern) for pattern in expected_files)
    ]
    return len(unrequested), unrequested


def _diff_group(diff: DiffResult | None, expected_files: Sequence[str]) -> dict[str, Any]:
    """A cell that failed before diff collection reports an empty diff — 0 is meaningful here."""
    if diff is None:
        return {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "unrequested_changes_count": None,
            "unrequested_files": None,
            "empty_diff": True,
        }
    count, files = unrequested_changes(diff.changed_files, expected_files)
    return {
        "files_changed": len(diff.changed_files),
        "insertions": diff.insertions,
        "deletions": diff.deletions,
        "unrequested_changes_count": count,
        "unrequested_files": files,
        "empty_diff": diff.empty_diff,
    }


def _agent_group(
    transcript: TranscriptMetrics, capabilities: AdapterCapabilities, wall_seconds: float
) -> dict[str, Any]:
    """Capability gating: fields the adapter's CLI cannot produce are forced to None (US6-AS2)."""
    return {
        "tool_calls_total": transcript.tool_calls_total if capabilities.tool_calls else None,
        "tool_calls_by_name": transcript.tool_calls_by_name if capabilities.tool_calls else None,
        "num_turns": transcript.num_turns,
        "input_tokens": transcript.input_tokens if capabilities.tokens else None,
        "output_tokens": transcript.output_tokens if capabilities.tokens else None,
        "cache_read_tokens": transcript.cache_read_tokens if capabilities.tokens else None,
        "cost_usd": transcript.cost_usd if capabilities.cost else None,
        "wall_seconds": round(max(wall_seconds, 0.0), 3),
    }


def build_metrics(
    *,
    run_id: str,
    task_id: str,
    config_name: str,
    repetition: int,
    adapter_name: str,
    status: str,
    failure_reason: str | None,
    wall_seconds: float,
    started_at: str,
    finished_at: str,
    capabilities: AdapterCapabilities,
    transcript: TranscriptMetrics,
    diff: DiffResult | None,
    expected_files: Sequence[str],
    checks: Sequence[CheckResult] = (),
) -> dict[str, Any]:
    """Assemble one schema-valid metrics.json payload; CheckResult fields mirror the schema 1:1."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "config_name": config_name,
        "repetition": repetition,
        "adapter": adapter_name,
        "status": status,
        "failure_reason": failure_reason,
        "started_at": started_at,
        "finished_at": finished_at,
        "agent": _agent_group(transcript, capabilities, wall_seconds),
        "diff": _diff_group(diff, expected_files),
        "checks": [asdict(check) for check in checks],
    }
