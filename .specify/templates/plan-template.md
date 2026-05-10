# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0, the following gates apply:

- **Gate 1 — Spec-First Conformance**: If this feature implements an external protocol (A2A, MCP, JSON-RPC, OpenAPI, MCP), link the canonical spec here and state the conformance scope. If not applicable, write `N/A — no external protocol`.
- **Gate 2 — Subagent Delegation**: Delegation table below (next section) maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: For each protocol surface, contract test tasks must appear before their implementation tasks in `tasks.md`. State here which surfaces require contract tests, or `N/A`.
- **Gate 4 — Reversible Config Changes**: If this feature touches `global/`, document the rollback path here. Otherwise `N/A`.
- **Gate 5 — Minimal Skill & Agent Surface**: If this feature adds a new skill or agent, justify why an existing one cannot be extended. Otherwise `N/A`.
- **Gate 6 — Parallel Isolation**: If any phase dispatches two or more writing subagents concurrently, list those phases in the Parallel Execution Map below and mark the affected tasks `Parallel: yes` in `tasks.md`. The dispatcher MUST pass `isolation: "worktree"` (or pre-create a worktree) for each concurrent writer. If no phase runs writers in parallel, write `N/A`.

Any violation must be either resolved or recorded in the Complexity Tracking table with explicit justification.

## Subagent Delegation

*GATE: Must reference `.specify/memory/agents.md` before generating tasks.*

This project has named subagents (`@dotnet-architect`, `@python-architect`, `@frontend-architect`, `@react-architect`, `@frontend-css`, `@unity-architect`, plus testers and orchestrators). Read `.specify/memory/agents.md` and produce a delegation table mapping each phase of work to its owner.

| Phase / concern | Owner | Why |
|---|---|---|
| [e.g., backend service layer] | [e.g., `@python-architect`] | [e.g., FastAPI structure decision] |
| [e.g., backend tests] | [e.g., `@python-tester`] | [e.g., pytest + real DB] |
| [e.g., UI components] | [e.g., `@react-architect` or `@frontend-architect`] | [e.g., matches/does-not-match 2025 stack] |
| [e.g., styling] | [e.g., `@frontend-css`] | [always — never let a framework agent do CSS] |
| [orchestration / cross-cutting] | `main` | [e.g., spans multiple domains] |

If no specialist matches a phase, explain why in the table and assign `main`. Do not invent agent names — use only those in `agents.md`.

### Parallel Execution Map

*GATE 6: Required when ≥2 writing subagents run concurrently in any phase. Otherwise write `N/A`.*

List every phase that dispatches two or more writing subagents in parallel. Each row represents a concurrent batch — every agent in the batch will receive `isolation: "worktree"` at dispatch time and must be merged back to the integration branch when done.

| Phase | Concurrent agents | Tasks (IDs) | Integration branch |
|---|---|---|---|
| [e.g., US1 implementation] | `@python-architect`, `@react-architect` | T012, T013 | [e.g., `feat/orders`] |
| [...] | [...] | [...] | [...] |

If any row appears here, the matching tasks in `tasks.md` MUST carry `Parallel: yes`. See [`docs/parallel-isolation.md`](../../docs/parallel-isolation.md) for the rule, the dispatch contract, and edge cases.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
