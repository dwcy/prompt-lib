# Contract: Visual Analytics Graph

## Command

```bash
python -m cabal.okf graph --graph docs/okf/prompt-lib/graph.json --db .cabal/okf/index.sqlite --analytics --out docs/okf/prompt-lib/graph.html
```

## Required Behavior

- Output is a static HTML file that works offline.
- Viewer embeds graph data and analytics data as valid JSON script payloads.
- Viewer exposes lenses for route pressure, fanout, overlap, unused agents, and changed concepts.
- Selecting a finding highlights affected nodes and edges.
- Inspector shows evidence such as shared agents, shared terms, route reasons, source paths, and line numbers when available.
- Viewer still works when analytics data is missing; analytics lenses are disabled with a clear unavailable state.
