# Implementation Plan: Codegen & Eval Workspace Modules

**Branch**: `021-codegen-eval-modules` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-codegen-eval-modules/spec.md`

## Summary

Give the two CLI-only subsystems — the .NET code generation pipeline (`cabal.dotnetgen`) and the agent eval harness (`cabal.evals`) — first-class Cabal Desktop modules, so neither requires a terminal for any primary workflow.

The technical approach is shaped by one finding from Phase 0 that overturns the obvious design: **the backend's job system cannot own these runs.** `JobManager` keeps jobs in an in-memory dict on daemon threads and never reloads them from SQLite, and the Tauri shell kills a backend it spawned on app exit. An eval matrix can run for hours; a job thread cannot. Both subsystems, however, already write durable, self-describing artifacts (`.dotnetgen/runs/<id>.json`, `evals/results/<id>/`), and the codegen approval gate is already a file-backed, TTL-free pending intent whose token is bound to a fingerprint of the solution tree.

So the design inverts the usual pattern: **runs execute as detached OS processes, and the on-disk artifact tree is the source of truth.** The backend supervises by reading artifacts, not by owning threads; the job record and SSE stream are a live *view* over a run, not the run itself. This is what makes "close the app, come back, resume" (FR-004, FR-005, FR-036) achievable rather than aspirational, and it makes reading CLI-produced runs (FR-045) fall out for free instead of being a separate code path.

Delivery is phased by module and by user-story priority. The codegen module's P1 slice (approval gate) and the eval module's P1 slice (read a comparison) are independently shippable and share only the run-supervision layer built first.

## Technical Context

**Language/Version**: Python ≥3.14 (backend + shared service layer); TypeScript 7 / React 19 (frontend); Rust (Tauri v2 shell — not modified by this feature)  
**Primary Dependencies**: FastAPI ≥0.115 (backend); Vite 8, TanStack Query 5, Zustand 5, Biome 2 (frontend); existing `cabal.webapi` action/job/SSE/audit infrastructure; the unmodified `cabal.dotnetgen` and `cabal.evals` packages  
**Storage**: Existing webapi SQLite (`jobs`, `tickets`, `audit`, `diagnostics`) for live handles and the audit trail; the subsystems' own on-disk artifact trees (`.dotnetgen/runs/`, `evals/results/`, `evals/` definitions) as the durable source of truth. No new database.  
**Testing**: pytest for backend, service layer, and contract tests (`tests/contract/`); Vitest + React Testing Library for frontend; Playwright for the approval-gate and long-run end-to-end flows  
**Target Platform**: Windows / macOS / Linux desktop via the existing Tauri v2 shell with a local FastAPI sidecar  
**Project Type**: Desktop application over a local backend — the existing 015 web-UI-overhaul structure, extended by two modules  
**Performance Goals**: Comparison view renders a completed matrix within 1s; per-cell progress visible within 2s of a cell finishing; the module remains interactive while a run streams  
**Constraints**: Neither subsystem's behaviour may change (FR-007); no write access to the user's real `~/.claude/` from an eval (SC-011); a run must survive app restart; the SSE ring buffer is 200 lines, so streaming is for liveness only and never for the record  
**Scale/Scope**: 2 modules, 8 user stories, 44 functional requirements. Roughly 12–16 new backend service/router files, ~10 new action descriptors, and two frontend module trees alongside the existing 22.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol`. This feature implements no published wire protocol. It consumes two internal Python packages and extends an internal REST + SSE surface whose conventions are set by `specs/015-web-ui-overhaul/contracts/`. The SSE usage follows the existing in-repo grammar in `cabal/webapi/sse.py`, not an external standard.
- **Gate 2 — Subagent Delegation**: **PASS** — delegation table below maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: **Required.** Four internal contract surfaces need tests written and observed failing first: (a) the codegen REST + action surface, (b) the eval REST + action surface, (c) the SSE event grammar for run progress, (d) the definition-authoring round-trip (a definition written by the module must be byte-equivalent in meaning to a hand-written one and must validate under the unmodified CLI). Contract tests live in `tests/contract/` and MUST precede their implementation tasks in `tasks.md`.
- **Gate 4 — Reversible Config Changes**: `N/A` — this feature adds nothing under `global/`. It touches `apps/cabal-desktop/`, `setup/src/cabal/webapi/`, and `specs/`. The `/dotnet-codegen` skill in `global/skills/` is **not** modified; the module is an additional front end to the same CLI. If a later task does need to touch `global/`, rollback is the standard apply-script re-run documented in Principle IV.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A` — no new skill and no new agent. The existing `/dotnet-codegen` skill keeps its role as the conversational front end; this feature adds GUI modules, which are not skills. Nothing in `global/agents/` changes.
- **Gate 6 — Parallel Isolation**: **Applies.** Two phases dispatch concurrent writing agents; see the Parallel Execution Map below.

**Post-Phase-1 re-check**: **PASS.** The Phase 1 design introduced no new external protocol (Gate 1 unchanged), no new skill or agent (Gate 5 unchanged), and nothing under `global/` (Gate 4 unchanged). Gate 3's surface list grew by one — the definition round-trip contract — which is recorded above and reflected in `contracts/`. No entries were added to Complexity Tracking.

## Subagent Delegation

*GATE: Must reference `.specify/memory/agents.md` before generating tasks.*

| Phase / concern | Owner | Why |
|---|---|---|
| Run-supervision layer (detached process launch, artifact reconciliation, restart recovery) | `@python-architect` | Service-layer and process-lifecycle design in a Python package; the hardest structural decision in the feature |
| Backend services + FastAPI routers for both modules | `@python-architect` | FastAPI router and service-layer structure |
| Action descriptors (prepare/execute, precondition digests) | `@python-architect` | Extends the existing `actions_catalog/` pattern |
| Definition-authoring read/write + round-trip preservation | `@python-architect` | Format-preserving serialisation over the existing `definitions_model` |
| Backend + contract tests | `@python-tester` | pytest, contract tests against the wire format |
| Codegen module UI (approval gate, cost views, run history) | `@react-architect` | Vite + TypeScript + Zustand + TanStack Query — matches the 2025 stack exactly |
| Eval module UI (launch, live matrix, comparison, definition editor) | `@react-architect` | Same stack; the comparison view is the feature's hardest UI problem |
| All CSS for both modules | `@frontend-css` | Constitution II — CSS-only work never goes to a framework agent |
| Comparison-view and approval-gate interaction design | `@ux-analyst` | Both surfaces present contested or partial evidence (ties, judge errors, low-n aggregates) where a naive layout actively misleads |
| Frontend + end-to-end tests | `@frontend-tester` | Vitest, RTL, Playwright for the long-run and gate flows |
| Cross-cutting integration, ADRs, spec artifacts, release-notes update | `main` | Spans Python, TypeScript, and docs; no single specialist owns it |

### Parallel Execution Map

*GATE 6: Required when ≥2 writing subagents run concurrently in any phase.*

| Phase | Concurrent agents | Tasks (IDs) | Integration branch |
|---|---|---|---|
| US1 + US2 implementation (codegen gate ‖ eval comparison) | `@python-architect`, `@react-architect` | assigned by `/speckit-tasks` | `021-codegen-eval-modules` |
| US3–US6 implementation (eval launch ‖ codegen cost ‖ definition authoring) | `@python-architect`, `@react-architect`, `@frontend-css` | assigned by `/speckit-tasks` | `021-codegen-eval-modules` |

Every agent in each batch receives `isolation: "worktree"` at dispatch and merges back to the integration branch. The matching tasks in `tasks.md` MUST carry `Parallel: yes`. The hard cap of 4 concurrent subagents applies. See [`docs/parallel-isolation.md`](../../docs/parallel-isolation.md).

**Sequencing constraint**: the run-supervision layer is built first, sequentially, by `@python-architect` alone. Both modules depend on it, and parallelising work that shares an unbuilt foundation produces merge conflicts rather than speed.

## Project Structure

### Documentation (this feature)

```text
specs/021-codegen-eval-modules/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── codegen-api.md
│   ├── evals-api.md
│   ├── run-events.md
│   └── definition-roundtrip.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
setup/src/cabal/webapi/
├── run_supervisor.py            # NEW — detached process launch, PID/liveness, artifact reconciliation
├── codegen_service.py           # NEW — dotnetgen: runs, pending intent, cost records, stage bindings
├── evals_service.py             # NEW — evals: definitions, matrix runs, comparison reduction
├── evals_definitions_service.py # NEW — format-preserving read/write of the benchmark tree
├── actions_catalog/
│   ├── codegen.py               # NEW — approve/reject gate, start run, new service
│   └── evals.py                 # NEW — launch/cancel/resume matrix, save/delete definitions
└── routers/
    ├── codegen.py               # NEW
    └── evals.py                 # NEW

setup/src/cabal/dotnetgen/        # UNCHANGED — consumed, never modified
setup/src/cabal/evals/            # UNCHANGED — consumed, never modified

apps/cabal-desktop/src/
├── api/
│   ├── codegen.ts               # NEW
│   └── evals.ts                 # NEW
└── modules/
    ├── codegen/                 # NEW
    │   ├── CodegenModule.tsx
    │   ├── components/          # ApprovalGate, StageCostTable, StageBindings, RunHistory
    │   └── hooks/
    ├── evals/                   # NEW
    │   ├── EvalsModule.tsx
    │   ├── components/          # MatrixLauncher, LiveMatrix, ComparisonView, DefinitionEditor
    │   └── hooks/
    └── registry.ts              # MODIFIED — two new entries

tests/
├── contract/                    # codegen-api, evals-api, run-events, definition-roundtrip
└── integration/

apps/cabal-desktop/tests/         # Vitest + RTL; Playwright for gate and long-run flows
```

**Structure Decision**: This extends the existing 015 web-UI-overhaul layout rather than introducing a new one — a FastAPI backend under `setup/src/cabal/webapi/` paired with a Vite/React frontend under `apps/cabal-desktop/src/modules/`, each module a directory with `components/` and `hooks/` siblings, registered in `modules/registry.ts`. The one structural addition is `run_supervisor.py`, which is deliberately module-agnostic: both modules need detached-process supervision with artifact-based reconciliation, and building it twice would guarantee they diverge.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.

The one design decision that *looks* like added complexity — running work as detached OS processes instead of using the existing `JobManager` — is documented in [research.md](./research.md) R1 as a correctness requirement, not a preference. The simpler alternative (a job thread) cannot satisfy FR-004, FR-005, or FR-036, because the Tauri shell kills the backend it spawned on app exit and `JobManager` never rehydrates from SQLite.
