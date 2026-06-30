# -*- coding: utf-8 -*-
"""Pure dataclasses for Claude session data — no I/O, no Textual, no tokens."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Session:
    session_id: str
    project_path: str
    log_path: Path
    file_size_bytes: int = 0


@dataclass
class LogEntry:
    type: str
    timestamp: datetime | None = None
    role: str | None = None
    content: str | list | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    is_error: bool = False
    request_id: str | None = None
    # Session-level metadata carried on most entries
    git_branch: str | None = None
    cwd: str | None = None
    claude_version: str | None = None
    # Custom-title entry
    custom_title: str | None = None
    # Hook event (attachment entries)
    hook_event: HookEvent | None = None
    # Count of is_error tool_result blocks inside this entry
    tool_error_count: int = 0


@dataclass
class ToolInvocation:
    tool_name: str
    input_preview: str
    timestamp: datetime | None = None
    caller_type: str = "direct"
    is_error: bool = False


@dataclass
class HookEvent:
    hook_name: str
    hook_event_type: str
    exit_code: int
    duration_ms: int
    timestamp: datetime | None = None


@dataclass
class AgentInvocation:
    agent_type: str
    description: str
    prompt_preview: str
    timestamp: datetime | None = None
    isolation: str | None = None
    triggered_by: str = "direct"
    model: str | None = None


@dataclass
class SkillInvocation:
    skill_name: str
    args: str
    timestamp: datetime | None = None
    agents_dispatched: list[str] = field(default_factory=list)


@dataclass
class TriggerEvent:
    timestamp: datetime
    tool: str
    path: str
    session_id: str | None = None


@dataclass
class SessionSummary:
    session_id: str
    project_path: str
    start_time: datetime | None
    duration_seconds: float
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_write_tokens: int
    estimated_cost_usd: float
    model_breakdown: dict[str, TokenUsage] = field(default_factory=dict)
    agent_count: int = 0
    agents: list[AgentInvocation] = field(default_factory=list)
    skills: list[SkillInvocation] = field(default_factory=list)
    tool_calls: list[ToolInvocation] = field(default_factory=list)
    hook_events: list[HookEvent] = field(default_factory=list)
    message_count: int = 0
    tool_error_count: int = 0
    files_written: int = 0
    title: str | None = None
    git_branch: str | None = None
    cwd: str | None = None
    claude_version: str | None = None
    # Inferred tree links (populated by infer_session_tree after all summaries are built)
    parent_session_id: str | None = None
    child_session_ids: list[str] = field(default_factory=list)
