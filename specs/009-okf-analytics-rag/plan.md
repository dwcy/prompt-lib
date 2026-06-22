# Implementation Plan: OKF Analytics and RAG Index

**Branch**: `feat/009-okf-analytics-rag` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md) | **Status**: Draft

## Summary

Add a SQLite-backed analytics and retrieval layer on top of the generated OKF bundle. SQLite is the default runtime index because the workload is local, app-like, offline, and search-heavy. DuckDB remains an optional later backend for heavier analytics and notebook-style exploration, not a default Cabal dependency.

MVP delivers:

- Local SQLite index built from `docs/okf/prompt-lib/`.
- FTS-backed search over concepts/chunks.
- Graph health analytics for agent/skill route pressure, unused agents, overlap, density, and changed concepts.
- Analytics-aware graph visualization with lenses for route pressure, overlap, unused agents, and changes.
- Cabal Knowledge screen summary.

Post-MVP delivers:

- Graph-backed context packs for agent use.
- Optional semantic overlap via embedding provider interface.
- Optional DuckDB analytics/export backend for historical snapshots and analytical exploration.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: stdlib `sqlite3`, existing Cabal/Textual, pytest  
**Storage**: Local generated SQLite cache, recommended default `.cabal/okf/index.sqlite`; OKF Markdown/JSON remains source of truth  
**Testing**: pytest unit, contract, integration; Textual `run_test()` for UI slice  
**Target Platform**: Windows, Linux, macOS local checkouts  
**Project Type**: Python package/CLI/Textual TUI feature  
**Performance Goals**: Index current OKF bundle under 10 seconds; analytics query under 1 second for current repo scale  
**Constraints**: Offline by default, no new hard dependency, no committed binary index required, no secret leakage  
**Scale/Scope**: Hundreds to low thousands of concept docs initially; design supports larger catalogs by rebuilding deterministic cache

## Constitution Check

### Gate 1 - Spec-First Conformance

**Status**: PASS

No new external protocol is implemented. The feature consumes the OKF bundle produced by feature 008 and keeps OKF as source of truth.

### Gate 2 - Subagent Delegation

**Status**: PASS

Delegation table is defined below using existing agents only.

### Gate 3 - Contract Tests Before Implementation

**Status**: PASS

Contract tests are required for:

- SQLite index CLI/report surface.
- Analytics JSON shape.
- Visual analytics viewer behavior.
- Context pack JSON shape.

These must precede implementation tasks.

### Gate 4 - Reversible Config Changes

**Status**: PASS

No deployed `global/` config mutation is required. `.cabal/okf/index.sqlite` is generated local cache and can be deleted/rebuilt.

### Gate 5 - Minimal Skill & Agent Surface

**Status**: PASS

No new skills or agents required. Existing Cabal Knowledge screen is extended.

### Gate 6 - Parallel Isolation

**Status**: PASS

Parallelizable test and UI tasks touch disjoint paths. Any concurrent writer tasks must be marked `Parallel: yes` in generated tasks and dispatched with worktree isolation.

## Subagent Delegation

| Phase / concern | Owner | Why |
|---|---|---|
| SQLite schema/index/search implementation | `@python-architect` | Python service/package architecture |
| Analytics report queries and context-pack service | `@python-architect` | Python data processing and API design |
| Analytics graph lenses and viewer integration | `@frontend-css`, `@python-architect` | Static viewer behavior plus Textual/HTML polish |
| Contract/unit/integration tests | `@python-tester` | pytest and fixture coverage |
| Cabal Knowledge UI summary | `@python-architect` | Textual Python screen/widget changes |
| Optional Textual styling polish | `@frontend-css` | CSS-only/Textual style work |
| Docs, source-of-truth policy, task orchestration | main | Cross-cutting documentation and coordination |
| Final conformance audit | `@code-plan-verifier` | Read-only verification |

### Parallel Execution Map

| Phase | Concurrent agents | Tasks | Integration branch |
|---|---|---|---|
| Contract/tests and service implementation after schema contract stabilizes | `@python-tester`, `@python-architect` | TBD by `/speckit-tasks` | `feat/009-okf-analytics-rag` |
| UI summary and docs after analytics API stabilizes | `@python-architect`, main | TBD by `/speckit-tasks` | `feat/009-okf-analytics-rag` |

## Project Structure

### Documentation

```text
specs/009-okf-analytics-rag/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
`-- contracts/
    |-- sqlite-index.contract.md
    |-- analytics-report.contract.md
    |-- visual-analytics.contract.md
    `-- context-pack.contract.md
```

### Source Code

```text
setup/src/cabal/okf/
|-- index.py              # SQLite schema, rebuild, FTS search
|-- analytics.py          # health reports and overlap detection
|-- context.py            # graph-expanded context packs
|-- embeddings.py         # optional provider interface, no default provider
|-- viewer.py             # analytics lenses in static graph viewer
|-- __main__.py           # index/search/analytics/context commands
`-- recommendations.py    # may reuse context pack later

setup/src/cabal/views/
`-- knowledge.py          # analytics summary in Cabal

tests/
|-- contract/
|   |-- test_okf_sqlite_index_contract.py
|   |-- test_okf_analytics_contract.py
|   |-- test_okf_visual_analytics_contract.py
|   `-- test_okf_context_pack_contract.py
|-- unit/
|   |-- test_okf_index.py
|   |-- test_okf_analytics.py
|   `-- test_okf_context.py
`-- integration/
    |-- test_okf_analytics_cli.py
    |-- test_okf_visual_analytics_viewer.py
    `-- test_okf_knowledge_analytics_ui.py
```

**Structure Decision**: Keep the index as a generated local cache under Cabal's OKF package. Do not add DuckDB to `pyproject.toml` for MVP.

## Phase 0: Research

Resolved in [research.md](./research.md):

- SQLite is default because it is built into Python, supports local FTS5, and fits mutable app-cache workflows.
- DuckDB is optional later for analytical exploration, historical snapshots, larger joins, and notebook-style workflows.
- Analytics should use layered evidence: graph first, text/FTS second, semantic embeddings later.
- Context packs are the first RAG deliverable; embeddings are optional post-MVP.

## Phase 1: Design and Contracts

Generated artifacts:

- [data-model.md](./data-model.md)
- [contracts/sqlite-index.contract.md](./contracts/sqlite-index.contract.md)
- [contracts/analytics-report.contract.md](./contracts/analytics-report.contract.md)
- [contracts/visual-analytics.contract.md](./contracts/visual-analytics.contract.md)
- [contracts/context-pack.contract.md](./contracts/context-pack.contract.md)
- [quickstart.md](./quickstart.md)

## Phase 2: MVP Implementation Plan

1. Add `.cabal/` generated-cache ignore policy if missing.
2. Implement SQLite schema and index rebuild from OKF bundle.
3. Add FTS search over concepts/chunks.
4. Implement analytics report categories:
   - agents with many incoming routes
   - skills with many outgoing routes
   - agents never referenced
   - graph overlap between skills
   - text overlap between skills
   - same-agent/similar-reason route groups
   - relation density by category
   - changed concepts since previous index
5. Add CLI commands: `index`, `search`, `analytics`.
6. Add analytics-aware visualization:
   - graph lenses for route pressure, fanout, overlap, unused agents, and changed concepts
   - finding-driven highlighting
   - inspector drill-down with evidence, shared agents, shared terms, and source paths
7. Add Cabal Knowledge summary for top analytics findings.
8. Add contract/unit/integration coverage.

## Phase 3: Visual Analytics Polish

1. Add graph legend and lens controls.
2. Add clickable analytics findings that focus the graph.
3. Add search-to-graph behavior so a query can reveal connected skills and agents.
4. Add changed-concept badges when previous-index comparison is available.
5. Keep the generated viewer static/offline.

## Phase 4: RAG Context Packs

1. Implement `context` command and service.
2. Retrieve FTS hits from SQLite.
3. Expand through graph neighbors and route evidence.
4. Emit JSON and human output explaining why each item was included.
5. Reuse context packs for recommendation explanations.

## Phase 5: Semantic Layer

1. Add embedding provider protocol with fake provider tests.
2. Store chunk embeddings with model name and text hash.
3. Add semantic overlap reports.
4. Add semantic retrieval to context packs when provider is configured.
5. Fall back gracefully to FTS when unavailable.

## Phase 6: Optional DuckDB Backend

1. Add export from SQLite/OKF to DuckDB or Parquet.
2. Add historical snapshot analytics.
3. Support notebook-style analysis outside core Cabal runtime.
4. Keep DuckDB optional and not required for default search/RAG.

## Complexity Tracking

No constitution violations expected. The main complexity choice is explicitly deferred: DuckDB and embeddings remain optional until SQLite analytics proves useful.

## Post-Design Constitution Recheck

**Status**: PASS

The plan keeps source of truth in OKF, adds no new global config, adds no new skill/agent, defines contract surfaces, and isolates optional complexity behind later phases.

## Next Command

Run `/speckit-tasks` for `009-okf-analytics-rag` after accepting this plan.
