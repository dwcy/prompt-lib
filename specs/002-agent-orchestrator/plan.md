# Implementation Plan: Agent Orchestrator — GitHub PR Review (v1)

**Branch**: `dawid/advanced-orchestrations` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-agent-orchestrator/spec.md`

## Summary

Build a v1 agent-orchestration daemon at `services/orchestrator/` that polls GitHub for new pull requests on a configured repo, dispatches each PR to a peer Claude Code agent over the existing A2A bridge, posts the agent's review back to the PR via `gh`, persists every state transition to an append-only SQLite event log, pushes notifications to the operator's phone via ntfy.sh, and exposes a separate Textual dashboard process that tails the event log in real time. v1 ships ONE vertical slice (PR-review only); PR-fix, Issue→PR, LangGraph multi-agent flows, and webhook triggers are explicitly v2+. The service is a sibling of `services/a2a-bridge/`, sharing the same Python 3.13 + Typer + httpx + uv toolchain.

## Technical Context

**Language/Version**: Python 3.13 (matches `services/a2a-bridge/`)
**Primary Dependencies**: Typer (CLI), httpx (ntfy publishing + reuse of `a2a_bridge.client.delegation.DelegationClient`), Pydantic v2 + pydantic-settings (config), Textual (dashboard), Rich (banner styling), `gh` (external CLI dependency, not pip), the existing `a2a-bridge` package as a sibling import. FastAPI is NOT pulled in for v1 (no inbound HTTP); webhook trigger in v2 will add it.
**Storage**: SQLite via stdlib `sqlite3` at `~/.claude/orchestrator/events.db` (append-only `events` table, single `cursor` table for poll bookmark, single `schema_version` table). No ORM. WAL mode.
**Testing**: pytest + pytest-asyncio + pytest-httpx (for ntfy and gh-CLI shims) + a fake `gh` script fixture for poll integration tests. One real-end-to-end integration test per P1/P2/P3 acceptance scenario using a throwaway test repo behind a `INTEGRATION=1` env-gate.
**Target Platform**: Operator workstation — Windows 10/11 (primary), Linux/macOS (supported). Localhost only.
**Project Type**: CLI service (daemon + TUI dashboard) — not a library, not a web service in v1.
**Performance Goals**: poll-to-notification ≤ 35 s (SC-001); review posted ≤ 90 s for diffs <500 lines (SC-002); dashboard refresh ≤ 1 s (SC-003); idle CPU <1%; 24 h uptime without crash (SC-005).
**Constraints**: localhost only (no public ingress); env vars only — no `.env` files written (FR-011, CLAUDE.md); single repo per daemon (FR-001); no new global skill or agent (FR-016, Gate 5).
**Scale/Scope**: 1 operator, 1 repo per daemon instance, 1–10 PRs/day, ~5–30 events per run.

## Constitution Check

Per `.specify/memory/constitution.md` v1.0.0, the following gates apply:

- **Gate 1 — Spec-First Conformance**: PASS. The orchestrator is a CONSUMER of three external surfaces (none of which it implements as a server in v1): (a) `gh` CLI's documented `--json` output schema for `gh pr list` and `gh pr view` (canonical reference: <https://cli.github.com/manual/>), (b) ntfy.sh's HTTP publish API (canonical reference: <https://docs.ntfy.sh/publish/>), and (c) the A2A v1.0.0 wire (consumed indirectly via `a2a_bridge.client.delegation.DelegationClient` — wire conformance is owned by `001-a2a-bridge`). Conformance scope is documented per surface in [`contracts/README.md`](./contracts/README.md). No new wire spec is invented.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table in the next section maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: PASS. [`contracts/`](./contracts/) enumerates the external surfaces the orchestrator parses or produces (`gh-pr-list.contract.md`, `ntfy-publish.contract.md`, `a2a-delegation.contract.md`). `/speckit-tasks` will produce a `tasks.md` that orders contract test tasks (`tests/contract/`) before their implementation tasks per the rule in `.specify/templates/tasks-template.md`. Internal Python interfaces (the `Trigger` Protocol, the eventlog read API) are NOT protocol surfaces under Gate 3 — they are covered by ordinary unit tests at the author's discretion.
- **Gate 4 — Reversible Config Changes**: N/A. v1 lives entirely under `services/orchestrator/` and does NOT touch `global/`. Per FR-016, no global skill, agent, hook, or settings change is required.
- **Gate 5 — Minimal Skill & Agent Surface**: PASS. v1 does NOT add a new global skill or agent. The orchestrator invokes the existing `/git`, `/pr`, `/review` skills and the `@code-plan-verifier` agent INSIDE delegated prompts (i.e., the peer Claude Code agent uses them — the orchestrator itself does not redefine them). `/review-conflicts` confirms no near-duplicate exists. If v3 (Issue → Plan → PR) eventually demands a dedicated `/orchestrate` slash command, that will be revisited in `specs/003-…/plan.md`.

No gate violations. Complexity Tracking table at bottom is empty.

## Subagent Delegation

Per `.specify/memory/agents.md`, the table below assigns each phase of work to a named subagent. `/speckit-implement` MUST dispatch each task accordingly via the `Agent` tool.

| Phase / concern | Owner | Why |
|---|---|---|
| Project scaffolding (`pyproject.toml`, `uv` lockfile, src/tests layout, ruff config) | `@python-architect` | Python project structure decision; mirror `services/a2a-bridge/` |
| `config.py` (pydantic-settings: env-only, no `.env`) | `@python-architect` | Service-layer config + validation |
| `eventlog.py` (SQLite schema, append + tail-since, transactional cursor, orphan recovery) | `@python-architect` | Storage adapter design, no ORM |
| `notifier.py` (ntfy HTTP publish, level→priority mapping, non-fatal error handling) | `@python-architect` | Async HTTP client design |
| `triggers/base.py` (`Trigger` Protocol, `TriggerEvent` model) | `@python-architect` | Async iterator + typing.Protocol shape |
| `triggers/github_poll.py` (subprocess wrap of `gh pr list --json`, diff vs. cursor) | `@python-architect` | Async + subprocess + JSON parse |
| `agents/pr_review.py` (build prompt, call `DelegationClient`, stream events, post via `gh pr review`) | `@python-architect` | Async streaming + external CLI orchestration |
| `daemon.py` + `cli.py` (Typer wiring trigger → agent → eventlog + notifier; signal handling) | `@python-architect` | Service composition + CLI ergonomics |
| `dashboard/app.py` (Textual app, banner header, runs DataTable, event Log, 500ms timer) | `@python-architect` | TUI is still Python service code; no separate frontend stack |
| Contract tests (`tests/contract/test_gh_pr_list_schema.py`, `test_ntfy_publish_request.py`, `test_a2a_delegation_consumer.py`) | `@python-tester` | Wire-format conformance suite per Gate 3 |
| Unit tests (`tests/unit/`) | `@python-tester` | pytest + httpx mocks + fake `gh` shim |
| Integration tests (`tests/integration/test_p1_pr_review.py`, `test_p2_dashboard_tail.py`, `test_p3_phone_notification.py`, `test_p4_replayable_history.py`) | `@python-tester` | Real subprocess + real test repo |
| `quickstart.md` validation pass on a live throwaway repo | `main` | One-time exercise of the integrated system end-to-end |
| ADRs for any external-surface deviations (none expected in v1) | `main` | Cross-cutting governance |
| Plan-conformance audit before commit | `@code-plan-verifier` | Constitution gate before pushing |

CSS / frontend / .NET / Unity / React are N/A for this feature — no `.css`, no `.tsx`, no `.csproj`, no Unity asset is touched. The Textual TUI uses inline Python CSS-strings inside `.py` files; per `.specify/memory/agents.md`, that is part of the Python service code and stays with `@python-architect`.

## Project Structure

### Documentation (this feature)

```
specs/002-agent-orchestrator/
├── plan.md              # This file
├── research.md          # Phase 0 output — tech choices with rationale (R1..R10)
├── data-model.md        # Phase 1 output — TriggerEvent, Run, Event, Notification, Cursor
├── quickstart.md        # Phase 1 output — operator setup walkthrough
├── contracts/           # Phase 1 output — external protocol surfaces
│   ├── README.md
│   ├── gh-pr-list.contract.md
│   ├── ntfy-publish.contract.md
│   └── a2a-delegation.contract.md
├── checklists/
│   └── requirements.md  # Already created by /speckit-specify
└── tasks.md             # Phase 2 output (NOT created by /speckit-plan — generated by /speckit-tasks)
```

### Source Code (repository root)

```
services/
└── orchestrator/
    ├── pyproject.toml                 # uv-managed; pins typer, httpx, pydantic, pydantic-settings, textual, rich; dev: pytest, pytest-asyncio, pytest-httpx, ruff
    ├── uv.lock
    ├── README.md                      # Points at specs/002-agent-orchestrator/quickstart.md
    ├── src/
    │   └── orchestrator/
    │       ├── __init__.py
    │       ├── cli.py                 # `orchestrator serve` and `orchestrator dash` Typer entry points
    │       ├── config.py              # pydantic-settings; env-only; validates A2A_PEER_URL, ntfy topic, repo, db path, poll interval, A2A bearer
    │       ├── daemon.py              # asyncio loop wiring Trigger → Agent → eventlog + notifier; SIGINT/SIGTERM clean shutdown
    │       ├── eventlog.py            # SQLite open + schema migration; append_event(); tail_since(id); cursor read/write; orphan-marking
    │       ├── notifier.py            # async httpx POST to ntfy; level → priority + tags; non-fatal failure semantics
    │       ├── triggers/
    │       │   ├── __init__.py
    │       │   ├── base.py            # `Trigger` Protocol + `TriggerEvent` Pydantic model
    │       │   └── github_poll.py     # async loop wrapping `gh pr list --json`; diff vs SQLite cursor table
    │       ├── agents/
    │       │   ├── __init__.py
    │       │   └── pr_review.py       # builds prompt with `gh pr diff <n>`; delegates via DelegationClient; posts via `gh pr review`
    │       └── dashboard/
    │           ├── __init__.py
    │           └── app.py             # Textual App: banner (mirror setup/apply.py:87-104), DataTable (mirror :785-825), Log widget, 500ms set_interval
    └── tests/
        ├── conftest.py                # Fake `gh` shim, fake ntfy server (httpx.MockTransport), fixture SQLite db, FakeDelegationClient
        ├── contract/                  # Constitution Principle III — external wire-format conformance
        │   ├── test_gh_pr_list_schema.py
        │   ├── test_ntfy_publish_request.py
        │   └── test_a2a_delegation_consumer.py
        ├── integration/               # Real subprocess + real test repo when INTEGRATION=1
        │   ├── test_p1_pr_review_end_to_end.py
        │   ├── test_p2_dashboard_tail.py
        │   ├── test_p3_phone_notification.py
        │   └── test_p4_replayable_history.py
        └── unit/
            ├── test_config.py
            ├── test_eventlog.py
            ├── test_notifier.py
            ├── test_trigger_base.py
            └── test_github_poll.py
```

**Structure Decision**: Sibling of `services/a2a-bridge/` under the same `services/` directory, sharing the Python 3.13 + uv + Typer + httpx + Pydantic toolchain. The orchestrator imports `a2a_bridge.client.delegation.DelegationClient` directly via a path dependency (single repo, sibling package). Tests are split into `contract/` (Gate 3 — external surfaces only), `integration/` (real subprocess gated by `INTEGRATION=1`), and `unit/` (everything else). The dashboard is a separate Typer subcommand running an in-process Textual `App` — it does not require its own package.

## Complexity Tracking

> No Constitution Check violations. Table empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | (none) | (none) |

## Future-work scaffold (worktree manager, dormant in v1)

The v1 source tree contains a `WorktreeManager` (`src/orchestrator/worktree.py`), a `worktrees` SQLite table, four `ORCHESTRATOR_WORKTREE_*` config fields, and a `worktree_manager` kwarg on `PrReviewAgent` — all dormant in v1. They are gated behind `ORCHESTRATOR_WORKTREE_ENABLED` (default `false`); with the flag unset the daemon never constructs the manager, never runs the prune loop, and `pr_review.py` passes `cwd=None` to the delegation client (preserving the A2A v1.0.0 wire shape). This is forward-scaffolding for the next feature, **`specs/003-worktree-manager/`** (PR-fix agent), which will own the spec, contract, deployment, and integration tests for that subsystem. The matching A2A `cwd` extension is recorded in [`../001-a2a-bridge/contracts/adr-cwd-extension.md`](../001-a2a-bridge/contracts/adr-cwd-extension.md).
