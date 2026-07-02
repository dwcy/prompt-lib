# Contract: Context Pack

## Command

```bash
python -m cabal.okf context .cabal/okf/index.sqlite "Python service architecture" --budget focused --format json
```

## Required JSON Shape

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

## Requirements

- FTS matches are included first.
- Graph neighbors are added by following relevant edges.
- `routes_to` evidence includes resource path and line when available.
- Output explains why each concept/edge was included.
- `budget` is one of `tiny`, `focused`, or `full`.
- Output includes an estimated token count so Cabal can show token impact.
- Generating a context pack writes a usage ledger entry unless disabled by an explicit test-only option.
- Embeddings are optional and must not be required for a valid context pack.
