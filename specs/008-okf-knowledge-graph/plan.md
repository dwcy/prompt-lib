# Implementation Plan: OKF Knowledge Graph

**Branch**: `008-okf-knowledge-graph` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md) | **Status**: Draft

## Summary

Build an Open Knowledge Format export and validation layer for prompt-lib, with the skill-agent reference graph as the first-class MVP value. The OKF bundle is generated from existing source files and lives under `docs/okf/prompt-lib/`; it does not replace `global/agents`, `global/skills`, `CLAUDE.md`, Spec Kit artifacts, or Cabal source as the canonical data.

MVP delivers:

- Deterministic OKF Markdown export for repo concepts.
- Doctor validation for generated documents, resources, and relations.
- Explicit `routes_to` relations from skills to agents, including evidence and backlinks.
- A graph JSON snapshot contract for future visualization and recommendations.

Beyond MVP adds:

- Static or Cabal-native graph visualization.
- Recommendation explanations backed by graph edges.
- Wider relation extraction for hooks, rules, specs, tools, MCP servers, and project templates.
- Optional OKF import/merge and MCP/search consumption after the generated catalog proves reliable.

## Technical Context

**Language/Version**: Python 3.11+ for Cabal and setup tooling  
**Primary Dependencies**: Existing stdlib-first Cabal code, pytest, Textual for UI integration  
**Storage**: Generated files under `docs/okf/prompt-lib/`; no database for MVP  
**Testing**: pytest unit, contract, and integration tests; Textual `run_test()` only for UI slices  
**Target Platform**: Windows, Linux, and macOS local checkouts  
**Project Type**: Python Textual TUI plus repository configuration library  
**Performance Goals**: Full export and doctor under 5 seconds on the current repo  
**Constraints**: Offline by default, deterministic output, no secret values, no runtime service, no source-of-truth migration  
**Scale/Scope**: Current repo artifact set: agents, skills, hooks, rules, output styles, project templates, Codex assets, setup tools, and Spec Kit features

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate 1 - Spec-First Conformance

**Status**: PASS

- Feature spec exists at [spec.md](./spec.md).
- The feature distinguishes MVP from beyond-MVP scope and avoids implementation-only goals.
- External standard conformance is scoped to generated OKF v0.1-compatible Markdown and tolerant relation extensions. The plan does not claim a complete OKF runtime.

### Gate 2 - Subagent Delegation

**Status**: PASS

Delegation is explicit in the Subagent Delegation section. Python implementation, tests, UI styling, docs, and verification have separate owners where useful. Parallel write tasks are limited to non-overlapping paths.

### Gate 3 - Contract Tests Before Implementation

**Status**: PASS

Contract artifacts are defined before code:

- [contracts/okf-bundle.contract.md](./contracts/okf-bundle.contract.md)
- [contracts/okf-doctor.contract.md](./contracts/okf-doctor.contract.md)
- [contracts/graph-json.contract.md](./contracts/graph-json.contract.md)

Implementation tasks must add failing contract tests for these surfaces before exporter, doctor, graph, or UI code lands.

### Gate 4 - Reversible Config Changes

**Status**: PASS

MVP does not deploy or mutate `~/.claude/`, user settings, MCP registration, or global runtime config. The generated `docs/okf/prompt-lib/` bundle is deletable and reproducible.

### Gate 5 - Minimal Skill & Agent Surface

**Status**: PASS

MVP adds no new agent and no new slash skill. It catalogs existing assets. A future skill can consume OKF only after the graph contract stabilizes.

### Gate 6 - Parallel Isolation

**Status**: PASS

Planned parallel work has isolated paths:

- Exporter/doctor service code under `setup/src/cabal/okf/`
- Textual UI integration under `setup/src/cabal/views/` and optional Textual CSS
- Tests under `tests/contract/`, `tests/unit/`, and `tests/integration/`
- Generated documentation under `docs/okf/prompt-lib/`

## Project Structure

### Documentation and Planning

```text
specs/008-okf-knowledge-graph/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
`-- contracts/
    |-- okf-bundle.contract.md
    |-- okf-doctor.contract.md
    `-- graph-json.contract.md
```

### Target Implementation Layout

```text
setup/src/cabal/
|-- okf/
|   |-- __init__.py
|   |-- exporter.py          # source discovery and OKF document generation
|   |-- frontmatter.py       # deterministic YAML subset writer/parser
|   |-- graph.py             # node/edge snapshot builder
|   |-- relations.py         # skill-agent and general relation extraction
|   |-- doctor.py            # validation and findings
|   `-- models.py            # dataclasses / typed dicts
|-- views/
|   `-- knowledge.py         # beyond-MVP Cabal graph/status screen
`-- widgets/
    `-- okf_panel.py         # optional home/status widget

tests/
|-- contract/
|   |-- test_okf_bundle_contract.py
|   |-- test_okf_doctor_contract.py
|   `-- test_okf_graph_contract.py
|-- unit/
|   |-- test_okf_exporter.py
|   |-- test_okf_relations.py
|   `-- test_okf_doctor.py
`-- integration/
    `-- test_okf_cabal_ui.py

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
|-- specs/
`-- templates/
```

**Structure Decision**: Place implementation in `setup/src/cabal/okf/` as a small service package that the TUI can call, but keep MVP usable from tests and future command wrappers without requiring a Textual screen.

## Phase 0: Research

Resolved in [research.md](./research.md):

- OKF should be generated derivative metadata, not a source-of-truth replacement.
- MVP should not add PyYAML; emit a deterministic YAML subset and validate the generated subset. Revisit a real YAML parser only for import/round-trip features.
- `docs/okf/prompt-lib/` is the default bundle root because it is documentation-facing and outside deployable `global/` config.
- Skill-agent extraction should start with explicit `@agent` references and routing tables; weak semantic inference belongs beyond MVP.
- Graph JSON should be the visualization contract before any static HTML or Cabal-native graph UI.

## Phase 1: Design and Contracts

Generated artifacts:

- [data-model.md](./data-model.md)
- [contracts/okf-bundle.contract.md](./contracts/okf-bundle.contract.md)
- [contracts/okf-doctor.contract.md](./contracts/okf-doctor.contract.md)
- [contracts/graph-json.contract.md](./contracts/graph-json.contract.md)
- [quickstart.md](./quickstart.md)

Contract-test plan:

- Add OKF fixture source trees with representative agents, skills, routing tables, malformed frontmatter, missing resources, and unresolved agent targets.
- Add graph fixture assertions for stable ids, `routes_to` edges, evidence, backlinks, and diagnostic overlays.
- Add doctor fixture assertions for error/warning severity and machine-readable output shape.
- Keep UI tests thin: verify Cabal can trigger export/doctor without blocking and can render graph status summaries.

## Phase 2: MVP Implementation Plan

1. Build `cabal.okf.models` with small immutable dataclasses or typed dicts for source artifacts, concepts, relations, graph nodes, graph edges, and doctor findings.
2. Build source discovery for configured repo categories with deterministic ordering and normalized POSIX resource paths.
3. Build deterministic frontmatter writing for the OKF subset used by generated documents.
4. Build concept generators for agents, skills, hooks, rules, output styles, project templates, setup tools, Codex assets, and Spec Kit features.
5. Build skill-agent relation extraction for explicit `@agent-name` references and simple Markdown routing tables.
6. Build backlink generation so agent concepts show incoming skill routes.
7. Build graph snapshot generation from concept and relation objects.
8. Build doctor validation for required fields, source resource existence, duplicate ids, unresolved relation targets, and graph/document consistency.
9. Add a small service entrypoint callable by tests and future Cabal UI actions.
10. Generate the first `docs/okf/prompt-lib/` bundle only after contract tests and exporter tests pass.

## Phase 3: Beyond MVP Plan

### Milestone B1 - Static Graph Explorer

- Generate `docs/okf/prompt-lib/graph.html` or `docs/okf/prompt-lib/viewer/` that consumes `graph.json`.
- Provide filters for concept type, relation kind, warnings, and disconnected nodes.
- Keep the viewer static and offline; no server requirement.

### Milestone B2 - Cabal Knowledge Screen

- Add a Cabal screen that runs export/doctor on a worker thread and displays graph health.
- Show concept counts, relation counts, top routed agents, orphaned concepts, and doctor findings.
- Add a focused detail panel for selected agent or skill nodes.

### Milestone B3 - Recommendation Explanations

- Add a recommendation helper that maps task signals to graph-backed skill-agent routes.
- Explain recommendations by citing relation evidence instead of hardcoded prose.
- Keep recommendations advisory; they do not silently invoke agents or mutate config.

### Milestone B4 - Wider Relation Extraction

- Extract hook-to-rule, tool-to-installer, template-to-agent, spec-to-agent, MCP-to-tool, and Codex-to-Claude compatibility relations.
- Add confidence levels so inferred edges are clearly separated from explicit edges.

### Milestone B5 - OKF Import and Federation

- Add optional import/merge from external OKF bundles.
- Require a full YAML parser and conflict policy before import becomes writable.
- Keep imported bundles namespaced and read-only until a user explicitly promotes changes.

## Subagent Delegation

| Area | Owner | Mode | Notes |
|---|---|---|---|
| OKF exporter, models, graph builder, doctor | `@python-architect` | Sequential for shared package | Owns `setup/src/cabal/okf/` architecture |
| Contract/unit tests and fixtures | `@python-tester` | Parallel after contracts are fixed | Owns `tests/contract/test_okf_*` and `tests/unit/test_okf_*` |
| Cabal Knowledge screen and worker integration | `@python-architect` | Parallel after service API stabilizes | Owns Textual view/widget code |
| Textual CSS-only polish for graph/status panels | `@frontend-css` | Parallel after UI structure exists | Owns CSS or style-only changes |
| Documentation, quickstart, and generated bundle policy | main session | Sequential | Keeps spec, docs, and source-of-truth language aligned |
| Plan/code conformance review | `@code-plan-verifier` | Read-only final audit | Verifies implementation matches spec and contracts |

## Parallel Execution Map

```text
Wave 1:
  main: finalize contracts and fixtures

Wave 2:
  @python-architect: implement models/exporter/frontmatter/relations
  @python-tester: create failing contract tests from contracts

Wave 3:
  @python-architect: implement doctor and graph builder
  @python-tester: add malformed fixture and doctor tests

Wave 4:
  @python-architect: add service entrypoint and optional Cabal status panel
  @frontend-css: style Cabal OKF panel if UI is included

Wave 5:
  main: generate docs/okf/prompt-lib bundle
  @code-plan-verifier: audit conformance and test coverage
```

## Complexity Tracking

No constitution violations are expected for MVP. Complexity is intentionally contained by:

- Treating OKF as generated output rather than a new authoring surface.
- Avoiding import/round-trip features until the export and graph contracts are stable.
- Deferring visualization until `graph.json` is proven by contract tests.
- Using explicit relation extraction first and marking later inference as lower confidence.

## Post-Design Constitution Recheck

**Status**: PASS

- Phase 1 artifacts are present.
- Contract surfaces are documented.
- No new global configuration mutation is introduced.
- No new skills or agents are required.
- Parallel tasks have non-overlapping owners and paths.

## Next Command

Run `/speckit-tasks` for this feature after accepting the plan. The first tasks should create contract tests before implementing exporter or doctor code.
