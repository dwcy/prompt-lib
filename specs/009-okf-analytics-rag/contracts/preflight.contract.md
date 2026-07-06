# Contract: OKF Preflight

## Command

```bash
python -m cabal.okf preflight .cabal/okf/index.sqlite "Add an MCP-backed OKF context pack" --format json
```

## Required JSON Shape

```json
{
  "task": "Add an MCP-backed OKF context pack",
  "scope": "L",
  "risk_flags": [],
  "likely_areas": [],
  "recommended_budget": "focused",
  "index_state": "fresh",
  "why": []
}
```

## Requirements

- `scope` is one of `S`, `M`, `L`, `XL`.
- `recommended_budget` is one of `tiny`, `focused`, `full`.
- Automatic preflight emits the small card only; it must not include full concept bodies.
- `why` explains the scope/risk/budget decision with short evidence strings.
- Missing or stale index state is reported clearly and does not crash Cabal.
