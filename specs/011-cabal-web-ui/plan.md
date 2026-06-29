# Implementation Plan: Cabal Web UI

**Branch**: `feat/011-cabal-web-ui` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-cabal-web-ui/spec.md`

## Summary

Add a local, read-only web interface for Cabal that presents existing Tools, OKF knowledge, and project-dashboard data in a modern dark browser application. The technical approach is to keep the frontend as static HTML/CSS/vanilla JavaScript with no build step, expose a small localhost-only Python JSON backend over existing Cabal service modules, and share serialization/redaction rules so the browser never invents or leaks data.

## Technical Context

**Language/Version**: Python >=3.11 for Cabal backend; HTML5, CSS, and vanilla JavaScript for frontend assets  
**Primary Dependencies**: Existing Cabal Python package, stdlib `http.server`/`json`/`threading`/`urllib.parse`, existing Textual-independent service modules; no frontend framework or Node build dependency planned  
**Storage**: No new persistent storage for MVP; reads existing repo files, generated OKF bundle, dashboard cache, and live Cabal probes  
**Testing**: pytest contract/unit/integration tests for serializers and HTTP endpoints; lightweight static asset tests; manual browser visual check for desktop/narrow layouts  
**Target Platform**: Local developer machine on Windows first; Linux/macOS best effort through localhost browser and existing Cabal service behavior  
**Project Type**: Python local app with static web frontend and local read API  
**Performance Goals**: Initial shell and cached overview render within 3 seconds on warm local probes; slow sections load independently without blocking navigation  
**Constraints**: Localhost-only, read-only MVP, no secrets in payloads or DOM, no writes under `global/`, no public hosting assumption, no frontend framework, existing TUI remains available  
**Scale/Scope**: 5 primary views, roughly 50+ tool rows, one OKF graph snapshot, one current project dashboard snapshot, diagnostics for backend/data source health

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0, the following gates apply:

- **Gate 1 - Spec-First Conformance**: N/A - no external third-party protocol is implemented. The feature exposes an internal localhost JSON contract documented in [contracts/web-data-api.contract.md](./contracts/web-data-api.contract.md).
- **Gate 2 - Subagent Delegation**: PASS - the delegation table below maps backend, frontend, CSS, tests, and verification to existing agents from `.specify/memory/agents.md`.
- **Gate 3 - Contract Tests Before Implementation**: PASS - contract tests are required before implementation for the web data API, frontend behavior/state contract, and redaction/local-only safety boundary.
- **Gate 4 - Reversible Config Changes**: PASS - no `global/` config changes. The web UI is launched from the repo/app and can be removed without changing deployed Claude config.
- **Gate 5 - Minimal Skill & Agent Surface**: PASS - no new skill or agent is added.
- **Gate 6 - Parallel Isolation**: PASS - implementation should be sequential for MVP because backend contracts, serializers, static assets, and tests are tightly coupled. If later tasks parallelize Python and frontend writers, `/speckit-tasks` must mark them `Parallel: yes` and dispatch them in worktrees.

No constitution violations are expected.

## Subagent Delegation

*GATE: Must reference `.specify/memory/agents.md` before generating tasks.*

| Phase / concern | Owner | Why |
|---|---|---|
| Local backend server, route dispatch, serializers, Cabal service integration | `@python-architect` | Python package architecture and service boundary design |
| Backend contract/unit/integration tests | `@python-tester` | pytest ownership for Python API and serialization tests |
| Vanilla JavaScript state, routing, fetch lifecycle, accessibility, and frontend test hooks | `@frontend-architect` | Browser UI architecture without the React 2025 stack |
| Dark application styling, responsive layout, density, state colors, and visual polish | `@frontend-css` | CSS-only work must be delegated to the CSS specialist |
| Cross-artifact orchestration, spec/plan consistency, quickstart, and read-only product safety decisions | `main` | Spans product scope, docs, and implementation sequencing |
| Final conformance audit | `@code-plan-verifier` | Read-only verification against plan, contracts, and repo rules |

### Parallel Execution Map

N/A - MVP implementation is planned as sequential. The feature has shared contracts and state names that are easier to keep coherent with one writing lane at a time.

## Project Structure

### Documentation (this feature)

```text
specs/011-cabal-web-ui/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── contracts/
    ├── frontend-ui.contract.md
    ├── local-safety-redaction.contract.md
    └── web-data-api.contract.md
```

### Source Code (repository root)

```text
setup/src/cabal/
├── web/
│   ├── __init__.py
│   ├── __main__.py
│   ├── api.py
│   ├── redaction.py
│   ├── serializers.py
│   ├── server.py
│   └── assets/
│       ├── app.js
│       ├── index.html
│       └── styles.css
├── tool_catalog.py
├── tools.py
├── models/
│   └── dashboard.py
└── okf/
    ├── graph.py
    └── viewer.py

tests/
├── contract/
│   ├── test_cabal_web_api_contract.py
│   ├── test_cabal_web_frontend_contract.py
│   └── test_cabal_web_redaction_contract.py
├── unit/
│   ├── test_cabal_web_redaction.py
│   └── test_cabal_web_serializers.py
└── integration/
    ├── test_cabal_web_assets.py
    └── test_cabal_web_server.py
```

**Structure Decision**: Add `setup/src/cabal/web/` as a small local-web package. Keep browser assets static and colocated under `assets/`; keep backend route and serialization code separate from Textual screens so both TUI and web UI can consume the same Cabal data sources.

## Phase 0: Research

Resolved in [research.md](./research.md):

- Use static HTML/CSS/vanilla JavaScript with no build step.
- Use a stdlib localhost Python server for MVP rather than FastAPI or a Node dev server.
- Keep the MVP read-only; install/update/configuration actions need a separate safety design.
- Serialize all responses through versioned JSON envelopes.
- Reuse existing Cabal services and models as source of truth.
- Redact secrets before data crosses the backend/browser boundary.
- Design the dark UI as a dense operational dashboard, not a landing page.

## Phase 1: Design and Contracts

Generated artifacts:

- [data-model.md](./data-model.md)
- [contracts/web-data-api.contract.md](./contracts/web-data-api.contract.md)
- [contracts/frontend-ui.contract.md](./contracts/frontend-ui.contract.md)
- [contracts/local-safety-redaction.contract.md](./contracts/local-safety-redaction.contract.md)
- [quickstart.md](./quickstart.md)

## Phase 2: MVP Implementation Plan

1. Add failing contract tests for API envelopes, read-only methods, response schemas, redaction, and static asset expectations.
2. Add `cabal.web.redaction` and serializer helpers that convert existing Cabal tool, OKF, dashboard, and diagnostics data into JSON-safe dictionaries.
3. Add `cabal.web.api` route handlers for health, overview, tools, knowledge graph, project health, and diagnostics.
4. Add `cabal.web.server` and `python -m cabal.web` entrypoint that binds only to `127.0.0.1`, serves static assets, serves JSON endpoints, and rejects mutating HTTP methods.
5. Build `index.html`, `styles.css`, and `app.js` as a framework-free dark application shell with Overview, Tools, Knowledge, Project Health, and Diagnostics views.
6. Implement frontend fetch lifecycle: independent section loading, stale/error states, retry, schema-version mismatch handling, and redacted DOM rendering.
7. Implement Tools view: category rail, search/filter controls, state summaries, status badges, and tool detail drawer.
8. Implement Knowledge view: graph summary, searchable node/relation lists, lightweight SVG/canvas-free relationship map or grouped route lanes, and inspector evidence.
9. Implement Project Health view: Git/GitHub/Supabase/Vercel sections with source freshness and no token rendering.
10. Add backend and asset integration tests, then run existing Cabal-focused tests to ensure the TUI still works.
11. Perform manual browser verification on desktop and narrow widths, including no overlapping text, usable dark theme, and backend failure states.
12. Run `@code-plan-verifier` as a read-only audit before commit.

## Final MVP Read-Only Boundary

The implemented MVP exposes only static assets and `GET`/`HEAD`/`OPTIONS` JSON reads. Browser-triggered `POST`, `PUT`, `PATCH`, and `DELETE` requests return `405` error envelopes. There are no endpoints for tool installation, tool updates, cleanup, configuration edits, git changes, shell execution, file export, or arbitrary filesystem reads.

Mutation-capable workflows are deferred until a separate safety contract exists. That future design must include explicit action manifests, per-action confirmation copy, dry-run previews, scoped project roots, audit logging, cancellation behavior, and tests proving that no browser request can mutate the workstation without the accepted confirmation flow.

## Complexity Tracking

No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

## Post-Design Constitution Recheck

**Status**: PASS

The design defines internal contracts before implementation, keeps the feature read-only and local, delegates Python/frontend/CSS/tests to existing agents, avoids `global/` changes, adds no new skill or agent, and plans sequential implementation for MVP.

## Next Command

Run `/speckit-tasks` for `011-cabal-web-ui` after accepting this plan.
