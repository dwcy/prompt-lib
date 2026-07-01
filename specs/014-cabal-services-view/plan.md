# Implementation Plan: Local Agent Services in the Cabal UI

**Branch**: `014-cabal-services-view` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-cabal-services-view/spec.md`

## Summary

Surface the three local agent services — **orchestrator**, **a2a-bridge**, **mcp-bus** — as first-class entries in the cabal TUI so a maintainer can see and run them from the wizard instead of remembering CLI commands. Add a dedicated **Local Agent Services** screen (off Home) backed by a new service registry, a session-scoped process supervisor (start / stop / live status, net-new for cabal), per-service prerequisite checks that surface actionable messages, and small `uv tool` installers. mcp-bus is presented for visibility only (a client-launched stdio MCP server), not given start/stop. No external protocol is involved; all work is Python/Textual inside `setup/src/cabal/`.

## Technical Context

**Language/Version**: Python 3.11+ (cabal targets the repo's existing interpreter)
**Primary Dependencies**: Textual (TUI), `subprocess` (process supervision), `uv` (tool install), stdlib `socket` (port liveness). The services themselves: Typer + uvicorn (a2a-bridge), Typer + Textual (orchestrator), `mcp` (mcp-bus) — unchanged by this feature.
**Storage**: None new. In-memory `dict[str, ServiceState]` for the cabal session; no DB, no PID file.
**Testing**: pytest, including Textual `App.run_test()` + `Pilot` smoke tests.
**Target Platform**: Windows primary (maintainer profile), cross-platform via the same patterns other managed tools use; no POSIX-only signals.
**Project Type**: Single project — a Textual desktop/CLI wizard (`setup/src/cabal/`).
**Performance Goals**: UI stays responsive; start/stop and status refresh complete well under a second of perceived latency (process I/O runs in workers, not the event loop).
**Constraints**: No regression to existing Tools/MCP screens (FR-012); UI files never call `subprocess` directly (python.md); session-scoped lifecycle only (no auto-restart supervisor).
**Scale/Scope**: 3 services, 1 new screen, ~6 new modules + home wiring, 4 test modules.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: **N/A — no external protocol.** This feature surfaces and supervises *existing* local services from the TUI. It defines no new wire protocol and does not modify any service's protocol behavior. (mcp-bus's MCP surface already shipped under 007/012.)
- **Gate 2 — Subagent Delegation**: **PASS** — delegation table below maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: **N/A — no protocol surface.** The only "contracts" are in-process Python module signatures (`contracts/internal-interfaces.md`); they are covered by ordinary unit/integration tests (owned by `@python-tester`), not wire contract tests.
- **Gate 4 — Reversible Config Changes**: **N/A — does not touch `global/`.** All code lives under `setup/src/cabal/` (the wizard), which does not deploy to `~/.claude/`. No `global/` skills/agents/hooks/settings change. Rollback = revert the branch; no `~/.claude/` migration.
- **Gate 5 — Minimal Skill & Agent Surface**: **N/A — no new Claude skill/agent.** This adds a cabal **screen**, not a `/skill` or `@agent`. No overlap with the harness surface.
- **Gate 6 — Parallel Isolation**: **N/A.** Implementation dispatches a single writing specialist (`@python-architect`) sequentially per module; no two writing subagents run concurrently. See Parallel Execution Map below.

All gates pass or are justified N/A — no Complexity Tracking entries required.

## Subagent Delegation

*GATE: References `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Service registry (`service_catalog.py`) | `@python-architect` | Python data-model / module-boundary decision |
| Process supervisor (`service_supervisor.py`) | `@python-architect` | subprocess lifecycle + state-machine design |
| Prerequisite probes (`service_prereqs.py`) | `@python-architect` | env/port/process probing design |
| Service installers (`installers/orchestrator.py`, `installers/a2a_bridge.py`) | `@python-architect` | mirror existing uv-tool installer pattern |
| Services screen (`views/services.py`) | `@python-architect` | Textual screen structure (no React; `@frontend-css` is web-only and N/A to Textual) |
| Tests (catalog, supervisor, prereqs, screen) | `@python-tester` | pytest + Textual `run_test`/`Pilot` |
| Home wiring, screen registration, CLAUDE.md, ADR/glue | `main` | cross-cutting orchestration |
| Pre-commit implementation audit | `@code-plan-verifier` | read-only plan-compliance gate |

No specialist exists for "Textual UI" specifically; `@python-architect` owns it because cabal is a Python/Textual app and the work is structural Python. `@frontend-css`/`@react-architect` do not apply (no web stack).

### Parallel Execution Map

*GATE 6:* **N/A** — no phase dispatches two or more writing subagents concurrently. All implementation tasks are dispatched sequentially to `@python-architect` (and tests to `@python-tester` after their targets exist). No `Parallel: yes` tasks; no worktree isolation required.

## Project Structure

### Documentation (this feature)

```text
specs/014-cabal-services-view/
├── plan.md              # This file
├── research.md          # Phase 0 — 7 design decisions
├── data-model.md        # Phase 1 — entities, enums, state machine
├── quickstart.md        # Phase 1 — maintainer flow + acceptance mapping
├── contracts/
│   └── internal-interfaces.md   # Phase 1 — in-process module contracts (no wire protocol)
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source Code (repository root)

```text
setup/src/cabal/
├── service_catalog.py          # NEW — ServiceDefinition, SERVICE_DEFINITIONS, ServiceStatus/State, validate
├── service_supervisor.py       # NEW — start/stop/status/reconcile, in-memory PID tracking (subprocess)
├── service_prereqs.py          # NEW — per-service prerequisite probes + is_set_up
├── installers/
│   ├── orchestrator.py         # NEW — uv tool install/upgrade + status (mirrors mcp_bus.py)
│   └── a2a_bridge.py           # NEW — uv tool install/upgrade + status
├── views/
│   ├── services.py             # NEW — ServicesScreen (compose + handlers; delegates all I/O)
│   └── home.py                 # EDIT — add "Local Agent Services" section + button → ServicesScreen

tests/
├── test_service_catalog.py     # NEW
├── test_service_supervisor.py  # NEW — state machine via dummy child process
├── test_service_prereqs.py     # NEW
└── test_services_screen.py     # NEW — Textual run_test smoke
```

**Structure Decision**: Single-project Textual app. New code is split into six focused modules per python.md size discipline (UI separated from subprocess/I/O): registry (data), supervisor (process I/O), prereqs (probing I/O), two installers (uv tool), one screen (UI only). The screen delegates every side-effecting call to the supervisor/prereqs/installers — no `subprocess` in the view. mcp-bus's existing Tools/MCP wiring is left untouched (FR-012). See `research.md` D1/D7.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
