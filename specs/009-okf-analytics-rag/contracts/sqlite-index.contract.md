# Contract: SQLite OKF Index

## Build Command

```bash
python -m cabal.okf index docs/okf/prompt-lib --db .cabal/okf/index.sqlite
```

Returns exit code `0` when the index is built.

## Required Tables

- `metadata`
- `concepts`
- `edges`
- `chunks`
- `concept_fts`

## Required Behavior

- Rebuilding the index replaces stale rows.
- Index is derived from OKF bundle only.
- Deleting the index and rebuilding produces equivalent analytics results.
- FTS5 availability is detected and reported clearly.

## Search Command

```bash
python -m cabal.okf search .cabal/okf/index.sqlite "pytest fixtures"
```

Returns JSON or human output containing:

- concept id
- type
- title
- resource
- snippet
- score/rank when available
