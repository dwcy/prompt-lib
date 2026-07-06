# Feature Specification: OKF Analytics and RAG Index

**Feature Branch**: `feat/009-okf-analytics-rag`  
**Created**: 2026-06-18  
**Status**: Draft  
**Input**: User description: "Add SQLite-backed analytics for agents/skills overlap and plan a RAG layer, while keeping DuckDB optional for heavier analytics."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a local OKF search index (Priority: P1)

As the prompt-lib maintainer, I want Cabal to build a local SQLite index from the generated OKF bundle so that concepts, edges, chunks, and full-text search can be queried without reparsing Markdown on every action.

**Why this priority**: All analytics and RAG features need a fast local index. SQLite gives the product a stdlib-first default that matches Cabal's offline local workflow.

**Independent Test**: Generate an OKF bundle from fixtures, build the SQLite index, and verify concepts, edges, chunks, and FTS rows are queryable.

**Acceptance Scenarios**:

1. **Given** `docs/okf/prompt-lib/graph.json` and concept Markdown files exist, **When** the index command runs, **Then** it creates a SQLite database under a local cache path.
2. **Given** a concept document has title, tags, body, and resource metadata, **When** the index is built, **Then** those fields are inserted into `concepts`, `chunks`, and FTS tables.
3. **Given** the graph contains `routes_to` edges with evidence, **When** the index is built, **Then** those edges are queryable by source, target, kind, confidence, reason, and evidence.

---

### User Story 2 - Report agent and skill health analytics (Priority: P1)

As the maintainer, I want Cabal to report graph health signals such as overloaded agents, skills that route too broadly, unused agents, relation density, and changed concepts so that I can keep the ecosystem understandable as it grows.

**Why this priority**: The graph becomes operational only when it can flag drift, duplication, and unhealthy routing patterns.

**Independent Test**: Build the SQLite index from fixture bundles and assert each report category returns deterministic rows.

**Acceptance Scenarios**:

1. **Given** an agent has more than the configured number of incoming skill routes, **When** analytics runs, **Then** it appears under agents with many incoming routes.
2. **Given** a skill routes to more than the configured number of agents, **When** analytics runs, **Then** it appears under skills with many outgoing routes.
3. **Given** an agent has no incoming `routes_to` edges, **When** analytics runs, **Then** it appears under agents never referenced.
4. **Given** a previous index is supplied, **When** concept body hashes differ, **Then** analytics reports changed concept ids.

---

### User Story 3 - Detect overlapping skills (Priority: P1)

As the maintainer, I want to detect duplicate or overlapping skills through graph overlap, text overlap, and later semantic overlap so that similar commands such as review/audit/code-review do not silently fragment the ecosystem.

**Why this priority**: Skill sprawl is one of the biggest risks for prompt-lib. Overlap detection protects discoverability and routing quality.

**Independent Test**: Use fixture skills that share target agents, tags, and vocabulary, then verify graph-overlap and FTS/text-overlap reports identify the pair with evidence.

**Acceptance Scenarios**:

1. **Given** two skills route to the same target agents, **When** graph overlap runs, **Then** the shared agents and skill ids are reported.
2. **Given** two skills share important terms or tags, **When** text overlap runs, **Then** the shared terms and score are reported.
3. **Given** several skills point to the same specialist for similar reasons, **When** analytics runs, **Then** the shared agent and reason group are reported.

---

### User Story 4 - Visualize analytics on the OKF graph (Priority: P2)

As the maintainer, I want the OKF graph viewer to show analytics lenses for overload, fanout, overlap, unused agents, and changed concepts so that I can visually understand how the ecosystem is connected and where it is drifting.

**Why this priority**: The skill-agent graph is the killer feature. Analytics must become visible and explorable, not just a JSON report.

**Independent Test**: Build an index and analytics report from fixture bundles, render the graph viewer with analytics data, and verify the viewer exposes lens controls, highlighted findings, and evidence drill-down data.

**Acceptance Scenarios**:

1. **Given** analytics has overloaded agents and broad skills, **When** the viewer renders, **Then** route-pressure and fanout lenses can highlight the affected nodes.
2. **Given** analytics has overlapping skills, **When** the overlap lens is selected, **Then** the viewer exposes the shared target agents, shared terms, and evidence for the selected overlap.
3. **Given** a previous index identifies changed concepts, **When** the changes lens is selected, **Then** changed concepts appear with source paths and hashes available for inspection.

---

### User Story 5 - Build graph-backed context packs (Priority: P2)

As a future agent or Cabal user, I want a query to return a context pack that combines FTS hits, graph expansion, and evidence lines so that an agent can read the most relevant OKF knowledge with an explanation for why it was included.

**Why this priority**: This is the practical RAG step. It turns analytics into reusable context without requiring embeddings on day one.

**Independent Test**: Query the index with a task phrase and verify the context pack includes matching concepts, expanded neighbor concepts, route evidence, and source paths.

**Acceptance Scenarios**:

1. **Given** a query matches a skill, **When** context pack generation runs, **Then** it includes that skill and its routed agents.
2. **Given** a route edge has evidence, **When** context pack output is rendered, **Then** it includes the evidence path and line.
3. **Given** no embedding provider is configured, **When** context pack generation runs, **Then** it still works using SQLite FTS and graph expansion.

---

### User Story 6 - Use OKF RAG from Claude and Cursor with visible usage (Priority: P2)

As the Cabal user, I want Claude and Cursor to use the same local OKF retrieval surface, and I want Cabal to show me when it was used, what it included, and roughly how many tokens it emitted, so that token optimization and scope control are observable rather than invisible magic.

**Why this priority**: Context packs are only useful operationally if the AI clients can call them and the maintainer can verify adoption. Claude and Cursor should not need separate retrieval implementations.

**Independent Test**: Register an opt-in `okf-rag` MCP template against a fixture server, call `okf_context_pack`, and verify Cabal records a usage ledger entry with client, budget, concepts, evidence count, token estimate, cache state, and duration.

**Acceptance Scenarios**:

1. **Given** Claude or Cursor is configured with the `okf-rag` MCP server, **When** the client calls `okf_context_pack`, **Then** the server returns the same context-pack shape as the CLI and writes a local usage-ledger entry.
2. **Given** Cabal opens the OKF Knowledge area, **When** usage entries exist, **Then** Cabal shows recent calls by client, action, budget, included concepts, token estimate, and cache state.
3. **Given** a Claude Code session used an `okf_*` MCP tool, **When** the Sessions screen parses the transcript, **Then** Cabal can cross-link that session activity to the OKF usage entry or show a Claude transcript match.
4. **Given** the user asks for automatic behavior, **When** Cabal preflight runs, **Then** it emits only a small scope/complexity card and recommended context budget unless the user explicitly asks for a context pack.

---

### User Story 7 - Add semantic overlap later (Priority: P3)

As the maintainer, I want an optional semantic layer for overlap and RAG so that skills with different wording but similar intent can be found when FTS is not enough.

**Why this priority**: Semantic search is valuable, but it should be optional and provider-backed after deterministic graph/text analytics prove useful.

**Independent Test**: With a fake embedding provider, index chunk embeddings and verify semantic overlap can be computed without changing the SQLite default path.

**Acceptance Scenarios**:

1. **Given** an embedding provider is configured, **When** embedding indexing runs, **Then** chunk embeddings are stored with model and text hash metadata.
2. **Given** two skills are semantically similar but share few words, **When** semantic overlap runs, **Then** they appear with a semantic score and cited chunks.
3. **Given** no provider is configured, **When** semantic features are requested, **Then** Cabal explains that semantic indexing is unavailable and falls back to FTS.

## Edge Cases

- SQLite builds may lack FTS5; the implementation must detect this and report a clear fallback or error.
- Generated OKF may include hundreds of concept docs; index rebuild must remain fast and deterministic.
- Binary SQLite index files must not become source of truth or be required in commits.
- DuckDB should not become a default dependency for Cabal.
- Semantic embeddings must not leak secrets; use the same redaction policy as OKF export.
- Analytics thresholds must be configurable so small fixture catalogs and the real repo can both be tested.
- Usage telemetry must avoid storing full prompts by default; store a redacted preview plus a hash.
- Claude transcript parsing can verify Claude usage, but Cursor usage must rely on the local OKF usage ledger.
- Client-launched stdio MCP servers should not appear as runnable daemons in Local Agent Services unless they later become long-running services.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST build a SQLite index from an existing OKF bundle, not from unrelated source files.
- **FR-002**: SQLite MUST be the default runtime search and analytics backend.
- **FR-003**: Index storage MUST be local generated cache, with OKF files remaining the source of truth.
- **FR-004**: Index MUST store concepts, edges, chunks, metadata, and FTS rows.
- **FR-005**: Analytics MUST report agents with too many incoming skill routes.
- **FR-006**: Analytics MUST report skills that route to too many agents.
- **FR-007**: Analytics MUST report agents never referenced by skills.
- **FR-008**: Analytics MUST report duplicate or overlapping skills through graph overlap.
- **FR-009**: Analytics MUST report text overlap using SQLite FTS/token analysis.
- **FR-010**: Analytics MUST report skills that mention the same agent for similar reasons.
- **FR-011**: Analytics MUST report relation density by concept category.
- **FR-012**: Analytics MUST report concepts changed since a previous index when provided.
- **FR-013**: Context packs MUST combine FTS hits with graph expansion and route evidence.
- **FR-014**: Semantic overlap MUST be optional and behind an embedding provider interface.
- **FR-015**: DuckDB MAY be added later as an optional analytics/export backend, but MUST NOT be required for core Cabal analytics.
- **FR-016**: Cabal Knowledge UI MUST surface the highest-priority analytics findings without blocking the Textual event loop.
- **FR-017**: Graph viewer MUST support analytics lenses for route pressure, fanout, overlap, unused agents, and changed concepts.
- **FR-018**: Graph viewer MUST allow a selected analytics finding to reveal affected nodes, affected edges, and evidence.
- **FR-019**: Graph visualization MUST remain static/offline and must not require a database server.
- **FR-020**: Cabal MUST provide a preflight result that classifies task scope/complexity, risk flags, likely OKF areas, and recommended context budget without emitting a full context pack by default.
- **FR-021**: System MUST expose context-pack retrieval through an opt-in `okf-rag` MCP server so Claude, Cursor, and other MCP clients can share one retrieval contract.
- **FR-022**: The `okf-rag` MCP server MUST be registered through Cabal MCP tooling / `setup/mcp-templates.json` and MUST NOT be enabled by default.
- **FR-023**: CLI, preflight, and MCP retrieval paths MUST write a local usage-ledger entry containing client, entrypoint, action, budget, included concepts, evidence count, token estimate, cache state, and duration.
- **FR-024**: Cabal Knowledge UI MUST show index freshness, preflight output, context-pack inspection, and cross-client OKF usage history.
- **FR-025**: Claude Sessions UI SHOULD detect `okf_*` tool calls in Claude transcripts and link or annotate them against OKF usage when possible.
- **FR-026**: `okf-rag` MUST be treated as a client-launched MCP server, not a Local Agent Services daemon, unless a future design changes it into a long-running service.
- **FR-027**: Automatic behavior MUST stay bounded to cache freshness and small preflight summaries; full retrieval MUST require an explicit context-pack action or MCP tool call.

### Key Entities

- **SQLite OKF Index**: Local generated database derived from the OKF bundle.
- **Concept Row**: Indexed concept metadata and body hash.
- **Edge Row**: Indexed graph relation with evidence JSON.
- **Chunk Row**: Searchable text segment derived from a concept body.
- **Analytics Report**: Deterministic health summary over concepts, edges, chunks, and optional previous index.
- **Overlap Finding**: Evidence-backed graph, text, or semantic similarity between skills.
- **Analytics Lens**: Viewer mode that maps report findings onto graph nodes and edges.
- **Context Pack**: Retrieved concepts, graph neighbors, evidence lines, and inclusion reasons for a query.
- **Preflight Card**: Small task-scope summary with complexity tier, risk flags, likely OKF areas, and recommended context budget.
- **OKF RAG MCP Server**: Client-launched stdio server exposing prepare/search/context/analytics/preflight/usage tools over MCP.
- **Usage Ledger Entry**: Local append-only record proving a CLI, preflight, or MCP retrieval action ran and what it emitted.
- **Client Registration State**: Cabal-visible status showing whether Claude and Cursor are configured to use `okf-rag`.
- **Embedding Record**: Optional future vector for a chunk with model and text hash provenance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Index rebuild over the current generated OKF bundle completes locally in under 10 seconds.
- **SC-002**: Analytics report returns all required categories with stable JSON shape.
- **SC-003**: Fixture tests cover route pressure, fanout, unused agents, graph overlap, text overlap, and changed concepts.
- **SC-004**: Context pack output cites at least one concept and one evidence-backed graph edge for a matching skill-agent route.
- **SC-005**: Cabal Knowledge screen can display analytics summary without blocking UI.
- **SC-006**: No generated SQLite index is treated as source of truth; deleting it and rebuilding produces equivalent report results.
- **SC-007**: Graph viewer can highlight at least one analytics finding and display its evidence in the inspector.
- **SC-008**: Preflight returns a deterministic scope tier and recommended context budget for fixture task descriptions.
- **SC-009**: MCP `okf_context_pack` returns the same required context-pack JSON shape as the CLI path.
- **SC-010**: Cabal can show at least one usage-ledger entry from Claude/Cursor/Cabal with included concept ids and token estimate.

## Assumptions

- OKF bundle generation from feature 008 remains available and valid.
- Python's stdlib `sqlite3` is available on supported platforms.
- SQLite FTS5 is available in the normal runtime; implementation will detect and report if not.
- DuckDB is useful later for heavy analytics, historical snapshots, and notebook-style exploration, but not for the default product path.
- Embeddings/RAG are incremental, not required for the first analytics release.
- Claude and Cursor can both consume MCP servers, but Cabal should still own setup/status/usage visibility instead of duplicating client-specific retrieval logic.
