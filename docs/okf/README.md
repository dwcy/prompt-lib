# OKF generated output

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
