# Implementation Plan: A2A Bridge for Multi-Agent CLI Delegation (v1)

**Branch**: `001-a2a-bridge` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-a2a-bridge/spec.md`

## Summary

Build a v1 multi-agent A2A bridge so Claude Code can delegate tasks to a peer Gemini CLI over the official A2A v1.0.0 JSON-RPC binding, and so external clients (curl, future peers) can drive Claude Code through the same protocol. v1 ships two adapters (Claude inbound, Gemini outbound target) sharing one Python package at `services/a2a-bridge/`, built on Python 3.13 + FastAPI + httpx + uv. Codex CLI support, full mesh, and any non-localhost deployment are explicitly v2+.

## Technical Context

**Language/Version**: Python 3.13 (latest stable as of 2026-05)
**Primary Dependencies**: FastAPI ≥0.135 (native `EventSourceResponse`), httpx (async streaming client), Pydantic v2, uvicorn (ASGI server), `a2a-sdk` (the official A2A Python SDK from a2aproject; only as a test/contract dependency — confirmed installed FastAPI 0.136.1 has `fastapi.sse.EventSourceResponse`, R2 verified)
**Storage**: None (FR-010 — in-memory task state only)
**Testing**: pytest + pytest-asyncio + httpx ASGITransport for in-process contract tests; one real-subprocess end-to-end test per user story; the `a2a-sdk` package (official A2A Python SDK) drives wire-format conformance tests
**Target Platform**: Developer laptop (macOS, Linux, Windows) — localhost only in v1
**Project Type**: Local service (one Python package, two adapter entry points, one delegation CLI)
**Performance Goals**: p95 inbound task acceptance < 100ms before CLI spawn; sustain ≥3 concurrent inbound tasks without contention; ≤30s end-to-end Claude→Gemini delegation for prompts <1000 tokens (matches SC-001); adapter cold start < 2s
**Constraints**: localhost-only (FR-009); bearer-token auth only (FR-005); no persistence between restarts (FR-010); zero spec deviations except via ADR (FR-012, Constitution Principle I)
**Scale/Scope**: 1 developer per machine, ≤10 concurrent in-flight tasks per adapter, 2 adapters per machine in v1

## Constitution Check

Per `.specify/memory/constitution.md` v1.0.0, the following gates apply:

- **Gate 1 — Spec-First Conformance**: PASS. Canonical A2A spec linked in `research.md` R1: <https://a2a-protocol.org/latest/specification/>, version v1.0.0 (released 2026-03-12). Conformance scope: JSON-RPC 2.0 binding + Agent Card discovery only. gRPC and HTTP+JSON/REST are out of scope and documented in `contracts/README.md`.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table in the next section maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: PASS. `contracts/` enumerates every protocol surface (Agent Card, JSON-RPC methods, SSE events, error codes). `/speckit-tasks` will produce a `tasks.md` that orders contract test tasks (`tests/contract/`) before their implementation tasks per the rule in `.specify/templates/tasks-template.md`.
- **Gate 4 — Reversible Config Changes**: N/A. v1 services live entirely under `services/a2a-bridge/` and do NOT touch `global/`. No global Claude config is mutated by this feature.
- **Gate 5 — Minimal Skill & Agent Surface**: PASS with explicit decision recorded. v1 does NOT add a new global skill or subagent. Per `research.md` R6, the developer-facing trigger for delegation is a CLI subcommand (`a2a-bridge delegate ...`) rather than a `/delegate` slash command. Justification: an existing surface (the `Bash` tool) already lets Claude Code invoke local CLIs; adding a global skill before we have usage data would be premature. v2 may revisit if usage justifies a dedicated trigger.

No gate violations. Complexity Tracking table at bottom is empty.

## Subagent Delegation

Per `.specify/memory/agents.md`, the table below assigns each phase of work to a named subagent. `/speckit-implement` MUST dispatch each task accordingly via the `Agent` tool.

| Phase / concern | Owner | Why |
|---|---|---|
| Project scaffolding (`pyproject.toml`, `uv` lockfile, package layout) | `@python-architect` | Python project structure decision |
| A2A protocol module (request/response models, validators, Agent Card builder) | `@python-architect` | Service-layer design with strict Pydantic validation |
| Adapter HTTP server (FastAPI app, JSON-RPC endpoint, SSE streaming) | `@python-architect` | FastAPI / async architecture |
| CLI runner abstraction (`asyncio.create_subprocess_exec`, timeout, JSON-stream parsing per CLI) | `@python-architect` | async subprocess management |
| Claude adapter wiring | `@python-architect` | Composes the protocol + runner modules |
| Gemini adapter wiring | `@python-architect` | Same shape as Claude adapter, different CLI invocation |
| DelegationClient (httpx async + SSE consumer) | `@python-architect` | Async HTTP client design |
| `a2a-bridge` CLI (Typer / argparse for `serve` and `delegate` subcommands) | `@python-architect` | CLI ergonomics fall under structural decisions |
| Contract tests (Agent Card schema, JSON-RPC envelope, SSE event ordering, error codes) | `@python-tester` | Pytest contract suite using `a2a-python` SDK |
| End-to-end tests (one per P1/P2 acceptance scenario; spawns real subprocess) | `@python-tester` | Real subprocess integration test pattern |
| Concurrency tests (≥3 parallel inbound tasks, no cross-contamination) | `@python-tester` | Async pytest fixtures + httpx ASGITransport |
| ADRs (any spec deviation, the CLI-trigger choice from R6) | `main` | Cross-cutting governance, lives in `.specify/specs/001-a2a-bridge/contracts/` (feature-scoped) or `docs/adr/` (cross-cutting) |
| `quickstart.md` validation pass | `main` | Exercises the integrated system end-to-end |
| Inspector manual conformance pass for SC-002 | `main` | One-time manual validation per release |

## Project Structure

### Documentation (this feature)

```
specs/001-a2a-bridge/
├── plan.md              # This file
├── research.md          # Phase 0 output — A2A spec, FastAPI SSE, CLI flags, test tooling
├── data-model.md        # Phase 1 output — Task, Artifact, Adapter, etc.
├── quickstart.md        # Phase 1 output — 9-step end-to-end verification
├── contracts/           # Phase 1 output — protocol surfaces
│   ├── README.md
│   ├── agent-card.schema.json
│   ├── jsonrpc-methods.md
│   ├── sse-events.md
│   └── error-codes.md
└── tasks.md             # Phase 2 output (NOT created by /speckit-plan — generated by /speckit-tasks)
```

### Source Code (repository root)

```
services/
└── a2a-bridge/
    ├── pyproject.toml                 # uv-managed; pins fastapi>=0.135, httpx, pydantic, a2a (test only)
    ├── uv.lock
    ├── README.md                      # Points at specs/001-a2a-bridge/quickstart.md
    ├── src/
    │   └── a2a_bridge/
    │       ├── __init__.py
    │       ├── protocol/              # A2A wire format — pure functions, no I/O
    │       │   ├── __init__.py
    │       │   ├── agent_card.py      # AgentCard model + builder; loads agent-card.schema.json
    │       │   ├── jsonrpc.py         # Request/response envelopes, error codes, parser
    │       │   ├── tasks.py           # Task entity + state machine + transitions
    │       │   └── sse.py             # SSE event framing helpers
    │       ├── adapters/              # One subpackage per CLI we wrap
    │       │   ├── __init__.py
    │       │   ├── base.py            # Shared FastAPI app factory + auth middleware
    │       │   ├── claude/
    │       │   │   ├── __init__.py
    │       │   │   ├── runner.py      # asyncio.create_subprocess_exec for `claude -p ... --bare`
    │       │   │   └── server.py      # FastAPI app instance for the Claude adapter
    │       │   └── gemini/
    │       │       ├── __init__.py
    │       │       ├── runner.py      # asyncio.create_subprocess_exec for `gemini -p ...`
    │       │       └── server.py      # FastAPI app instance for the Gemini adapter
    │       ├── client/
    │       │   ├── __init__.py
    │       │   └── delegation.py      # DelegationClient — httpx async + SSE consumer
    │       └── cli.py                 # `a2a-bridge serve <agent>` and `a2a-bridge delegate <peer> <prompt>`
    └── tests/
        ├── conftest.py                # Shared fixtures (bearer token, ASGI transport, fake CLI)
        ├── contract/                  # Constitution Principle III — wire-format conformance
        │   ├── test_agent_card_schema.py
        │   ├── test_jsonrpc_envelope.py
        │   ├── test_jsonrpc_methods_send_subscribe.py
        │   ├── test_jsonrpc_methods_get.py
        │   ├── test_jsonrpc_methods_cancel.py
        │   ├── test_sse_event_ordering.py
        │   └── test_error_codes.py
        ├── integration/               # Real subprocess; one per acceptance scenario
        │   ├── test_p1_outbound_delegation.py
        │   ├── test_p2_inbound_curl.py
        │   ├── test_p3_agent_card_discovery.py
        │   └── test_concurrency.py
        └── unit/                      # Optional per Constitution III; included only where they pay off
            ├── test_task_state_machine.py
            └── test_bearer_token_compare.py
```

**Structure Decision**: Single Python package under `services/a2a-bridge/` with subpackages by concern (`protocol/`, `adapters/`, `client/`). Each adapter is a subpackage so Codex (v2) can be added by creating `adapters/codex/` without touching shared code. Tests are split into `contract/` (the protocol surface — gated by Principle III), `integration/` (real subprocess, one per acceptance scenario), and `unit/` (optional, used sparingly). The package is invoked via the `a2a-bridge` console script defined in `pyproject.toml`.

This structure does NOT touch `global/`, satisfying Constitution Gate 4 by trivially not modifying any deployable Claude config.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(none)_ | _(none)_ |

## Re-evaluation post-design

All five constitution gates remain satisfied after Phase 1 design artifacts (`data-model.md`, `contracts/`, `quickstart.md`) were produced:

- **Gate 1**: `contracts/` files explicitly declare conformance scope per A2A v1.0.0 method and event. Out-of-scope items are listed in `contracts/README.md` so they cannot be silently added.
- **Gate 2**: Delegation table above is concrete; no task is implicitly assigned to `main`.
- **Gate 3**: `tests/contract/` directory plan covers every surface in `contracts/`. `/speckit-tasks` will enforce the ordering rule.
- **Gate 4**: No `global/` touch in the project structure.
- **Gate 5**: No new global skill or agent in v1; CLI subcommand only. R6 records the decision.

## Phase 2 — Tasks

Phase 2 (`tasks.md`) is generated by `/speckit-tasks`, not by this command. The next step is to run `/speckit-tasks` so that:

- Each user story (P1, P2, P3) becomes a phase with contract tests ordered before implementation.
- Every task is tagged `Owner: @python-architect`, `Owner: @python-tester`, or `Owner: main` per the table in this plan.
- Setup and Foundational phases produce the `pyproject.toml`, the auth middleware, and the protocol module before any user-story work begins.
