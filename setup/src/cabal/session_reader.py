# > 400 LoC justified: single I/O service module — scan → read → parse → aggregate → link tree; splitting would fragment one pipeline across multiple files.
# -*- coding: utf-8 -*-
"""Session reader — scan ~/.claude/projects/, parse JSONL transcripts, compute summaries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

from cabal.models.session import (
    AgentInvocation,
    HookEvent,
    LogEntry,
    Session,
    SessionSummary,
    SkillInvocation,
    TokenUsage,
    ToolInvocation,
    TriggerEvent,
)
from cabal.session_pricing import PricingEntry, lookup

_AGENT_TOOL_NAMES = frozenset({"Task", "Agent"})
_PROJECTS_DIR = Path.home() / ".claude" / "projects"
_WRITE_AUDIT_PATH = Path.home() / ".claude" / "write_audit.jsonl"


def _tool_preview(name: str, inp: dict) -> str:
    """Return a short human-readable summary of a tool call's input."""
    if name in ("Read", "Write", "Edit", "NotebookEdit"):
        return inp.get("file_path", inp.get("notebook_path", ""))[:80]
    if name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description", "")
        return (desc or cmd)[:80]
    if name in ("Glob", "Grep"):
        return inp.get("pattern", "")[:80]
    if name in ("Agent", "Task"):
        return inp.get("subagent_type", inp.get("description", ""))[:80]
    if name == "WebFetch":
        return inp.get("url", "")[:80]
    if name == "WebSearch":
        return inp.get("query", "")[:80]
    # generic fallback: first key=value
    for k, v in inp.items():
        return f"{k}={str(v)[:60]}"
    return ""


def scan_projects_dir(projects_dir: Path | None = None) -> list[Session]:
    """Enumerate all .jsonl session files under ~/.claude/projects/."""
    root = projects_dir or _PROJECTS_DIR
    sessions: list[Session] = []
    if not root.is_dir():
        return sessions
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        project_path = unquote(project_dir.name)
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            try:
                size = jsonl_file.stat().st_size
            except OSError:
                size = 0
            sessions.append(
                Session(
                    session_id=jsonl_file.stem,
                    project_path=project_path,
                    log_path=jsonl_file,
                    file_size_bytes=size,
                )
            )
    return sessions


def read_session(session: Session) -> list[LogEntry]:
    """Parse a session JSONL file into LogEntry list; skips malformed lines."""
    entries: list[LogEntry] = []
    try:
        text = session.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        entries.append(_parse_entry(raw))
    return entries


def _parse_entry(raw: dict) -> LogEntry:
    # Real Claude Code transcripts wrap message data under a "message" key.
    # Fall back to top-level keys to stay compatible with test fixtures.
    msg = raw.get("message") if isinstance(raw.get("message"), dict) else {}

    entry_type = str(raw.get("type", ""))
    ts = _parse_ts(raw.get("timestamp"))
    role = msg.get("role") or raw.get("role")
    model = msg.get("model") or raw.get("model")
    request_id = raw.get("requestId")

    # Session-level metadata on every entry
    git_branch = raw.get("gitBranch") or None
    cwd = raw.get("cwd") or None
    claude_version = raw.get("version") or None

    usage_raw = msg.get("usage") or raw.get("usage")
    usage = (
        TokenUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0)),
            output_tokens=int(usage_raw.get("output_tokens", 0)),
            cache_read_input_tokens=int(usage_raw.get("cache_read_input_tokens", 0)),
            cache_creation_input_tokens=int(usage_raw.get("cache_creation_input_tokens", 0)),
        )
        if isinstance(usage_raw, dict)
        else None
    )

    # content: real format has it in message.content; fixture format at top level
    content = msg.get("content") if msg else None
    if content is None:
        content = raw.get("content")

    # Extract first tool_use block from content array (real format)
    # Also accept legacy flat-format name/input fields
    tool_name: str | None = raw.get("name")
    tool_input: dict | None = raw.get("input") if isinstance(raw.get("input"), dict) else None
    tool_error_count = 0
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_name = tool_name or block.get("name")
                if tool_input is None and isinstance(block.get("input"), dict):
                    tool_input = block["input"]
            elif block.get("type") == "tool_result" and block.get("is_error"):
                tool_error_count += 1

    # Flatten content list to plain text
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts) if parts else None

    # custom-title entry
    custom_title: str | None = raw.get("customTitle") or None

    # attachment entry (hook event)
    hook_event: HookEvent | None = None
    att = raw.get("attachment")
    if isinstance(att, dict) and att.get("hookEvent"):
        hook_event = HookEvent(
            hook_name=str(att.get("hookName", "")),
            hook_event_type=str(att.get("hookEvent", "")),
            exit_code=int(att.get("exitCode", 0)),
            duration_ms=int(att.get("durationMs", 0)),
            timestamp=ts,
        )

    return LogEntry(
        type=entry_type,
        timestamp=ts,
        role=role,
        content=content,
        model=model,
        usage=usage,
        tool_name=tool_name,
        tool_input=tool_input,
        is_error=bool(raw.get("is_error", False)),
        request_id=request_id,
        git_branch=git_branch,
        cwd=cwd,
        claude_version=claude_version,
        custom_title=custom_title,
        hook_event=hook_event,
        tool_error_count=tool_error_count,
    )


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def compute_summary(
    session: Session,
    entries: list[LogEntry],
    pricing: list[PricingEntry],
) -> SessionSummary:
    """Aggregate tokens, cost, agents, and skills from parsed log entries."""
    total = TokenUsage()
    model_breakdown: dict[str, TokenUsage] = {}
    agents: list[AgentInvocation] = []
    skills: list[SkillInvocation] = []
    tool_calls: list[ToolInvocation] = []
    hook_events: list[HookEvent] = []
    message_count = 0
    tool_error_total = 0
    timestamps: list[datetime] = []
    title: str | None = None
    git_branch: str | None = None
    cwd: str | None = None
    claude_version: str | None = None

    seen_request_ids: set[str] = set()

    for idx, entry in enumerate(entries):
        if entry.timestamp:
            timestamps.append(entry.timestamp)

        # Deduplicate by requestId: real transcripts repeat the same usage block
        # across multiple entries that share a request (one per content block).
        if entry.type == "assistant" and entry.usage:
            if not entry.request_id or entry.request_id not in seen_request_ids:
                total = total + entry.usage
                model_key = entry.model or "unknown"
                existing = model_breakdown.get(model_key, TokenUsage())
                model_breakdown[model_key] = existing + entry.usage
                if entry.request_id:
                    seen_request_ids.add(entry.request_id)

        if entry.type in ("user", "assistant"):
            message_count += 1

        if entry.type == "user" and isinstance(entry.content, str):
            stripped = entry.content.strip()
            if stripped.startswith("/"):
                parts = stripped.split(None, 1)
                skill_name = parts[0].lstrip("/")
                args = parts[1] if len(parts) > 1 else ""
                skills.append(
                    SkillInvocation(
                        skill_name=skill_name,
                        args=args,
                        timestamp=entry.timestamp,
                    )
                )

        # Collect session-level metadata from first entry that has each field
        if not title and entry.custom_title:
            title = entry.custom_title
        if not git_branch and entry.git_branch:
            git_branch = entry.git_branch
        if not cwd and entry.cwd:
            cwd = entry.cwd
        if not claude_version and entry.claude_version:
            claude_version = entry.claude_version

        # Hook events
        if entry.hook_event:
            hook_events.append(entry.hook_event)

        # Tool errors from tool_result blocks
        tool_error_total += entry.tool_error_count

        # Collect all tool invocations; agent dispatches also go into agents list.
        if entry.tool_name:
            inp = entry.tool_input or {}
            tool_calls.append(
                ToolInvocation(
                    tool_name=entry.tool_name,
                    input_preview=_tool_preview(entry.tool_name, inp),
                    timestamp=entry.timestamp,
                    caller_type="direct",
                    is_error=bool(entry.is_error),
                )
            )
            if entry.tool_name in _AGENT_TOOL_NAMES:
                agents.append(
                    AgentInvocation(
                        agent_type=str(inp.get("subagent_type", inp.get("description", "unknown"))),
                        description=str(inp.get("description", "")),
                        prompt_preview=str(inp.get("prompt", ""))[:200],
                        timestamp=entry.timestamp,
                        isolation=inp.get("isolation"),
                        triggered_by=infer_trigger(idx, entries),
                        model=entry.model,
                    )
                )

    # Assign agents_dispatched to each skill
    for skill in skills:
        if skill.timestamp:
            skill.agents_dispatched = [
                a.agent_type
                for a in agents
                if a.timestamp and a.timestamp >= skill.timestamp
            ]

    cost = _compute_cost(model_breakdown, pricing)
    start_time = min(timestamps) if timestamps else None
    end_time = max(timestamps) if timestamps else None
    duration = (end_time - start_time).total_seconds() if start_time and end_time else 0.0

    files_written = sum(
        1 for t in tool_calls if t.tool_name in ("Write", "Edit", "NotebookEdit")
    )
    return SessionSummary(
        session_id=session.session_id,
        project_path=session.project_path,
        start_time=start_time,
        duration_seconds=duration,
        total_input_tokens=total.input_tokens,
        total_output_tokens=total.output_tokens,
        total_cache_read_tokens=total.cache_read_input_tokens,
        total_cache_write_tokens=total.cache_creation_input_tokens,
        estimated_cost_usd=cost,
        model_breakdown=model_breakdown,
        agent_count=len(agents),
        agents=agents,
        skills=skills,
        tool_calls=tool_calls,
        hook_events=hook_events,
        message_count=message_count,
        tool_error_count=tool_error_total,
        files_written=files_written,
        title=title,
        git_branch=git_branch,
        cwd=cwd,
        claude_version=claude_version,
    )


def _compute_cost(breakdown: dict[str, TokenUsage], pricing: list[PricingEntry]) -> float:
    total_cost = 0.0
    for model, usage in breakdown.items():
        entry = lookup(model, pricing)
        total_cost += (
            usage.input_tokens * entry.input_usd_per_mtok / 1_000_000
            + usage.output_tokens * entry.output_usd_per_mtok / 1_000_000
            + usage.cache_read_input_tokens * entry.cache_read_usd_per_mtok / 1_000_000
            + usage.cache_creation_input_tokens * entry.cache_write_usd_per_mtok / 1_000_000
        )
    return total_cost


def infer_trigger(entry_index: int, entries: list[LogEntry]) -> str:
    """Walk backwards from entry_index to find the nearest skill or user message."""
    for i in range(entry_index - 1, -1, -1):
        e = entries[i]
        if e.type == "user" and isinstance(e.content, str):
            text = e.content.strip()
            if text.startswith("/"):
                return text.split(None, 1)[0].lstrip("/")
            return text[:60] if text else "user message"
    return "direct"


def infer_session_tree(summaries: list[SessionSummary]) -> None:
    """Assign parent_session_id / child_session_ids using time-containment heuristics.

    Claude Code stores subagent sessions as separate JSONL files with no explicit
    parentSessionId link.  The only available signal is time: if session B started
    and ended while session A was running in the same project, B was likely spawned
    by A.  The tightest (shortest) container is chosen as the parent so that nested
    subagent chains resolve correctly.
    """
    by_project: dict[str, list[SessionSummary]] = {}
    for s in summaries:
        by_project.setdefault(s.project_path, []).append(s)

    for group in by_project.values():
        for child in group:
            if not child.start_time or child.duration_seconds <= 0:
                continue
            child_end = child.start_time + timedelta(seconds=child.duration_seconds)
            best: SessionSummary | None = None
            for candidate in group:
                if candidate.session_id == child.session_id:
                    continue
                if not candidate.start_time or candidate.duration_seconds <= 0:
                    continue
                cand_end = candidate.start_time + timedelta(seconds=candidate.duration_seconds)
                # Candidate must contain the child's time range (with 5-min grace for
                # subagents that finish slightly after the parent's last recorded entry).
                if (
                    candidate.start_time <= child.start_time
                    and child_end <= cand_end + timedelta(minutes=5)
                    and candidate.duration_seconds > child.duration_seconds
                ):
                    if best is None or candidate.duration_seconds < best.duration_seconds:
                        best = candidate
            if best is not None and child.parent_session_id is None:
                child.parent_session_id = best.session_id
                if child.session_id not in best.child_session_ids:
                    best.child_session_ids.append(child.session_id)


def delete_session(session: Session) -> None:
    """Remove the session's JSONL file from disk."""
    try:
        session.log_path.unlink()
    except FileNotFoundError:
        pass


def read_write_audit(
    audit_path: Path | None = None,
    since: datetime | None = None,
) -> list[TriggerEvent]:
    """Parse ~/.claude/write_audit.jsonl into TriggerEvent list."""
    path = audit_path or _WRITE_AUDIT_PATH
    events: list[TriggerEvent] = []
    if not path.exists():
        return events
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(raw.get("ts"))
        if ts is None:
            continue
        if since and ts < since:
            continue
        events.append(
            TriggerEvent(
                timestamp=ts,
                tool=str(raw.get("tool", "")),
                path=str(raw.get("path", "")),
            )
        )
    return events
