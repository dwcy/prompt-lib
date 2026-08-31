# Implementation Plan: Environment Variables — Multi-Source Browser

**Branch**: `020-env-variable-sources` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-env-variable-sources/spec.md`

## Summary

Turn the Environment module from a two-pill Curated/System view into a multi-source, read-only
variable browser for the selected project. Config files discovered in the repo, .NET's layered
settings and its out-of-repo developer secret store, plus Azure, Vercel, and GitHub, each
contribute tabs that appear only when actually detected. Every tab loads **names and metadata
only**; a per-row eye control fetches one value on demand, and each entry declares up front
whether its value is retrievable at all.

Technical approach: one collector module per source under `setup/src/cabal/`, following the
existing `dashboard_vercel_service.py` shape (all subprocess/network I/O isolated, never raises,
returns an `AvailabilityState` plus a hint). Pure link detection joins `dashboard_links.py`. A new
`envsources_service.py` fans out to the collectors concurrently and assembles one payload. Two new
routes: a listing route (names only) and a single-entry reveal route that audits every call. The
frontend replaces the two-pill switcher with a dynamic tab strip driven entirely by what the
backend reports.

## Technical Context

**Language/Version**: Python 3.14 (backend, `setup/src/cabal/`), TypeScript 5.x + React 19 (frontend, `apps/cabal-desktop/`)
**Primary Dependencies**: FastAPI, uvicorn, psutil, platformdirs (backend); Vite, TanStack Query, Zustand, Zod, Biome (frontend). No new runtime dependency is required — `az`, `gh`, and `vercel` are consumed as external processes, and Vercel additionally via its REST API using `urllib` as `dashboard_vercel_service.py` already does.
**Storage**: SQLite via the existing `webapi/storage.py` for audit records only. Revealed values are never persisted (FR-015).
**Testing**: pytest (`setup/tests/`, contract tests under `setup/tests/contract/`); Vitest + React Testing Library + MSW (`apps/cabal-desktop/tests/`)
**Target Platform**: Windows/macOS/Linux desktop — Tauri shell plus the `run web` browser workspace
**Project Type**: Web application (shared Python service layer + FastAPI backend, React frontend)
**Performance Goals**: First usable content within 3s regardless of external source count (SC-010); local config discovery within 3s with no network (SC-001)
**Constraints**: Read-only against all three providers (FR-023); names-only on load (FR-008); no external source may block render (FR-039); reveals never cached to disk (FR-015)
**Scale/Scope**: 5 source kinds, 47 functional requirements, 7 user stories. Expect up to ~50 discovered config files in a monorepo and a few hundred entries per source.

**Resolved by research** (see [research.md](./research.md)): value retrievability per provider,
.NET config precedence and key flattening, the secret-store id lookup, the concurrency model for
fanning out to collectors, and the reveal route's audit shape.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol`. The feature *consumes* three
  third-party APIs but implements none. It publishes no protocol of its own beyond this app's
  existing internal envelope contract, which is unchanged.
- **Gate 2 — Subagent Delegation**: satisfied — see the Subagent Delegation table below. Every
  phase maps to an owner drawn from `.specify/memory/agents.md`, except the UX review, which the
  roster has no owner for and which therefore falls to `main` with the reason stated, as the
  constitution permits. See Roster drift below.
- **Gate 3 — Contract Tests Before Implementation**: **required**. Two REST surfaces are added
  (`GET /api/env/sources`, `POST /api/env/reveal`). Contract tests for both live in
  `setup/tests/contract/test_env_sources_contract.py` and MUST be written and observed failing
  before the route implementations. The per-provider collectors are internal functions, not
  protocol surfaces, so they take ordinary unit tests.
- **Gate 4 — Reversible Config Changes**: `N/A`. Nothing under `global/` changes. The one write
  this feature performs is the per-project Azure link (FR-025), stored in this app's own
  platform data directory — not in `~/.claude/` — and clearable from the UI (FR-033).
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A`. No new skill and no new agent. The feature
  extends the existing `environment` module and adds service modules alongside the existing
  `dashboard_*_service.py` family.
- **Gate 6 — Parallel Isolation**: **applies** — see the Parallel Execution Map below. The three
  provider collectors are the natural parallel batch.

No violations. Complexity Tracking is empty.

**Post-design re-check**: still passing. Phase 1 added no protocol surface beyond the two routes
already covered by Gate 3, added no dependency, and introduced no new skill or agent.

## Subagent Delegation

*GATE: references `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Link detection + config-file discovery (pure parsing) | `@python-architect` | Module boundaries alongside `dashboard_links.py`; no I/O, heavy on structure |
| Per-provider collectors (Azure, Vercel, GitHub, .NET secret store) | `@python-architect` | Subprocess/REST isolation, `AvailabilityState` degradation contract |
| Reveal route + audit wiring | `@python-architect` | FastAPI route design and the single-entry retrieval contract |
| Backend contract + unit tests | `@python-tester` | pytest, contract tests under `setup/tests/contract/` |
| Dynamic tab strip, source/entry components, reveal interaction | `@react-architect` | Matches the Vite + Zustand + TanStack + Zod stack exactly |
| Tab strip, source badges, retrievability states, overflow styling | `@frontend-css` | CSS-only work always goes here, regardless of framework |
| Frontend tests (Vitest, RTL, MSW fixtures) | `@frontend-tester` | MSW fixtures per source and per degradation state |
| Retrievability states, empty/degraded copy, reveal affordance review | `main` | Five distinct non-happy states need a behaviour review before build, but `.specify/memory/agents.md` lists no UX reviewer — see Roster drift below |
| Post-implementation verification against this plan | `@code-plan-verifier` | Read-only check that the 47 requirements landed |
| Orchestration, ADRs, cross-cutting glue | `main` | Spans Python + TypeScript + three external providers |

### Parallel Execution Map

*GATE 6.*

| Phase | Concurrent agents | Tasks (IDs) | Integration branch |
|---|---|---|---|
| Provider collectors (US3, US4, US5) | `@python-architect` ×3 — one per provider | assigned in `tasks.md` | `020-env-variable-sources` |

The three provider collectors are genuinely independent files with no shared state, which makes
them the one batch worth running concurrently. Each writer gets `isolation: "worktree"` and merges
back to the feature branch. Everything else is sequential: the discovery layer must land before the
collectors that build on its link detection, and the frontend needs the contract fixed first.

Note for the dispatcher: this repository is currently being edited by more than one session. Even
the sequential phases should confirm the working tree is theirs before writing. See
[`docs/parallel-isolation.md`](../../docs/parallel-isolation.md).

### Roster drift (finding, not a blocker)

`.specify/memory/agents.md` is a subset of the agents this harness actually offers. `@ux-analyst`
exists and is the right owner for reviewing the five non-happy states, but it is absent from the
roster file, and Gate 2 forbids inventing names. Those tasks are assigned to `main` rather than
silently naming an agent the governance file does not know about.

Same gap applies to `@frontend-designer`, `@api-designer`, and `@solution-architect`. Worth
reconciling `agents.md` with the live roster in its own change — not folded into this feature.

## Project Structure

### Documentation (this feature)

```text
specs/020-env-variable-sources/
├── plan.md              # This file
├── spec.md              # 47 requirements, 7 user stories
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist (+ .NET amendment record)
├── contracts/
│   ├── env-sources.contract.md   # GET /api/env/sources
│   └── env-reveal.contract.md    # POST /api/env/reveal
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
setup/src/cabal/
├── dashboard_links.py                  # EXTENDED: azure link ladder, vercel/github reuse
├── envsource_discovery.py              # NEW: repo config-file scan, pure; no I/O beyond reads
├── envsource_dotnet.py                 # NEW: appsettings layering, key flattening, UserSecretsId
├── envsource_azure_service.py          # NEW: az CLI collector
├── envsource_vercel_service.py         # NEW: vercel REST collector
├── envsource_github_service.py         # NEW: gh collector
├── models/
│   └── envsources.py                   # NEW: source/container/entry/retrievability dataclasses
└── webapi/
    ├── envsources_service.py           # NEW: fan-out, assembly, reveal dispatch
    └── routers/
        └── environment.py              # EXTENDED: two new routes; existing routes untouched

setup/tests/
├── contract/
│   └── test_env_sources_contract.py    # NEW: both routes, wire format (Gate 3)
├── test_envsource_discovery.py         # NEW
├── test_envsource_dotnet.py            # NEW
└── test_envsource_collectors.py        # NEW: degradation matrix per provider

apps/cabal-desktop/src/
├── api/
│   └── envSources.ts                   # NEW: zod schemas + query/mutation hooks
├── modules/environment/
│   ├── EnvironmentModule.tsx           # EXTENDED: dynamic tabs replace the two-pill switcher
│   ├── EnvironmentModule.css           # EXTENDED
│   └── components/
│       ├── EnvSourceTabs.tsx           # NEW: dynamic, overflow-aware tab strip
│       ├── EnvSourceTable.tsx          # NEW: names + metadata + reveal column
│       ├── RevealCell.tsx              # NEW: the eye, and its three retrievability states
│       └── EnvSourceEmptyState.tsx     # NEW: not-linked / empty / degraded copy
└── ...

apps/cabal-desktop/tests/
├── envSources.test.tsx                 # NEW
└── msw/fixtures.ts                     # EXTENDED: per-source and per-degradation fixtures
```

**Structure Decision**: Web application. The backend follows this repo's established split —
pure parsing in a plain module (`dashboard_links.py` and the new `envsource_discovery.py`),
side-effecting collectors in per-provider `*_service.py` files, and orchestration in
`webapi/envsources_service.py`. That is the same shape as the existing dashboard collectors, so
the module boundary is already proven here. The frontend follows the existing per-module layout
under `src/modules/environment/`, with a `src/api/envSources.ts` client mirroring
`src/api/securityEnvironment.ts`.

The existing curated/system routes, the `env.apply` action, and `redaction.py` are unchanged;
this feature only adds alongside them (FR-002).

## Complexity Tracking

No constitution violations. Table intentionally empty.
