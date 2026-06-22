# Contract: Graph JSON Snapshot

This contract defines `docs/okf/prompt-lib/graph.json`.

## Top-Level Shape

```json
{
  "schema_version": "1",
  "bundle_id": "prompt-lib",
  "generated_at": "2026-06-18T00:00:00Z",
  "nodes": [],
  "edges": [],
  "counts": {
    "nodes_by_type": {},
    "edges_by_kind": {},
    "findings_by_severity": {}
  },
  "findings": []
}
```

All object keys MUST be written in deterministic order.

## Node Shape

```json
{
  "id": "agent:python-architect",
  "label": "python-architect",
  "type": "agent",
  "resource": "global/agents/python-architect.md",
  "doc": "agents/python-architect.md",
  "tags": ["prompt-lib", "agent", "claude-code"],
  "metrics": {
    "incoming": 3,
    "outgoing": 1,
    "warnings": 0,
    "errors": 0
  }
}
```

Required node fields:

| Field | Type |
|---|---|
| `id` | string |
| `label` | string |
| `type` | string |
| `resource` | string |
| `doc` | string |
| `tags` | string[] |
| `metrics` | object |

## Edge Shape

```json
{
  "id": "edge:skill:orchestrate:routes_to:agent:python-architect:abc123",
  "source": "skill:orchestrate",
  "target": "agent:python-architect",
  "target_ref": "@python-architect",
  "kind": "routes_to",
  "confidence": "explicit",
  "reason": "Skill routes Python architecture tasks to python-architect.",
  "evidence": [
    {
      "resource": "global/skills/orchestrate.md",
      "line": 42,
      "text": "@python-architect",
      "extractor": "agent_token"
    }
  ]
}
```

Required edge fields:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable relation id |
| `source` | string | Existing node id |
| `target` | string/null | Existing node id when resolved |
| `target_ref` | string | Raw target reference |
| `kind` | string | Relation kind |
| `confidence` | string | `explicit`, `structured`, or `inferred` |
| `reason` | string | Human explanation |
| `evidence` | object[] | One or more evidence records |

## Counts

`counts.nodes_by_type` MUST count every node by `type`.

`counts.edges_by_kind` MUST count every edge by `kind`.

`counts.findings_by_severity` MUST count every doctor finding included in the graph snapshot.

## Findings Overlay

Findings use the same shape as the OKF doctor contract and may reference `concept_id` or `relation_id`.

Visualizers MAY use findings to style nodes and edges, but the graph contract MUST remain useful without layout-specific data.

## Ordering

- Nodes sorted by `type`, then `id`.
- Edges sorted by `kind`, then `source`, then `target_ref`, then `id`.
- Findings sorted by `severity`, then `code`, then `resource`, then `message`.

## MVP Relation Kinds

MVP MUST support:

- `routes_to`: skill or routing artifact selects an agent.
- `references`: source artifact links to or names another concept.

Beyond MVP MAY add:

- `depends_on`
- `documents`
- `configured_by`
- `deploys`
- `extends`
- `uses`

## Visualization Requirements

Any visualizer built beyond MVP MUST:

- Consume this JSON file rather than reparsing Markdown.
- Support filtering by node `type`.
- Support filtering by edge `kind`.
- Show `reason` and `evidence` for selected edges.
- Treat `target: null` edges as unresolved rather than dropping them silently.
