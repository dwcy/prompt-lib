# -*- coding: utf-8 -*-
"""Renderers for the aggregate report: compact markdown for report.md and a rich terminal table."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from rich.table import Table

_NA: Final[str] = "n/a"


def _format_cell(cell: dict[str, Any]) -> str:
    mean = cell.get("mean")
    if mean is None:
        return f"{_NA} (n={cell.get('n', 0)})"
    text = f"{mean:g}"
    stddev = cell.get("stddev")
    if stddev is not None:
        text += f" +/-{stddev:g}"
    return f"{text} (n={cell.get('n', 0)})"


def _configs(report: dict[str, Any]) -> list[str]:
    return [str(config) for config in report.get("configs", [])]


def render_markdown(report: dict[str, Any], notes: Sequence[str] = ()) -> str:
    """One compact markdown document: header facts, metric table, failures, advisory notes."""
    configs = _configs(report)
    lines = [
        f"# Eval report: {report.get('run_id')}",
        "",
        f"- created: {report.get('created_at')}",
        f"- tasks: {', '.join(str(task) for task in report.get('tasks', []))}",
        f"- runs per cell: {report.get('runs_per_cell')}",
        "",
        "| Metric | " + " | ".join(configs) + " |",
        "| --- | " + " | ".join("---" for _ in configs) + " |",
    ]
    for row in report.get("metrics_rows", []):
        per_config = row.get("per_config", {})
        cells = " | ".join(_format_cell(per_config.get(config, {})) for config in configs)
        lines.append(f"| {row.get('metric')} | {cells} |")
    lines += ["", "## Failures", ""]
    failures = report.get("failures", [])
    if failures:
        lines += [
            f"- {failure.get('task_id')}/{failure.get('config_name')}/"
            f"{failure.get('repetition')}: {failure.get('reason')}"
            for failure in failures
        ]
    else:
        lines.append("No failed runs.")
    if notes:
        lines += ["", "## Notes", ""]
        lines += [f"- {note}" for note in notes]
    lines.append("")
    return "\n".join(lines)


def build_terminal_table(report: dict[str, Any]) -> Table:
    """The rich table the CLI prints: metric rows, one column per config."""
    configs = _configs(report)
    table = Table(
        title=f"Eval report: {report.get('run_id')}",
        caption=f"{len(report.get('tasks', []))} task(s), "
        f"{report.get('runs_per_cell')} run(s) per cell",
    )
    table.add_column("Metric", style="bold")
    for config in configs:
        table.add_column(config, justify="right")
    for row in report.get("metrics_rows", []):
        per_config = row.get("per_config", {})
        table.add_row(
            str(row.get("metric")),
            *(_format_cell(per_config.get(config, {})) for config in configs),
        )
    return table
