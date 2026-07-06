# Quickstart: OKF Analytics and RAG Index

Generate the OKF bundle first:

```bash
python -m cabal.okf export --out docs/okf/prompt-lib
python -m cabal.okf doctor docs/okf/prompt-lib
```

Build the SQLite index:

```bash
python -m cabal.okf index docs/okf/prompt-lib --db .cabal/okf/index.sqlite
```

Run analytics:

```bash
python -m cabal.okf analytics docs/okf/prompt-lib --db .cabal/okf/index.sqlite --format human
python -m cabal.okf analytics docs/okf/prompt-lib --db .cabal/okf/index.sqlite --format json
```

Generate an analytics-aware graph viewer:

```bash
python -m cabal.okf graph --graph docs/okf/prompt-lib/graph.json --db .cabal/okf/index.sqlite --analytics --out docs/okf/prompt-lib/graph.html
```

Search:

```bash
python -m cabal.okf search .cabal/okf/index.sqlite "security review"
```

Build a context pack:

```bash
python -m cabal.okf context .cabal/okf/index.sqlite "Python service architecture" --budget focused --format json
```

Run a small preflight instead of full retrieval:

```bash
python -m cabal.okf preflight .cabal/okf/index.sqlite "Add an MCP-backed OKF context pack" --format json
```

Inspect local usage telemetry:

```bash
python -m cabal.okf usage .cabal/okf/usage.jsonl --format human
python -m cabal.okf usage .cabal/okf/usage.jsonl --format json
```

Register the optional `okf-rag` MCP server:

```bash
# Cabal MCP manager should expose the okf-rag template with default_enabled=false.
# Equivalent shape when registering manually:
claude mcp add okf-rag -- python -m cabal.okf.mcp_server
```

Call the shared MCP tools from Claude/Cursor:

```text
okf_preflight(task="Add an MCP-backed OKF context pack")
okf_context_pack(query="Python service architecture", budget="focused")
okf_usage(limit=10)
```

Compare changes:

```bash
python -m cabal.okf analytics docs/okf/prompt-lib \
  --db .cabal/okf/index.sqlite \
  --previous-db .cabal/okf/previous.sqlite \
  --format json
```

Expected analytics categories:

- agents with many incoming skill routes
- skills with many outgoing routes
- agents never referenced
- skill graph overlap
- skill text overlap
- same-agent/similar-reason route groups
- relation density by category
- changed concepts since previous index

Expected visualization lenses:

- route pressure
- fanout
- overlap
- unused agents
- changed concepts

Expected preflight/usage behavior:

- preflight returns scope tier, risk flags, likely OKF areas, recommended context budget, and index state
- automatic preflight stays small and does not emit full context by default
- context packs write usage ledger entries with client, action, budget, concept ids, token estimate, cache state, and duration
- Cabal Knowledge shows usage across Cabal/Claude/Cursor
- Claude Sessions can flag `okf_*` calls seen in Claude transcripts
