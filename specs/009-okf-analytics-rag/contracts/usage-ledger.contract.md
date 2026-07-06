# Contract: OKF Usage Ledger

## File

```text
.cabal/okf/usage.jsonl
```

## Required JSONL Entry Shape

```json
{
  "timestamp": "2026-07-01T12:00:00Z",
  "client": "claude",
  "entrypoint": "mcp",
  "action": "okf_context_pack",
  "query_hash": "sha256:...",
  "query_preview": "Python service architecture",
  "budget": "focused",
  "included_concepts": [],
  "evidence_edge_count": 0,
  "estimated_tokens": 0,
  "cache_state": "fresh",
  "duration_ms": 0
}
```

## Requirements

- Ledger writes are append-only.
- Full prompts are not stored by default; store a short redacted preview plus a stable hash.
- `client` is one of `cabal`, `claude`, `cursor`, or `unknown`.
- `entrypoint` is one of `cli`, `preflight`, `mcp`, or `ui`.
- `budget` is one of `tiny`, `focused`, `full`, or `none`.
- Cabal can read malformed/missing ledger files without crashing.
