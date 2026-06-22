# OKF generated output

## What OKF is

OKF means Open Knowledge Format. In prompt-lib, it is used to turn the repo's agent ecosystem into a portable knowledge catalog that other AI tools, graph viewers, and future RAG/indexing features can read without needing to understand the original folder layout.

The export describes agents, skills, hooks, rules, tools, templates, Codex assets, output styles, and Spec Kit files as concept documents with metadata and graph relations. That makes it easier to answer questions such as which skills route to which agents, where responsibilities overlap, which concepts are unused, and what changed since the last export.

Exporting creates files; it does not automatically load the catalog into Claude, Codex, or other tools. Point prompts, repo instructions, or future indexes at this directory when you want an AI tool to use the catalog.

The current branch provides the OKF bundle, doctor checks, route extraction, graph data, a static graph viewer, and the Cabal Knowledge screen. The next analytics/RAG work builds on this by adding SQLite-backed search, overlap reports, graph lenses, context packs, and optional semantic retrieval.

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
