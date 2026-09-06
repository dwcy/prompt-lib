# OKF generated output

## What OKF is

OKF means Open Knowledge Format. In prompt-lib, it is used to turn the repo's agent ecosystem into a portable knowledge catalog that other AI tools, graph viewers, and future RAG/indexing features can read without needing to understand the original folder layout.

The export describes agents, skills, hooks, rules, tools, templates, Codex assets, output styles, and Spec Kit files as concept documents with metadata and graph relations. That makes it easier to answer questions such as which skills route to which agents, where responsibilities overlap, which concepts are unused, and what changed since the last export.

Exporting creates files; it does not automatically load the catalog into Claude, Codex, or other tools. Point prompts, repo instructions, or future indexes at this directory when you want an AI tool to use the catalog.

The current branch provides the OKF bundle, doctor checks, route extraction, graph data, and a static graph viewer. On top of that, prompt-lib now ships a SQLite-backed OKF index with keyword search, preflight scope estimation, budgeted context packs, and a usage ledger, plus embedding-based semantic search once its optional dependency is installed. All of this is reachable from Cabal's Knowledge screen, in the "OKF RAG" panel: `Rebuild Index` (re)builds the SQLite index from the bundle, `Search` runs a raw full-text keyword lookup against the index, `Preflight` estimates likely-relevant concepts and a recommended token budget for a query, `Context` builds a token-budgeted, graph-expanded context pack, `Semantic` runs embedding similarity search when the optional dependency is available, and `Usage` shows the most recent entries from the on-disk usage ledger. The same operations are also available from the `python -m cabal.okf` CLI.

The index only covers the generated OKF concept documents with frontmatter under `docs/okf/prompt-lib/` — the agent, skill, hook, rule, tool, template, Codex, output-style, and Spec Kit concept files produced by export. It does not index arbitrary repository files such as top-level `README.md`s or other prose docs; if a search or context-pack query returns no matches, check whether the concept you expect was actually exported into the bundle before assuming the index is broken.

The same operations are also exposed to MCP-aware tools (Claude Code, Cursor, Codex) through the `okf-rag` stdio MCP server (`setup/src/cabal/okf/mcp_server.py`, console script `cabal-okf-rag`). It serves eight tools: `okf_search` (hybrid FTS + semantic, fused with reciprocal rank fusion, compact rows only), `okf_get` (full concept bodies for chosen ids), `okf_preflight`, `okf_context_pack`, `okf_analytics`, `okf_usage`, `okf_status` (index freshness and capability report), and `okf_prepare` (idempotent bundle-export + index rebuild keyed on the content fingerprint). Every search/context response carries an `index_state` field and a staleness warning when source files changed after the last export, so a stale index reports itself instead of silently returning old text. Registration is opt-in via the `okf-rag` entry in `setup/mcp-templates.json` — enable it from Cabal's MCP screen, or manually: `claude mcp add -s user okf-rag -- cabal-okf-rag` (the `cabal-okf-rag` script must be on PATH, e.g. via `uv tool install .`; from a dev checkout use the venv's `.venv/Scripts/cabal-okf-rag.exe`). The bundle location can be overridden with the `OKF_BUNDLE_ROOT` environment variable.

`docs/okf/prompt-lib/` is generated from prompt-lib source files. Treat it as a portable catalog for other AI tools and visualizers, not as the source of truth.

Edit source files first, then regenerate the bundle:

```bash
python -m cabal.okf export --out docs/okf/prompt-lib
python -m cabal.okf doctor docs/okf/prompt-lib --format human
python -m cabal.okf graph --graph docs/okf/prompt-lib/graph.json --out docs/okf/prompt-lib/graph.html
```

Generated output is safe to delete and recreate. Do not put secrets, local credentials, or private runtime state into source files that will be cataloged.

## Retrieval scope and scaling limits

The semantic search layer is tuned for what the bundle actually contains: short, English, prose-style concept documents — agent and skill descriptions, hook and rule summaries, template metadata. The embedding model is `BAAI/bge-small-en-v1.5` (384 dimensions, English-only, 512-token input window), and the indexer chunks documents into ~900-character paragraph-aware pieces (`setup/src/cabal/okf/index.py`), which fits comfortably inside that window. For this material, retrieval quality is good and no external vector database would improve it.

Two known ceilings apply if the corpus ever grows beyond concept documents:

1. **Embedding model before database.** `bge-small-en-v1.5` degrades on source code and long technical documents. If the index is ever extended to cover code or large spec trees, upgrade the embedding model first — e.g. `nomic-embed-text-v1.5` (8k-token context, still runs locally via fastembed) — before touching the storage layer. `semantic.py` caches vectors per `(text_hash, model)`, so a model swap re-embeds cleanly without schema changes.
2. **Brute-force similarity search.** Semantic search computes cosine similarity in Python across all cached vectors. This is instant at the current scale (hundreds of chunks) and stays fine up to roughly tens of thousands of chunks. Past that, the intended fix is the `sqlite-vec` extension — same SQLite file, proper vector indexing, small code change — not a migration to a vector database service.

Hosted vector databases (Pinecone and similar) are deliberately out of scope: the catalog is personal configuration data, and a corpus this size gains nothing from an external service. SQLite remains the storage layer at every stage of the growth path above.

## What gets generated

- `index.md` and `log.md` reserved OKF documents.
- Concept documents for agents, skills, hooks, rules, tools, templates, Codex assets, output styles, and Spec Kit files.
- `manifest.json` with deterministic generated file listings.
- `graph.json` with nodes, `routes_to` edges, evidence, and backlinks.
- `graph.html` as a static offline viewer.

## Regeneration policy

Generated OKF files may be committed when the graph is useful for review, but fixes should always start in the source files under `global/`, `setup/`, or `specs/`. Regenerate the bundle afterward and run the doctor before pushing.
