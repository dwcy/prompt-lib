# OKF generated output

## What OKF is

OKF means Open Knowledge Format. In prompt-lib, it is used to turn the repo's agent ecosystem into a portable knowledge catalog that other AI tools, graph viewers, and future RAG/indexing features can read without needing to understand the original folder layout.

The export describes agents, skills, hooks, rules, tools, templates, Codex assets, output styles, and Spec Kit files as concept documents with metadata and graph relations. That makes it easier to answer questions such as which skills route to which agents, where responsibilities overlap, which concepts are unused, and what changed since the last export.

Exporting creates files; it does not automatically load the catalog into Claude, Codex, or other tools. Point prompts, repo instructions, or future indexes at this directory when you want an AI tool to use the catalog.

The current branch provides the OKF bundle, doctor checks, route extraction, graph data, and a static graph viewer. On top of that, prompt-lib now ships a SQLite-backed OKF index with keyword search, preflight scope estimation, budgeted context packs, and a usage ledger, plus embedding-based semantic search once its optional dependency is installed. All of this is reachable from Cabal's Knowledge screen, in the "OKF RAG" panel: `Rebuild Index` (re)builds the SQLite index from the bundle, `Search` runs a raw full-text keyword lookup against the index, `Preflight` estimates likely-relevant concepts and a recommended token budget for a query, `Context` builds a token-budgeted, graph-expanded context pack, `Semantic` runs embedding similarity search when the optional dependency is available, and `Usage` shows the most recent entries from the on-disk usage ledger. The same operations are also available from the `python -m cabal.okf` CLI.

The index only covers the generated OKF concept documents with frontmatter under `docs/okf/prompt-lib/` — the agent, skill, hook, rule, tool, template, Codex, output-style, and Spec Kit concept files produced by export. It does not index arbitrary repository files such as top-level `README.md`s or other prose docs; if a search or context-pack query returns no matches, check whether the concept you expect was actually exported into the bundle before assuming the index is broken.

What is not built yet: an `okf-rag` MCP server. Claude, Codex, Cursor, and other MCP-aware tools cannot call search, preflight, or context-pack building automatically today — only Cabal's own TUI panel and the `cabal.okf` CLI can. Point prompts or repo instructions at the generated bundle directly (as described above) until the MCP server lands.

`docs/okf/prompt-lib/` is generated from prompt-lib source files. Treat it as a portable catalog for other AI tools and visualizers, not as the source of truth.

Edit source files first, then regenerate the bundle:

```bash
python -m cabal.okf export --out docs/okf/prompt-lib
python -m cabal.okf doctor docs/okf/prompt-lib --format human
python -m cabal.okf graph --graph docs/okf/prompt-lib/graph.json --out docs/okf/prompt-lib/graph.html
```

Generated output is safe to delete and recreate. Do not put secrets, local credentials, or private runtime state into source files that will be cataloged.

## What gets generated

- `index.md` and `log.md` reserved OKF documents.
- Concept documents for agents, skills, hooks, rules, tools, templates, Codex assets, output styles, and Spec Kit files.
- `manifest.json` with deterministic generated file listings.
- `graph.json` with nodes, `routes_to` edges, evidence, and backlinks.
- `graph.html` as a static offline viewer.

## Regeneration policy

Generated OKF files may be committed when the graph is useful for review, but fixes should always start in the source files under `global/`, `setup/`, or `specs/`. Regenerate the bundle afterward and run the doctor before pushing.
