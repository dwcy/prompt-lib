# -*- coding: utf-8 -*-
"""Web payload shaping for Claude transcript sessions.

The parser and pricing math stay in cabal.session_reader/session_pricing; this
module only adds pagination, tab payloads, and action-friendly lookup helpers.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cabal import session_reader
from cabal.models.session import Session, SessionSummary, TokenUsage
from cabal.session_pricing import load_pricing, lookup
from cabal.webapi.envelope import ApiError, compute_precondition_digest

SessionTab = Literal["overview", "activity", "raw", "triggers"]

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _projects_dir() -> Path:
    return session_reader._PROJECTS_DIR  # type: ignore[attr-defined]


def _audit_path() -> Path:
    return session_reader._WRITE_AUDIT_PATH  # type: ignore[attr-defined]


def _load_summaries(projects_dir: Path | None = None) -> list[tuple[Session, SessionSummary]]:
    pricing = load_pricing()
    rows: list[tuple[Session, SessionSummary]] = []
    for session in session_reader.scan_projects_dir(projects_dir or _projects_dir()):
        entries = session_reader.read_session(session)
        summary = session_reader.compute_summary(session, entries, pricing)
        rows.append((session, summary))
    session_reader.infer_session_tree([summary for _session, summary in rows])
    return rows


def _matches_project(summary: SessionSummary, project: str | None) -> bool:
    if not project:
        return True
    needle = project.lower()
    return needle in summary.project_path.lower()


def _sort_key(row: tuple[Session, SessionSummary], sort: str) -> tuple:
    session, summary = row
    # start_time is tz-aware; a naive datetime.min fallback would make sort()
    # raise on aware-vs-naive comparison when one transcript has no timestamp.
    started = summary.start_time or datetime.min.replace(tzinfo=timezone.utc)
    if sort == "cost_desc":
        return (summary.estimated_cost_usd, started, session.session_id)
    if sort == "tokens_desc":
        tokens = summary.total_input_tokens + summary.total_output_tokens
        return (tokens, started, session.session_id)
    if sort == "duration_desc":
        return (summary.duration_seconds, started, session.session_id)
    return (started, session.session_id)


def _model_rows(summary: SessionSummary) -> list[dict]:
    pricing = load_pricing()
    rows = []
    for model, usage in sorted(summary.model_breakdown.items()):
        entry = lookup(model, pricing)
        cost = (
            usage.input_tokens * entry.input_usd_per_mtok / 1_000_000
            + usage.output_tokens * entry.output_usd_per_mtok / 1_000_000
            + usage.cache_read_input_tokens * entry.cache_read_usd_per_mtok / 1_000_000
            + usage.cache_creation_input_tokens * entry.cache_write_usd_per_mtok / 1_000_000
        )
        rows.append(
            {
                "model": model,
                "tokens_in": usage.input_tokens,
                "tokens_out": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_input_tokens,
                "cache_write_tokens": usage.cache_creation_input_tokens,
                "cost_usd": round(cost, 6),
            }
        )
    return rows


def _session_row(session: Session, summary: SessionSummary) -> dict:
    return {
        "session_id": summary.session_id,
        "project": summary.project_path,
        "branch": summary.git_branch,
        "title": summary.title,
        "started_at": _iso(summary.start_time),
        "duration_seconds": round(summary.duration_seconds, 3),
        "cost_usd": round(summary.estimated_cost_usd, 6),
        "tokens_in": summary.total_input_tokens,
        "tokens_out": summary.total_output_tokens,
        "cache_read_tokens": summary.total_cache_read_tokens,
        "cache_write_tokens": summary.total_cache_write_tokens,
        "agent_count": summary.agent_count,
        "skill_count": len(summary.skills),
        "tool_count": len(summary.tool_calls),
        "hook_count": len(summary.hook_events),
        "message_count": summary.message_count,
        "tool_error_count": summary.tool_error_count,
        "files_written": summary.files_written,
        "parent_id": summary.parent_session_id,
        "child_ids": list(summary.child_session_ids),
        "has_raw_log": session.log_path.is_file(),
        "file_size_bytes": session.file_size_bytes,
    }


def _totals(rows: list[tuple[Session, SessionSummary]]) -> dict:
    return {
        "session_count": len(rows),
        "tokens_in": sum(summary.total_input_tokens for _session, summary in rows),
        "tokens_out": sum(summary.total_output_tokens for _session, summary in rows),
        "cache_read_tokens": sum(summary.total_cache_read_tokens for _session, summary in rows),
        "cache_write_tokens": sum(summary.total_cache_write_tokens for _session, summary in rows),
        "cost_usd": round(sum(summary.estimated_cost_usd for _session, summary in rows), 6),
        "duration_seconds": round(sum(summary.duration_seconds for _session, summary in rows), 3),
        "files_written": sum(summary.files_written for _session, summary in rows),
        "agent_count": sum(summary.agent_count for _session, summary in rows),
    }


def list_sessions_payload(
    *,
    project: str | None = None,
    sort: str = "date_desc",
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    projects_dir: Path | None = None,
) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))
    try:
        offset = int(cursor or "0")
    except ValueError as exc:
        raise ApiError(422, "params_invalid", "cursor must be an integer offset") from exc
    offset = max(0, offset)

    rows = [
        row
        for row in _load_summaries(projects_dir)
        if _matches_project(row[1], project)
    ]
    rows.sort(key=lambda row: _sort_key(row, sort), reverse=True)
    page = rows[offset : offset + limit]
    next_offset = offset + len(page)
    return {
        "totals": _totals(rows),
        "items": [_session_row(session, summary) for session, summary in page],
        "next_cursor": str(next_offset) if next_offset < len(rows) else None,
        "page_size": limit,
        "sort": sort,
        "project": project,
    }


def find_session(session_id: str, projects_dir: Path | None = None) -> tuple[Session, SessionSummary]:
    for session, summary in _load_summaries(projects_dir):
        if session.session_id == session_id:
            return session, summary
    raise ApiError(404, "session_not_found", f"Unknown session {session_id!r}")


def session_digest(session_id: str) -> str:
    session, _summary = find_session(session_id)
    try:
        stat = session.log_path.stat()
        state = {
            "session_id": session_id,
            "path": str(session.log_path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
    except OSError:
        state = {"session_id": session_id, "path": str(session.log_path), "missing": True}
    return compute_precondition_digest(state)


def session_detail_payload(session_id: str, tab: SessionTab) -> dict:
    session, summary = find_session(session_id)
    entries = session_reader.read_session(session)
    base = {"session_id": session_id, "tab": tab}
    if tab == "overview":
        payload = {
            "summary": _session_row(session, summary),
            "models": _model_rows(summary),
            "children": list(summary.child_session_ids),
        }
    elif tab == "activity":
        payload = {
            "skills": [asdict(skill) for skill in summary.skills],
            "agents": [asdict(agent) for agent in summary.agents],
            "tools": [asdict(tool) for tool in summary.tool_calls],
            "hooks": [asdict(hook) for hook in summary.hook_events],
        }
    elif tab == "raw":
        try:
            text = session.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        payload = {"path": str(session.log_path), "text": text[-200_000:], "truncated": len(text) > 200_000}
    elif tab == "triggers":
        triggers = session_reader.read_write_audit(_audit_path(), since=summary.start_time)
        payload = {"events": [asdict(event) for event in triggers]}
    else:
        raise ApiError(422, "params_invalid", f"Unknown session tab {tab!r}")
    return {**base, "payload": payload, "entry_count": len(entries)}


def delete_session_payload(session_id: str) -> dict:
    session, _summary = find_session(session_id)
    path = session.log_path
    session_reader.delete_session(session)
    return {"session_id": session_id, "removed": str(path)}
