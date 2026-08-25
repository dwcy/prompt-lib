# -*- coding: utf-8 -*-
"""Agent adapter registry: name -> factory, selected by eval.config.toml's `adapter` value.

Drop-in contract for future adapters (codex, gemini, ...) — implement the `AgentAdapter`
protocol from `cabal.evals.adapters.base` (a `name` attribute plus `check()` / `capabilities()`
/ `run()`; no base class required), then satisfy the four duties below. Nothing in the runner
core (matrix, metrics, judge, report) may need to change for a new adapter.

Registration: call `register(name, factory)` at import time at the bottom of your module, then
import that module at the bottom of this file for the side effect — that single line is what
makes the name resolvable from eval.config.toml's `adapter` key and `run --adapter`; unknown
names fail at validate time and in cli_run before any cell executes.

Capabilities honesty: `capabilities()` must declare only what your CLI genuinely reports —
declare False for any field (tokens, tool_calls, cost) it cannot supply so metrics.py records
null, never a fabricated zero; a capability declared True but never populated corrupts every
aggregate mean downstream.

Transcript passthrough: `run()` streams the CLI's raw event output verbatim to
`spec.transcript_path` (one JSON line per event where the CLI offers it) without reshaping —
metrics.py owns all interpretation, and fields it cannot find in your transcript surface as
null through the capability gate rather than as adapter-side guesses.

Timeout kill duty: `run()` enforces `spec.timeout_seconds` itself and must kill the entire
process tree on expiry (`cabal.evals.proc.kill_process_tree`), returning a failed
AgentRunResult with reason `agent_timeout` — a leaked child process outlives the disposable
worktree and poisons subsequent cells.
"""

from __future__ import annotations

from collections.abc import Callable

from cabal.evals.adapters.base import AgentAdapter


class UnknownAdapterError(ValueError):
    """No adapter is registered under the requested name."""


_REGISTRY: dict[str, Callable[[], AgentAdapter]] = {}


def register(name: str, factory: Callable[[], AgentAdapter]) -> None:
    """Register an adapter factory under its eval.config.toml `adapter` name."""
    _REGISTRY[name] = factory


def registered_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def get_adapter(name: str) -> AgentAdapter:
    """Instantiate the adapter registered under `name`; unknown names are a validate-time error."""
    factory = _REGISTRY.get(name)
    if factory is None:
        known = ", ".join(registered_names()) or "(none registered)"
        raise UnknownAdapterError(f"unknown adapter {name!r}; registered adapters: {known}")
    return factory()


# Imported for its register() side effect — this is what puts "claude-code" in the registry.
from cabal.evals.adapters import claude_code as _claude_code  # noqa: E402,F401
