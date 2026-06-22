# Research: OKF Analytics and RAG Index

**Feature**: 009-okf-analytics-rag  
**Date**: 2026-06-18

## R1 - SQLite or DuckDB?

**Decision**: SQLite is the default runtime index; DuckDB is optional later.

**Rationale**:

- SQLite is included with Python and keeps Cabal stdlib-first.
- SQLite FTS5 is a direct fit for local concept/chunk search.
- The workload is app-like: rebuild cache, query concepts, query edges, compare previous index.
- DuckDB is better for OLAP-style analytics, historical snapshots, Parquet/Arrow workflows, and notebook exploration.

**Alternatives considered**:

- *DuckDB default*: rejected for MVP because it adds a dependency and optimizes for heavier analytics than the default product path needs.
- *No database*: rejected because repeated Markdown/JSON parsing will limit search, analytics, and context-pack ergonomics.

## R2 - What is the first RAG deliverable?

**Decision**: Context packs, not embeddings.

**Rationale**:

- FTS + graph expansion already answers many practical questions.
- Context packs can cite concept docs and edge evidence deterministically.
- Embeddings add provider, privacy, caching, and model-version concerns.

**Alternatives considered**:

- *Start with embeddings*: deferred until deterministic analytics proves useful.
- *Only analytics, no retrieval*: rejected because the index should serve both maintainers and agents.

## R3 - How should overlap detection work?

**Decision**: Layered overlap detection.

1. Graph overlap: shared target agents and route patterns.
2. Text overlap: FTS/token similarity over skill bodies, tags, and titles.
3. Semantic overlap: optional embeddings later.

**Rationale**:

- Graph overlap is explainable and low-noise.
- Text overlap catches duplicated vocabulary and near-duplicate skills.
- Semantic overlap catches same-intent/different-wording cases, but needs more machinery.

## R4 - Where should the SQLite file live?

**Decision**: Generated local cache, default `.cabal/okf/index.sqlite`.

**Rationale**:

- Binary database should not be canonical source.
- User can delete and rebuild it from OKF.
- Keeping it outside `docs/okf/prompt-lib/` avoids accidental publishing.

**Alternative considered**:

- *Store under `docs/okf/prompt-lib/index.sqlite`*: rejected because docs are generated/publishable artifacts and SQLite is a local cache.

## R5 - How should changed concepts be detected?

**Decision**: Store body/content hashes per concept and compare with a previous index.

**Rationale**:

- Hash comparison is deterministic and cheap.
- It does not require git.
- It works for generated OKF snapshots from different times.

## R6 - What does DuckDB add later?

**Decision**: DuckDB can be a separate analytics/export backend.

**Rationale**:

- It is useful for historical trend analysis, joining OKF with usage logs, token stats, and run histories.
- It supports a notebook-style exploratory workflow better than SQLite.
- It should not sit on the critical path for Cabal search/health checks.
