# -*- coding: utf-8 -*-
"""Aggregate reducer: all metrics.json + comparison.json under a run-id -> report.json payload.

Aggregation rules per data-model.md MatrixReport: failed runs count against task_pass_rate but
are excluded from quality means; stddev only at n>=3; all-null inputs yield a null mean with n
reflecting the available samples; pairwise win rate excludes ties and judge errors.
"""

from __future__ import annotations

import json
import os
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from cabal.evals.judge import COMPARISON_FILENAME
from cabal.evals.matrix import MANIFEST_FILENAME, METRICS_FILENAME, write_json_atomic
from cabal.evals.metrics import SCHEMA_VERSION

REPORT_JSON_FILENAME: Final[str] = "report.json"
REPORT_MD_FILENAME: Final[str] = "report.md"

METRIC_ORDER: Final[tuple[str, ...]] = (
    "task_pass_rate",
    "test_pass_rate",
    "build_success_rate",
    "unrequested_changes",
    "tool_calls",
    "tokens_total",
    "wall_seconds",
    "pairwise_win_rate",
)

_MIN_SAMPLES_FOR_STDDEV: Final[int] = 3


class ReportError(Exception):
    """The run directory cannot be reduced into a report (missing/invalid manifest or cells)."""


@dataclass(frozen=True)
class ReportBundle:
    """The schema-valid report payload plus advisory notes that must not enter report.json."""

    payload: dict[str, Any]
    notes: tuple[str, ...]


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / MANIFEST_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read run manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReportError(f"run manifest {path} is not a JSON object")
    for key in ("run_id", "baseline", "candidate", "runs", "tasks"):
        if key not in data:
            raise ReportError(f"run manifest {path} is missing {key!r}")
    return data


def _load_cells(run_dir: Path, tasks: Sequence[str], configs: Sequence[str]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for task_id in tasks:
        for config in configs:
            config_dir = run_dir / task_id / config
            if not config_dir.is_dir():
                continue
            for rep_dir in sorted(
                (child for child in config_dir.iterdir() if child.is_dir() and child.name.isdigit()),
                key=lambda child: int(child.name),
            ):
                path = rep_dir / METRICS_FILENAME
                if not path.is_file():
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(data, dict):
                    cells.append(data)
    return cells


def _checks(cell: dict[str, Any]) -> list[dict[str, Any]]:
    checks = cell.get("checks")
    return [check for check in checks if isinstance(check, dict)] if isinstance(checks, list) else []


def _is_completed(cell: dict[str, Any]) -> bool:
    return cell.get("status") == "completed"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _task_pass(cell: dict[str, Any]) -> float:
    """Every run has a sample here — failed runs count against the rate."""
    passed = _is_completed(cell) and all(
        check.get("status") == "passed" for check in _checks(cell)
    )
    return 1.0 if passed else 0.0


def _test_rate(cell: dict[str, Any]) -> float | None:
    passed = failed = 0
    found = False
    for check in _checks(cell):
        if check.get("kind") != "test":
            continue
        p, f = _number(check.get("passed_count")), _number(check.get("failed_count"))
        if p is None or f is None:
            continue
        passed += int(p)
        failed += int(f)
        found = True
    if not found or passed + failed == 0:
        return None
    return passed / (passed + failed)


def _build_rate(cell: dict[str, Any]) -> float | None:
    builds = [check for check in _checks(cell) if check.get("kind") == "build"]
    if not builds:
        return None
    return sum(1 for check in builds if check.get("status") == "passed") / len(builds)


def _unrequested(cell: dict[str, Any]) -> float | None:
    if not _is_completed(cell):
        return None
    diff = cell.get("diff")
    return _number(diff.get("unrequested_changes_count")) if isinstance(diff, dict) else None


def _agent_field(cell: dict[str, Any], field: str) -> float | None:
    if not _is_completed(cell):
        return None
    agent = cell.get("agent")
    return _number(agent.get(field)) if isinstance(agent, dict) else None


def _tokens_total(cell: dict[str, Any]) -> float | None:
    if not _is_completed(cell):
        return None
    agent = cell.get("agent")
    if not isinstance(agent, dict):
        return None
    input_tokens = _number(agent.get("input_tokens"))
    output_tokens = _number(agent.get("output_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    return input_tokens + output_tokens


_EXTRACTORS: Final[dict[str, Callable[[dict[str, Any]], float | None]]] = {
    "task_pass_rate": _task_pass,
    "test_pass_rate": _test_rate,
    "build_success_rate": _build_rate,
    "unrequested_changes": _unrequested,
    "tool_calls": lambda cell: _agent_field(cell, "tool_calls_total"),
    "tokens_total": _tokens_total,
    "wall_seconds": lambda cell: _agent_field(cell, "wall_seconds"),
}


def _stat_cell(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"mean": None, "min": None, "max": None, "stddev": None, "n": 0}
    stddev = (
        round(statistics.stdev(values), 4) if len(values) >= _MIN_SAMPLES_FOR_STDDEV else None
    )
    return {
        "mean": round(sum(values) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "stddev": stddev,
        "n": len(values),
    }


def _load_comparisons(run_dir: Path, tasks: Sequence[str]) -> tuple[list[dict[str, Any]], list[str]]:
    comparisons: list[dict[str, Any]] = []
    missing: list[str] = []
    for task_id in tasks:
        path = run_dir / task_id / COMPARISON_FILENAME
        if not path.is_file():
            missing.append(task_id)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            missing.append(task_id)
            continue
        if isinstance(data, dict):
            comparisons.append(data)
        else:
            missing.append(task_id)
    return comparisons, missing


def _win_rate_row(comparisons: Sequence[dict[str, Any]], configs: Sequence[str]) -> dict[str, Any]:
    """Ties and judge_errors are excluded; no decisive pairs -> null mean for both configs."""
    wins = {config: 0 for config in configs}
    for comparison in comparisons:
        baseline = str(comparison.get("baseline_config"))
        candidate = str(comparison.get("candidate_config"))
        pairs = comparison.get("pairs")
        for pair in pairs if isinstance(pairs, list) else []:
            winner = pair.get("winner") if isinstance(pair, dict) else None
            if winner == "baseline" and baseline in wins:
                wins[baseline] += 1
            elif winner == "candidate" and candidate in wins:
                wins[candidate] += 1
    decisive = sum(wins.values())
    per_config = {
        config: {
            "mean": round(wins[config] / decisive, 4) if decisive else None,
            "min": None,
            "max": None,
            "stddev": None,
            "n": decisive,
        }
        for config in configs
    }
    return {"metric": "pairwise_win_rate", "per_config": per_config}


def _failures(cells: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": str(cell.get("task_id")),
            "config_name": str(cell.get("config_name")),
            "repetition": int(cell.get("repetition", 0)) or 1,
            "reason": str(cell.get("failure_reason") or "unknown"),
        }
        for cell in cells
        if cell.get("status") == "failed"
    ]


def build_report(run_dir: Path) -> ReportBundle:
    """Reduce one run directory into a report.schema.json-valid payload plus advisory notes."""
    run_dir = Path(run_dir)
    manifest = _load_manifest(run_dir)
    tasks = [str(task) for task in manifest["tasks"]]
    configs = [str(manifest["baseline"]), str(manifest["candidate"])]
    cells = _load_cells(run_dir, tasks, configs)
    if not cells:
        raise ReportError(f"no metrics.json artifacts found under {run_dir}")
    comparisons, missing = _load_comparisons(run_dir, tasks)

    metrics_rows: list[dict[str, Any]] = []
    for metric in METRIC_ORDER[:-1]:
        extractor = _EXTRACTORS[metric]
        per_config: dict[str, Any] = {}
        for config in configs:
            samples = [
                value
                for cell in cells
                if cell.get("config_name") == config
                for value in (extractor(cell),)
                if value is not None
            ]
            per_config[config] = _stat_cell(samples)
        metrics_rows.append({"metric": metric, "per_config": per_config})
    metrics_rows.append(_win_rate_row(comparisons, configs))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(manifest["run_id"]),
        "created_at": _utc_now(),
        "tasks": tasks,
        "configs": configs,
        "runs_per_cell": int(manifest["runs"]),
        "metrics_rows": metrics_rows,
        "failures": _failures(cells),
    }
    notes = tuple(
        [
            f"no comparison.json for task(s): {', '.join(missing)} - "
            "pairwise_win_rate reflects judged tasks only; run `judge` first for full coverage"
        ]
        if missing
        else []
    )
    return ReportBundle(payload=payload, notes=notes)


def write_report(run_dir: Path, bundle: ReportBundle, markdown: str) -> tuple[Path, Path]:
    """Persist report.json and report.md atomically into the run directory."""
    run_dir = Path(run_dir)
    json_path = run_dir / REPORT_JSON_FILENAME
    md_path = run_dir / REPORT_MD_FILENAME
    write_json_atomic(json_path, bundle.payload)
    tmp = md_path.parent / (md_path.name + ".tmp")
    tmp.write_text(markdown, encoding="utf-8")
    os.replace(tmp, md_path)
    return json_path, md_path
