"""Small OKF preflight card for scope, risk, and context-budget selection."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from cabal.okf.index import fts_available, search_index
from cabal.okf.usage import append_usage


RISK_RULES: tuple[tuple[str, str, str], ...] = (
    (r"\bmcp\b|model context protocol", "mcp_protocol", "Touches an MCP protocol surface."),
    (r"\bhook|pre[- ]?process", "hook_runtime", "Mentions hooks or preprocessing."),
    (r"\bcabal|tui|textual|knowledge screen", "cabal_ui", "Touches Cabal UI or knowledge surfaces."),
    (r"\bclaude\b|\bcursor\b", "cross_client", "Needs cross-client behavior."),
    (r"\btoken|context budget|rag|retriev", "token_heavy", "Context volume or retrieval matters."),
    (r"\bglobal/|settings\.json|CLAUDE\.md", "global_config", "May affect deployed global config."),
)

AREA_RULES: tuple[tuple[str, str], ...] = (
    (r"\bokf|knowledge|rag|retriev|context pack", "okf"),
    (r"\bmcp\b|model context protocol", "mcp"),
    (r"\bhook|pre[- ]?process", "hooks"),
    (r"\bcabal|tui|textual", "cabal_knowledge"),
    (r"\bclaude session|transcript|usage ledger", "claude_sessions"),
    (r"\bcursor\b", "cursor"),
)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _scope(task: str, risk_flags: list[str]) -> str:
    word_count = len(re.findall(r"\w+", task))
    score = 0
    if word_count > 10:
        score += 1
    if word_count > 28:
        score += 1
    if word_count > 55:
        score += 1
    score += sum(
        1
        for flag in risk_flags
        if flag in {"mcp_protocol", "hook_runtime", "cross_client", "global_config"}
    )
    score = min(score, 3)
    return ("S", "M", "L", "XL")[score]


def _budget(scope: str, risk_flags: list[str]) -> str:
    if scope == "S" and not risk_flags:
        return "tiny"
    if scope == "XL" or len(risk_flags) >= 4:
        return "full"
    return "focused"


def run_preflight(
    db_path: Path,
    task: str,
    *,
    client: str = "cabal",
    entrypoint: str = "cli",
    usage_path: Path | None = None,
    record_usage: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    task_lower = task.lower()
    risk_flags = _unique(
        [flag for pattern, flag, _ in RISK_RULES if re.search(pattern, task_lower)]
    )
    why = [
        explanation
        for pattern, flag, explanation in RISK_RULES
        if flag in risk_flags and re.search(pattern, task_lower)
    ]

    likely_areas = _unique(
        [area for pattern, area in AREA_RULES if re.search(pattern, task_lower)]
    )
    index_state = "missing"
    matches: list[dict[str, Any]] = []
    db = Path(db_path)
    if db.exists():
        try:
            index_state = "fresh" if fts_available(db) else "unusable"
            if index_state == "fresh":
                matches = search_index(db, task, limit=5)
                likely_areas.extend(str(row["id"]) for row in matches)
                why.append(f"Index search found {len(matches)} likely OKF concepts.")
        except Exception as exc:  # pragma: no cover - defensive UI path
            index_state = "error"
            why.append(f"Index check failed: {exc}")
    else:
        why.append(f"Index not found at {db}. Run `python -m cabal.okf index` first.")

    likely_areas = _unique(likely_areas)
    scope = _scope(task, risk_flags)
    recommended_budget = _budget(scope, risk_flags)
    if not why:
        why.append("No high-risk keywords found; use a small explicit context request if needed.")
    why.append(f"Scope {scope} selected from task length and {len(risk_flags)} risk flags.")
    why.append(f"Recommended `{recommended_budget}` context budget.")

    report = {
        "task": task,
        "scope": scope,
        "risk_flags": risk_flags,
        "likely_areas": likely_areas,
        "recommended_budget": recommended_budget,
        "index_state": index_state,
        "why": why,
    }
    if record_usage:
        append_usage(
            action="okf_preflight",
            query=task,
            budget=recommended_budget,
            client=client,
            entrypoint=entrypoint,
            included_concepts=[item for item in likely_areas if ":" in item],
            evidence_edge_count=0,
            estimated_tokens=round(len(str(report)) / 4),
            cache_state=index_state,
            duration_ms=round((time.perf_counter() - started) * 1000),
            usage_path=usage_path,
        )
    return report


def render_preflight_human(report: dict[str, Any]) -> str:
    lines = [
        "OKF preflight",
        f"scope: {report['scope']}",
        f"budget: {report['recommended_budget']}",
        f"index: {report['index_state']}",
        f"risk: {', '.join(report['risk_flags']) if report['risk_flags'] else 'none'}",
        f"likely: {', '.join(report['likely_areas']) if report['likely_areas'] else 'none'}",
        "",
        "Why",
    ]
    for reason in report.get("why", []):
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"
