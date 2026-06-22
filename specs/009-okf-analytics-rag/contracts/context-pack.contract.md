# Contract: Context Pack

## Command

```bash
python -m cabal.okf context .cabal/okf/index.sqlite "Python service architecture" --format json
```

## Required JSON Shape

```json
{
  "query": "Python service architecture",
  "matches": [],
  "expanded_concepts": [],
  "evidence_edges": [],
  "why": []
}
```

## Requirements

- FTS matches are included first.
- Graph neighbors are added by following relevant edges.
- `routes_to` evidence includes resource path and line when available.
- Output explains why each concept/edge was included.
- Embeddings are optional and must not be required for a valid context pack.
