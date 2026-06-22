# Quickstart: OKF Knowledge Graph

This feature is implemented as a local, stdlib-first OKF exporter, doctor, graph viewer, and recommendation helper.

## Goal

Generate a portable OKF bundle from prompt-lib and validate it:

```text
docs/okf/prompt-lib/
|-- index.md
|-- log.md
|-- manifest.json
|-- graph.json
|-- agents/
|-- skills/
|-- hooks/
|-- rules/
|-- tools/
`-- specs/
```

## MVP Workflow

From the repo root:

```bash
python -m cabal.okf export --out docs/okf/prompt-lib
python -m cabal.okf doctor docs/okf/prompt-lib --format human
python -m cabal.okf doctor docs/okf/prompt-lib --format json
```

Expected success summary:

```text
OKF doctor passed
documents: <count>
relations: <count>
errors: 0
warnings: 0
```

## Skill-Agent Graph Check

After export, inspect `docs/okf/prompt-lib/graph.json`.

Look for `routes_to` edges:

```json
{
  "source": "skill:orchestrate",
  "target": "agent:python-architect",
  "kind": "routes_to",
  "confidence": "explicit",
  "reason": "Skill routes Python architecture tasks to python-architect."
}
```

The matching agent document should include a backlink section that names the skills routing to it.

## Cabal Integration Target

Beyond MVP, Cabal should expose a Knowledge screen:

```bash
python setup/settings-configurator-ui.py
```

Expected capabilities:

- Run OKF export.
- Run OKF doctor.
- Show concept and relation counts.
- Show top routed agents.
- Open graph visualization or display a graph status panel.

## Static Visualization Target

Generate a static graph explorer:

```bash
python -m cabal.okf graph --graph docs/okf/prompt-lib/graph.json --out docs/okf/prompt-lib/graph.html
```

The visualizer must consume `graph.json`; it must not parse Markdown independently.

## Recommendation Target

Ask for graph-backed recommendations:

```bash
python -m cabal.okf recommend docs/okf/prompt-lib/graph.json "Python service architecture"
```

Recommendations are advisory. They cite `routes_to` graph evidence and do not invoke agents or mutate configuration.

## Development Validation

Before implementation is accepted:

```bash
pytest tests/contract/test_okf_bundle_contract.py
pytest tests/contract/test_okf_doctor_contract.py
pytest tests/contract/test_okf_graph_contract.py
pytest tests/unit/test_okf_exporter.py tests/unit/test_okf_relations.py tests/unit/test_okf_doctor.py
pytest tests/unit/test_okf_recommendations.py tests/unit/test_okf_security.py
```

If a Cabal UI slice is included:

```bash
pytest tests/integration/test_okf_cabal_ui.py
pytest tests/integration/test_okf_graph_viewer.py
pytest tests/integration/test_okf_recommendations_cli.py
```

## Source-of-Truth Rule

Edit prompt-lib source files first:

- `global/agents/*.md`
- `global/skills/*.md`
- `global/hooks/**`
- `global/rules/**`
- `setup/src/cabal/**`
- `specs/**`

Then regenerate OKF. Do not hand-edit generated OKF files as the canonical fix.
