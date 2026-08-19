# -*- coding: utf-8 -*-
"""The agent-CLI adapter seam per `specs/019-agent-eval-harness/contracts/agent-adapter.md`.

The runner core depends only on this protocol, never on a concrete CLI, so Codex/Gemini adapters
drop in without touching matrix/checks/metrics/judge/report. Metric fields an adapter's CLI cannot
produce are declared via `AdapterCapabilities` so metrics records `null`, never fabricated zeros.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

RunStatus = Literal["completed", "failed"]
FAILURE_AGENT_TIMEOUT = "agent_timeout"
FAILURE_AGENT_CRASH = "agent_crash"


class AdapterUnavailableError(RuntimeError):
    """The agent CLI itself is absent or unusable — distinct from a run-level failure."""


@dataclass(frozen=True)
class AgentRunSpec:
    """Everything one headless agent run needs; constructed by the matrix engine by field name."""

    prompt: str
    worktree: Path
    config_dir: Path | None
    settings_file: Path | None
    env: Mapping[str, str]
    model: str | None
    timeout_seconds: int
    skip_permissions: bool
    transcript_path: Path


@dataclass(frozen=True)
class AgentRunResult:
    """Outcome of one run. Run-level failures are encoded here, never raised."""

    status: RunStatus
    failure_reason: str | None
    final_text: str
    exit_code: int | None
    wall_seconds: float


@dataclass(frozen=True)
class AdapterCapabilities:
    """Which metric fields this adapter's CLI can supply; False means metrics stores null."""

    tokens: bool
    tool_calls: bool
    cost: bool


@dataclass(frozen=True)
class AdapterStatus:
    """Outcome of a reachability probe (`check()`), for validate-time adapter diagnostics."""

    adapter: str
    available: bool
    detail: str = ""


@runtime_checkable
class AgentAdapter(Protocol):
    """Implemented by every agent CLI adapter. `name` is the registry key used in eval.config.toml."""

    name: str

    def check(self) -> AdapterStatus:
        """Probe that the CLI exists and runs (e.g. --version). Never raises."""
        ...

    def capabilities(self) -> AdapterCapabilities:
        """Which metric fields this adapter can supply."""
        ...

    def run(self, spec: AgentRunSpec) -> AgentRunResult:
        """Execute one headless agent run. Run-level failures are encoded in the result;
        raises `AdapterUnavailableError` only when the CLI itself is absent."""
        ...
