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
python -m cabal.okf context .cabal/okf/index.sqlite "Python service architecture" --format json
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
