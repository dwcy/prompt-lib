# Phase 0 - Research and Design Decisions

**Feature**: 008-okf-knowledge-graph - OKF Knowledge Graph  
**Date**: 2026-06-18

This document records the decisions behind the MVP and beyond-MVP plan.

## R1 - Should OKF become source of truth?

**Decision**: No. OKF is a generated derivative catalog.

**Rationale**:

- Prompt-lib already has clear source artifacts: `global/agents`, `global/skills`, `global/hooks`, `global/rules`, `CLAUDE.md`, setup metadata, and Spec Kit docs.
- Replacing those with OKF would make day-to-day editing harder and would couple the repo to a draft external format.
- A generated catalog still gives external AI tools a standard reading surface and can be deleted/regenerated safely.

**Alternatives considered**:

- *Make OKF primary authoring format*: rejected because it would force every prompt-lib maintainer workflow through a new schema.
- *Do nothing until OKF stabilizes*: rejected because generated metadata is low-risk and can evolve with the draft.

## R2 - Where should the bundle live?

**Decision**: Use `docs/okf/prompt-lib/` as the default generated bundle root.

**Rationale**:

- The bundle is documentation and interoperability output, not deployable Claude config.
- Keeping it outside `global/` prevents accidental deployment to `~/.claude/`.
- A stable docs path can be published, linked, or consumed by future visualizers without affecting runtime config.

**Alternatives considered**:

- *`global/okf/`*: rejected because `global/` is deployment input.
- *`.okf/`*: rejected because hidden directories are less discoverable and less docs-friendly.
- *`setup/src/cabal/okf_bundle/`*: rejected because generated content should not live inside package source.

## R3 - Should MVP add a YAML dependency?

**Decision**: No new YAML dependency in MVP. Emit a deterministic YAML subset and validate only the subset this exporter creates.

**Rationale**:

- MVP does not import or round-trip arbitrary third-party OKF documents.
- The exporter controls the generated frontmatter, so a small writer is enough for scalar fields and simple lists.
- Avoiding a dependency keeps Cabal's install surface small.

**Alternatives considered**:

- *Add PyYAML now*: deferred. It becomes more compelling for import, merge, and arbitrary OKF validation.
- *Write JSON-only metadata*: rejected because OKF v0.1 centers on Markdown files with YAML frontmatter.

## R4 - What relation extraction should ship first?

**Decision**: Start with explicit skill-agent references and simple routing tables.

**Rationale**:

- The user identified skill-agent references as the killer feature.
- Explicit `@agent-name` tokens and routing tables provide high-confidence edges with understandable evidence.
- Starting explicit prevents the graph from feeling magical or noisy.

**Alternatives considered**:

- *Infer relations from all prose using heuristics*: deferred. Useful later, but must be clearly marked lower-confidence.
- *Only generate flat concepts, no relations*: rejected because the graph value comes from connections.

## R5 - What should graph visualization consume?

**Decision**: Generate `graph.json` first and make every visualizer consume that contract.

**Rationale**:

- A JSON snapshot lets tests validate the graph without rendering UI.
- Static HTML, Cabal screens, search indexes, and recommendation helpers can share the same source.
- It prevents each consumer from reparsing Markdown in its own subtly different way.

**Alternatives considered**:

- *Visualizer parses Markdown directly*: rejected because parsing would drift across consumers.
- *Use a database-backed graph*: rejected for MVP; unnecessary storage and migration overhead.

## R6 - Should generated OKF be committed?

**Decision**: The implementation must support committed or uncommitted generated output, but should treat it as reproducible.

**Rationale**:

- Committing generated docs can make diffs and GitHub browsing useful.
- Some users may prefer to regenerate locally and ignore output.
- Determinism keeps both workflows valid.

**Alternatives considered**:

- *Always commit generated docs*: too rigid.
- *Never commit generated docs*: limits discovery and visual publishing.

## R7 - How should recommendations use OKF?

**Decision**: Recommendation and explanation features are beyond MVP and must cite graph evidence.

**Rationale**:

- Recommendations are only credible if the graph is already correct and validated.
- The graph can answer "why this agent?" with evidence from the skill route instead of hidden hardcoding.
- Keeping recommendation advisory avoids surprising agent invocation or config changes.

**Alternatives considered**:

- *Ship recommendation in MVP*: rejected because it would build on unproven graph quality.
- *Hardcode recommendation rules separately*: rejected because it duplicates the graph and makes explanations stale.

## R8 - What OKF conformance level is realistic?

**Decision**: Target generated OKF v0.1-compatible Markdown, with tolerant additive fields for prompt-lib relations.

**Rationale**:

- OKF v0.1 is draft and intentionally lightweight.
- The required baseline is Markdown with YAML frontmatter, plus reserved index/log docs.
- Prompt-lib-specific relation fields can be additive as long as unknown fields are tolerated.

**Alternatives considered**:

- *Wait for OKF v1.0*: rejected because this is a low-risk interoperability layer.
- *Invent a custom graph-only schema*: rejected because OKF's value is the shared external vocabulary.
