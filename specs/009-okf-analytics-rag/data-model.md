# Data Model: OKF Analytics and RAG Index

## SQLite Tables

### `metadata`

| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PRIMARY KEY | `schema_version`, `bundle_root`, `generated_at` |
| `value` | TEXT | Metadata value |

### `concepts`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | Concept id from OKF frontmatter |
| `type` | TEXT | agent, skill, hook, rule, tool, spec, etc. |
| `title` | TEXT | Display title |
| `description` | TEXT | Frontmatter description |
| `resource` | TEXT | Repo-relative source path |
| `doc` | TEXT | Bundle-relative document path |
| `tags_json` | TEXT | JSON list |
| `body` | TEXT | Markdown body after frontmatter |
| `body_hash` | TEXT | SHA-256 hash for change detection |

### `edges`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | Graph edge id |
| `source` | TEXT | Source concept id |
| `target` | TEXT NULL | Target concept id when resolved |
| `target_ref` | TEXT | Raw target reference |
| `kind` | TEXT | `routes_to`, etc. |
| `confidence` | TEXT | explicit, structured, inferred |
| `reason` | TEXT | Human reason |
| `evidence_json` | TEXT | JSON evidence records |

### `chunks`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | `<concept_id>:<ordinal>` |
| `concept_id` | TEXT | FK to concepts |
| `ordinal` | INTEGER | Chunk order |
| `text` | TEXT | Chunk content |
| `text_hash` | TEXT | SHA-256 hash |

### `concept_fts`

SQLite FTS5 virtual table over:

- `title`
- `description`
- `resource`
- `tags`
- `body`

### Future `embeddings`

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | TEXT | FK to chunks |
| `model` | TEXT | Embedding model id |
| `text_hash` | TEXT | Ensures embedding matches chunk text |
| `vector` | BLOB/TEXT | Provider-specific vector encoding |

## Analytics Report Shape

```json
{
  "agents_with_many_routes": [],
  "skills_with_many_routes": [],
  "agents_never_referenced": [],
  "skill_graph_overlap": [],
  "skill_text_overlap": [],
  "skills_same_agent_similar_reasons": [],
  "relation_density_by_category": [],
  "changed_concepts": []
}
```

## Context Pack Shape

```json
{
  "query": "Python service architecture",
  "budget": "focused",
  "matches": [],
  "expanded_concepts": [],
  "evidence_edges": [],
  "estimated_tokens": 1500,
  "why": []
}
```

## Preflight Shape

```json
{
  "task": "Add an MCP-backed OKF context pack",
  "scope": "L",
  "risk_flags": ["mcp_protocol", "cabal_ui", "token_heavy"],
  "likely_areas": ["okf", "mcp", "cabal_knowledge"],
  "recommended_budget": "focused",
  "index_state": "fresh",
  "why": []
}
```

Scope tiers:

- `S`: one doc/file, no deploy impact.
- `M`: multiple files or normal localized feature work.
- `L`: Cabal runtime, generated OKF, hook behavior, MCP template, or cross-platform behavior.
- `XL`: protocol surface, global deploy behavior, security hooks, agent routing, or migration-like changes.

## Usage Ledger Entry Shape

Stored as JSON Lines under `.cabal/okf/usage.jsonl`.

```json
{
  "timestamp": "2026-07-01T12:00:00Z",
  "client": "claude",
  "entrypoint": "mcp",
  "action": "okf_context_pack",
  "query_hash": "sha256:...",
  "query_preview": "Python service architecture",
  "budget": "focused",
  "included_concepts": ["skill:orchestrate", "agent:python-architect"],
  "evidence_edge_count": 2,
  "estimated_tokens": 1500,
  "cache_state": "fresh",
  "duration_ms": 42
}
```

The ledger is telemetry, not source of truth. It must avoid storing full prompts by default.

## OKF RAG MCP Tool Surface

The opt-in `okf-rag` MCP server exposes thin adapters over the service layer:

- `okf_prepare`
- `okf_search`
- `okf_preflight`
- `okf_context_pack`
- `okf_analytics`
- `okf_usage`

## Visual Analytics Shape

```json
{
  "lenses": ["route_pressure", "fanout", "overlap", "unused", "changes"],
  "findings": [],
  "node_highlights": [],
  "edge_highlights": []
}
```

Visual analytics data is derived from the analytics report and graph JSON. It is embedded into the static viewer output, not stored as the source of truth.
