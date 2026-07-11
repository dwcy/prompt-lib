# Implementation Plan: Cabal Web UI Overhaul — Full-Feature Desktop Workspace

**Branch**: `015-web-ui-overhaul` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-web-ui-overhaul/spec.md`

## Summary

Replace the first-generation read-only web UI with a full-parity workspace covering all 22 Cabal feature modules, including confirmation-guarded mutations. Architecture: a shared Python service layer (already largely Textual-free) is exposed through a new FastAPI backend (`cabal/webapi/`) with a two-phase prepare/execute action-safety protocol, SSE job/log streaming, and SQLite-persisted jobs + mutation audit; the frontend is a Vite + React + TypeScript app (repo-standard 2025 stack, pnpm) wrapped in a Tauri v2 desktop shell that spawns the backend as a bundled sidecar with single-instance and window-state behavior. The TUI keeps calling the same service functions, so behavior cannot drift between surfaces. Full decision log in [research.md](./research.md).

## Technical Context

**Language/Version**: Python ≥3.11 (backend), TypeScript 5.x (frontend), Rust stable (thin Tauri v2 shell only)
**Primary Dependencies**: FastAPI + uvicorn + pydantic v2 (backend); React + Vite + Zustand + TanStack Query/Virtual + Tailwind CSS v4 + Zod + Biome, `d3-force` for graph layout (frontend, pnpm); Tauri v2 with `shell`, `single-instance`, `window-state` plugins (desktop shell); PyInstaller for the sidecar binary
**Storage**: SQLite (new, small: jobs + mutation audit + diagnostics history, in platform user-data dir); everything else reads existing sources — repo files, `~/.claude`, OKF bundle, widget caches, live probes
**Testing**: pytest (contract/unit/integration for webapi, service extractions, safety protocol); Vitest + React Testing Library + MSW (frontend units/components); Playwright (E2E smoke against a fixture backend); `cargo test` only if the shell grows logic
**Target Platform**: Windows 11 first-class; Linux/macOS best-effort (matching existing product stance)
**Project Type**: Desktop application = local web frontend + local API backend + native shell wrapper
**Performance Goals**: usable data-populated workspace < 3 s warm (SC-002); tool statuses resolve async and always terminate (SC-003); interaction latency < 200 ms at 1,000+ sessions / 1,000+ graph nodes (SC-010)
**Constraints**: loopback-only + per-launch bearer token (FR-018); no mutation without prepare/execute ticket (FR-016, FR-014); single shared redaction rule set server-side (FR-019); TUI behavior unchanged (FR-015); Tauri not Electron (user-mandated); pnpm not npm/yarn (house rule, user-confirmed)
**Scale/Scope**: 22 feature modules, 8 user stories, ~60 HTTP endpoints + SSE channels, ~25 registered action descriptors

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol`. The HTTP/SSE surface is an internal contract between the shell/frontend and the local backend, documented in [contracts/](./contracts/). No A2A/MCP/JSON-RPC surface is implemented or modified.
- **Gate 2 — Subagent Delegation**: PASS — delegation table below maps every phase to owners from `.specify/memory/agents.md` (one noted roster addition, see table footnote).
- **Gate 3 — Contract Tests Before Implementation**: PASS — contract tests are required, written first, and ordered before implementation in `/speckit-tasks` for: (a) the web data API envelope + module endpoints ([contracts/web-api.contract.md](./contracts/web-api.contract.md)), (b) the jobs/SSE streaming protocol ([contracts/jobs-and-streams.contract.md](./contracts/jobs-and-streams.contract.md)), (c) the action-safety prepare/execute protocol incl. redaction and auth ([contracts/action-safety.contract.md](./contracts/action-safety.contract.md)), (d) the desktop shell ↔ backend lifecycle handshake ([contracts/desktop-shell.contract.md](./contracts/desktop-shell.contract.md)).
- **Gate 4 — Reversible Config Changes**: `N/A — no files under global/ change`. New code lives in `setup/src/cabal/webapi/`, `apps/cabal-desktop/`, and `tests/`. (The feature *reads and deploys* global config as data — it does not alter the deploy source.) Rollback = delete the new packages; the TUI and legacy web UI are untouched until the final retirement task, which is a single revertable commit.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A — no new skill or agent`.
- **Gate 6 — Parallel Isolation**: PASS — backend and frontend writers run concurrently in module tranches; phases and worktree requirements listed in the Parallel Execution Map. Matching tasks must carry `Parallel: yes` in `tasks.md`.

Post-Phase-1 re-check: no violations introduced by the design artifacts. Complexity Tracking is empty.

## Subagent Delegation

*GATE: references `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Service-layer extraction (Textual-free refactors), FastAPI app, routers, JobManager, action registry, security/handshake, SQLite persistence | `@python-architect` | Python package architecture, async design, service boundaries |
| Backend contract/unit/integration tests (pytest, TestClient, SSE) | `@python-tester` | Every Python test task goes to the Python tester |
| React app architecture: module routing, TanStack Query layer, Zustand stores, components, graph canvas, virtualized tables | `@react-architect` | Project uses exactly the 2025 stack (Vite + TS + Zustand + TanStack) |
| Design tokens, Tailwind theme, dark operational styling, state visuals, responsive layout | `@frontend-css` | CSS-only work never goes to a framework agent |
| Frontend tests (Vitest + RTL + MSW, Playwright smoke) | `@frontend-tester`¹ | Dedicated frontend testing specialist |
| Tauri shell (Rust): sidecar spawn/kill, single-instance, window-state, capabilities | `main` | No Rust specialist exists in the roster; the shell is deliberately thin (<200 LoC of glue) |
| Cross-cutting orchestration, contracts upkeep, ADR-level decisions, legacy retirement sequencing | `main` | Spans all domains |
| Post-implementation conformance audit | `@code-plan-verifier` | Read-only verification gate before commit |

¹ `@frontend-tester` exists in the deployed agent roster (`global/agents/frontend-tester.md`) but is missing from `.specify/memory/agents.md`; that file should gain its row (docs-only follow-up). It is not an invented name.

### Parallel Execution Map

*GATE 6: phases dispatching ≥2 concurrent writers.*

| Phase | Concurrent agents | Tasks (IDs) | Integration branch |
|---|---|---|---|
| Foundational: webapi core + app shell scaffold | `@python-architect`, `@react-architect` | assigned in tasks.md | `015-web-ui-overhaul` |
| Each module tranche (US2–US8): module endpoints + module UI | `@python-architect`, `@react-architect` | assigned in tasks.md | `015-web-ui-overhaul` |
| Styling passes alongside next tranche | `@frontend-css`, `@react-architect` | assigned in tasks.md | `015-web-ui-overhaul` |

Every writer in a concurrent batch is dispatched with `isolation: "worktree"` and merged back to `015-web-ui-overhaul`. Test authors run sequentially per surface (contract tests precede implementation per Gate 3). `tasks.md` MUST mark all batch members `Parallel: yes`.

## Project Structure

### Documentation (this feature)

```text
specs/015-web-ui-overhaul/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── checklists/
│   └── requirements.md
├── contracts/           # Phase 1
│   ├── web-api.contract.md
│   ├── jobs-and-streams.contract.md
│   ├── action-safety.contract.md
│   └── desktop-shell.contract.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
setup/src/cabal/
├── webapi/                      # NEW: FastAPI backend (replaces web/ at end)
│   ├── __init__.py
│   ├── __main__.py              # cabal-backend entrypoint (--project, handshake write)
│   ├── app.py                   # create_app(), router registration, lifespan
│   ├── security.py              # loopback bind, bearer token, handshake file, CORS
│   ├── envelope.py              # SnapshotEnvelope v2, ModuleHealth
│   ├── jobs.py                  # JobManager, SSE publishers
│   ├── actions.py               # ActionDescriptor registry, prepare/execute, digests
│   ├── audit.py                 # mutation audit + diagnostics persistence (SQLite)
│   ├── storage.py               # SQLite bootstrap in platformdirs user-data dir
│   └── routers/                 # one router per feature-module group
│       ├── system.py            # health, diagnostics, project context, jobs
│       ├── tools.py             # catalog, statuses, install/update actions
│       ├── config.py            # deploy tree, diff, apply, cleanup, restore, settings
│       ├── mcp.py               # scopes table, activate/disable actions
│       ├── local_config.py      # scaffold previews + apply actions
│       ├── knowledge.py         # bundle, graph, search, semantic, packs, ledger
│       ├── services.py          # service rows, start/stop, log streams
│       ├── security_scan.py     # package security scan + fix actions
│       ├── sessions.py          # sessions list/detail/delete
│       ├── account.py           # account, doctor, model assignments, info
│       ├── environment.py       # env vars, git identity, commit policy
│       ├── projects.py          # recents, browse, clone, provider auth, init wizard
│       └── codex.py             # codex deploy tree, local scaffold, conversion audit
├── redaction.py                 # MOVED here from web/redaction.py — single shared rule set
├── web/                         # legacy 011 package — untouched until final retirement task
└── (existing service modules)   # *_service.py, tool_catalog, diff_apply, mcp_ops,
                                 # local_setup, session_reader, okf/, package_security/,
                                 # service_supervisor, cleanup_service, model_assignments,
                                 # git_policy, claude_settings, codex_setup/ — shared layer

apps/cabal-desktop/              # NEW: pnpm workspace app
├── package.json                 # pnpm; scripts: dev, build, test, tauri
├── vite.config.ts / tsconfig.json / biome.json / tailwind config
├── src/
│   ├── main.tsx / App.tsx       # shell, nav, connectivity state
│   ├── api/                     # typed client, Zod schemas, envelope + auth handling
│   ├── stores/                  # Zustand: project context, ui prefs, job tray
│   ├── lib/                     # SSE hook, virtualization helpers, formatting
│   ├── components/              # shared: DataTable, DiffView, ConfirmDialog, JobPane,
│   │                            #   StatePill, DetailDrawer, LogStream, EmptyState
│   └── modules/                 # one folder per feature module (22)
│       ├── overview/  tools/  config-deploy/  cleanup-restore/  settings/
│       ├── mcp/  local-config/  knowledge/  services/  package-security/
│       ├── sessions/  account/  doctor/  model-assignments/  environment/
│       ├── git-identity/  provider/  init-project/  codex/  diagnostics/
│       └── project-gate/  project-dashboard/
├── src-tauri/                   # Tauri v2 shell (Rust, thin)
│   ├── tauri.conf.json          # externalBin: cabal-backend sidecar
│   ├── capabilities/default.json
│   └── src/main.rs              # sidecar lifecycle, single-instance, window-state
└── tests/                       # Vitest + RTL + MSW; e2e/ Playwright smoke

setup/build/
└── cabal-backend.spec           # NEW: PyInstaller spec for the sidecar binary

tests/                           # pytest (repo root, existing layout)
├── contract/
│   ├── test_webapi_envelope_contract.py
│   ├── test_webapi_modules_contract.py
│   ├── test_webapi_jobs_sse_contract.py
│   ├── test_webapi_action_safety_contract.py
│   └── test_webapi_handshake_contract.py
├── unit/            # redaction, digests, serial shapes, job state machine
└── integration/     # uvicorn lifecycle, SQLite persistence, service-layer parity
```

**Structure Decision**: Backend joins the existing `cabal` package (`webapi/`) so it imports the shared service layer directly — same process-model as the TUI, no RPC between Python parts. The frontend + shell live in a new top-level `apps/cabal-desktop/` because they have a foreign toolchain (pnpm, Rust) that must not entangle the Python package. `cabal/web/` is retired only in the final phase (research R12).

## Phase 0: Research

Complete — see [research.md](./research.md). Key decisions: Tauri v2 + PyInstaller sidecar (R1); FastAPI replaces stdlib server (R2); repo-standard React stack with pnpm (R3); SSE not WebSockets (R4); SQLite-persisted JobManager (R5); prepare/execute tickets with precondition digests (R6); ephemeral port + bearer-token handshake file (R7); parity via shared service layer, single server-side redaction (R8); d3-force canvas graph (R9); PyInstaller + tauri bundler packaging with browser-first dev loop (R10); embedded device login, streamed handoffs, external terminal for orchestrator dash (R11); staged legacy retirement (R12).

## Phase 1: Design & Contracts

Complete — artifacts:

- [data-model.md](./data-model.md) — entities, fields, relationships, and the Job/Ticket state machines.
- [contracts/web-api.contract.md](./contracts/web-api.contract.md) — envelope v2, auth, error model, full endpoint catalog per module.
- [contracts/jobs-and-streams.contract.md](./contracts/jobs-and-streams.contract.md) — job lifecycle + SSE event grammar + reconnect semantics.
- [contracts/action-safety.contract.md](./contracts/action-safety.contract.md) — prepare/execute protocol, precondition digests, audit, redaction guarantees.
- [contracts/desktop-shell.contract.md](./contracts/desktop-shell.contract.md) — sidecar lifecycle, handshake file, single-instance, shutdown ordering.
- [quickstart.md](./quickstart.md) — dev loop, test commands, production build.

## Phase 2: Task Generation Approach (for /speckit-tasks)

- **Foundational tranche (blocking)**: contract tests → security/handshake → envelope → JobManager → action registry → app shell + API client + design tokens. Backend and frontend foundations run as a parallel pair (worktrees).
- **Module tranches by story priority**: US1 (gate, overview, dashboard, diagnostics) → US2 (tools) → US3 (config deploy, cleanup/restore, settings, local config, codex) → US4 (sessions, account, doctor, models) → US5 (knowledge) → US6 (mcp, services) → US7 (provider, init wizard) → US8 (security, environment, identity). Each tranche: contract tests first, then backend router + frontend module in parallel worktrees, then a sequential integration/styling task.
- **Final tranche**: desktop shell hardening (single-instance, window-state, exit ordering), packaging (PyInstaller spec + tauri build), Playwright smoke, parity walkthrough against the 22-module table (SC-001), legacy `cabal/web/` retirement (R12), `@code-plan-verifier` audit.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
