# Feature Specification: OKF Knowledge Graph

**Feature Branch**: `008-okf-knowledge-graph`  
**Created**: 2026-06-18  
**Status**: Draft  
**Input**: User description: "Create a plan for using OKF from MVP to beyond MVP, with the skill-agent reference graph as a killer feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export a portable OKF bundle (Priority: P1)

As the prompt-lib maintainer, I want Cabal to generate an Open Knowledge Format bundle from the repository's existing agents, skills, hooks, rules, templates, and tool metadata so that other AI tools can inspect the ecosystem without learning prompt-lib's internal folder layout.

**Why this priority**: The project is an infrastructure library for connecting relevant tools to the AI ecosystem. A generated OKF bundle gives the ecosystem a standard, vendor-neutral surface without replacing the repository's current source of truth.

**Independent Test**: Run the export against a clean checkout and verify the output directory contains OKF Markdown files with required frontmatter, stable resource paths, and a manifest that names all included source categories.

**Acceptance Scenarios**:

1. **Given** the repo contains `global/agents`, `global/skills`, `global/hooks`, `global/rules`, and setup tool metadata, **When** the OKF export runs, **Then** it writes a deterministic OKF bundle under `docs/okf/prompt-lib/`.
2. **Given** a generated OKF document, **When** an OKF consumer reads the file, **Then** it can find `type`, `title`, `description`, `resource`, `tags`, and `timestamp` fields in YAML frontmatter.
3. **Given** no source files changed, **When** the OKF export runs twice, **Then** the generated file tree and graph snapshot are byte-stable except for explicitly configured timestamp behavior.

---

### User Story 2 - Doctor the knowledge catalog (Priority: P1)

As the maintainer, I want a doctor check that validates the generated OKF bundle and reports missing concepts, broken resource paths, malformed frontmatter, and orphaned graph edges so that the catalog can be trusted before it is shared or used by agents.

**Why this priority**: A graph is useful only if it can be verified. The doctor is also the safest first integration point because it can run in tests and in the TUI without changing user configuration.

**Independent Test**: Deliberately create a malformed generated fixture and verify the doctor returns deterministic errors, warnings, and exit status.

**Acceptance Scenarios**:

1. **Given** a valid generated bundle, **When** the doctor runs, **Then** it returns success with counts for documents, relations, and source categories.
2. **Given** a document points to a missing source file, **When** the doctor runs, **Then** it returns a failing finding with the document path and missing resource.
3. **Given** a relation target cannot be resolved, **When** the doctor runs, **Then** it reports the relation as an orphaned edge and identifies the source document that emitted it.

---

### User Story 3 - Reveal skill-agent references (Priority: P1)

As the maintainer, I want the OKF exporter to discover which skills route to which specialist agents, including the reason for each relationship, so that the repo can answer "why would this agent be used here?" instead of exposing only a flat file list.

**Why this priority**: The skill-agent reference map is the most differentiated value. It turns prompt-lib from a collection of Markdown files into an explainable operational graph.

**Independent Test**: Run extraction against fixture skills with explicit `@agent` references and routing tables, then assert the generated OKF relations and graph edges contain the expected source, target, kind, evidence, and reason.

**Acceptance Scenarios**:

1. **Given** a skill file references `@python-architect`, **When** the OKF export runs, **Then** the skill concept contains a `routes_to` relation targeting the `python-architect` agent concept.
2. **Given** a skill routing table explains when an agent is selected, **When** the relation is generated, **Then** the edge includes a short evidence string or line reference that explains the route.
3. **Given** an agent is referenced by multiple skills, **When** the agent concept is generated, **Then** it includes backlink data showing the skills that route to it.

---

### User Story 4 - Browse the graph visually (Priority: P2)

As the maintainer, I want a visual graph view that shows agents, skills, hooks, rules, tools, and specs as connected nodes so that I can understand the ecosystem at a glance and spot orphaned or overloaded areas.

**Why this priority**: Visualization is the most powerful beyond-MVP payoff, but it depends on the stable export, doctor, and graph contracts.

**Independent Test**: Generate graph JSON from a fixture bundle and open the static visualizer or Cabal knowledge screen to confirm nodes, edges, filters, and selected-node details render correctly.

**Acceptance Scenarios**:

1. **Given** a generated graph snapshot, **When** the visualizer opens, **Then** it displays nodes grouped by concept type and edges by relation kind.
2. **Given** the user selects an agent node, **When** details render, **Then** the view shows its source file, incoming skill routes, outgoing links, and any doctor warnings.
3. **Given** the user filters to `routes_to` edges, **When** the graph updates, **Then** only skill-agent routing relationships remain visible.

---

### User Story 5 - Explain recommendations from graph context (Priority: P3)

As the maintainer, I want future agent/tool recommendations to cite the OKF graph so that Cabal or a compatible harness can explain why it recommends a specific agent, tool, or skill for a task.

**Why this priority**: This makes the OKF catalog operational instead of merely documentary, but it should come after the graph has proven reliable.

**Independent Test**: Feed a task classification fixture into the recommendation layer and verify it returns a candidate agent plus relation-backed explanation.

**Acceptance Scenarios**:

1. **Given** a task mentions Python service design, **When** recommendation runs, **Then** it can point to the relevant skill-agent route and the `python-architect` concept.
2. **Given** multiple agents match a task, **When** recommendation explains the choice, **Then** it includes graph evidence rather than a hardcoded answer.

### Edge Cases

- Source files may contain references to agents that do not exist in `global/agents`; the export should keep the edge as unresolved and the doctor should report it.
- Agent names may appear in prose without a routing intent; MVP extraction should prefer explicit `@agent` tokens, routing tables, and frontmatter over weak natural-language guesses.
- Some generated concepts may represent files that are Claude-Code-specific; OKF metadata must mark them as Claude-specific rather than implying they are portable instructions for every harness.
- The OKF spec is draft v0.1; unknown frontmatter fields and relation extensions must be additive and tolerant.
- Generated output must not include secrets, local credential values, or private runtime state.
- Windows, Linux, and macOS path separators must normalize to POSIX-style resource paths inside OKF documents.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate an OKF bundle from existing prompt-lib source files without making generated OKF documents the canonical source of truth.
- **FR-002**: The generated bundle MUST live under `docs/okf/prompt-lib/` by default and MUST be safe to delete and regenerate.
- **FR-003**: Each generated OKF document MUST include YAML frontmatter with at least `type`, `title`, `description`, `resource`, `tags`, and `timestamp`.
- **FR-004**: The exporter MUST include concepts for agents, skills, hooks, rules, output styles, project templates, Codex-compatible assets, setup tools, and active Spec Kit features when those source categories exist.
- **FR-005**: The exporter MUST emit stable concept identifiers derived from repository-relative paths or normalized names.
- **FR-006**: The exporter MUST extract explicit skill-agent references from `@agent-name` tokens and structured routing tables in `global/skills/*.md`.
- **FR-007**: Skill-agent relations MUST include relation kind, source concept, target concept, source resource path, and evidence text or line reference when available.
- **FR-008**: Agent concepts MUST include backlink metadata for skills that route to them.
- **FR-009**: The exporter MUST generate a graph snapshot file that can be consumed without parsing all Markdown documents.
- **FR-010**: The doctor MUST validate required frontmatter, resource path existence, relation target resolution, duplicate concept identifiers, and graph/document consistency.
- **FR-011**: Doctor output MUST be deterministic and machine-readable while also having a concise human-readable summary for Cabal.
- **FR-012**: MVP implementation MUST avoid network access and MUST run offline from the repository checkout.
- **FR-013**: MVP implementation MUST not require a new persistent service, database, or cloud account.
- **FR-014**: Generated metadata MUST never include secret values; environment variables may be listed by key name only when already documented by the repo.
- **FR-015**: Beyond-MVP graph visualization MUST consume the same graph snapshot contract used by tests, not a separate ad hoc parser.
- **FR-016**: Beyond-MVP Cabal UI integration MUST surface export, doctor, and graph status without blocking the Textual event loop.
- **FR-017**: Recommendation features MUST cite graph relations as evidence when explaining suggested agents, tools, or skills.

### Key Entities

- **OKF Bundle**: A generated directory containing Markdown concept documents, reserved index/log documents, manifest metadata, and graph snapshots.
- **Concept Document**: A single OKF Markdown file representing an agent, skill, hook, rule, tool, template, spec, or other prompt-lib artifact.
- **Relation**: A typed edge between two concepts, such as `routes_to`, `references`, `depends_on`, `documents`, `configured_by`, or `deploys`.
- **Edge Evidence**: The file path, line number, or short text that explains why a relation exists.
- **Graph Snapshot**: A generated JSON file containing normalized nodes, edges, counts, and diagnostic overlays for visualizers and recommendation features.
- **Doctor Finding**: A validation result with severity, code, message, location, and optional remediation guidance.
- **Source Artifact**: A repository file or directory that the exporter reads to derive one or more concepts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean export over the current repo completes locally in under 5 seconds on a typical development machine.
- **SC-002**: The generated bundle includes at least 95 percent of files from the configured source categories, excluding documented skip patterns.
- **SC-003**: Contract tests cover OKF frontmatter, graph snapshot shape, doctor output, and at least three skill-agent relation fixtures before implementation is considered complete.
- **SC-004**: The doctor returns zero errors for a freshly generated bundle from a clean checkout.
- **SC-005**: The graph snapshot includes every generated concept as a node and every emitted relation as an edge.
- **SC-006**: For explicit `@agent` references in skill fixtures, extraction produces 100 percent of expected `routes_to` edges with evidence.
- **SC-007**: No generated document contains raw secret-like values from environment files, local settings, or runtime state fixtures.

## Assumptions

- OKF is used as a portable derived catalog, not as a replacement for `global/agents`, `global/skills`, `CLAUDE.md`, or Spec Kit artifacts.
- MVP targets the local repository only; import from third-party OKF bundles is beyond MVP.
- The OKF spec remains draft v0.1 during this feature and allows additive unknown fields.
- Cabal is the primary local UI, but the export and doctor logic should be usable from tests and future command entrypoints without Textual.
- Generated output can be committed later if useful, but implementation must tolerate deleting and regenerating it.
- The first visualization can be static HTML or a Cabal knowledge screen as long as it consumes the same graph JSON contract.
