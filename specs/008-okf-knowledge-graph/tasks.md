# Tasks: OKF Knowledge Graph

**Input**: Design documents from `/specs/008-okf-knowledge-graph/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)  
**Tests**: Required by SC-003 and Constitution Gate 3. Contract tests must be written before implementation for OKF bundle, doctor, and graph JSON surfaces.  
**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (5/5 — T001–T005)
**Purpose**: Create the OKF package shell, fixtures, and generated-output documentation.

- [X] T001 Create OKF package directory and exports in `setup/src/cabal/okf/__init__.py` â€” Owner: @python-architect
- [X] T002 [P] Create representative source fixture tree in `tests/fixtures/okf_repo/` â€” Owner: @python-tester â€” Parallel: yes
- [X] T003 [P] Create malformed generated bundle fixture in `tests/fixtures/okf_bundle_malformed/` â€” Owner: @python-tester â€” Parallel: yes
- [X] T004 [P] Add generated OKF output policy in `docs/okf/README.md` â€” Owner: main â€” Parallel: yes
- [X] T005 Add module command placeholder in `setup/src/cabal/okf/__main__.py` â€” Owner: @python-architect

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (6/6 — T006–T011)
**Purpose**: Build shared models, frontmatter handling, and path safety used by every story.

**CRITICAL**: No user story implementation begins until this phase is complete.

- [X] T006 [P] Add model construction tests in `tests/unit/test_okf_models.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T007 Implement OKF dataclasses in `setup/src/cabal/okf/models.py` â€” Owner: @python-architect
- [X] T008 [P] Add deterministic frontmatter tests in `tests/unit/test_okf_frontmatter.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T009 Implement deterministic YAML subset writer/parser in `setup/src/cabal/okf/frontmatter.py` â€” Owner: @python-architect
- [X] T010 [P] Add path normalization and secret-screening tests in `tests/unit/test_okf_paths.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T011 Implement resource path normalization and secret screening helpers in `setup/src/cabal/okf/paths.py` â€” Owner: @python-architect

**Checkpoint**: Foundation ready. User story work can now begin.

---

## Phase 3: User Story 1 - Export a portable OKF bundle (Priority: P1) MVP

**Status**: ✅ Complete (9/9 — T012–T020)
**Goal**: Generate deterministic OKF Markdown, manifest, index, log, and graph placeholder files from existing prompt-lib source categories.

**Independent Test**: Run export against a fixture repo and verify required files, required frontmatter, stable resource paths, manifest categories, and deterministic output.

### Tests for User Story 1

> Write these tests first and confirm they fail before implementation.

- [X] T012 [P] [US1] Add bundle output contract tests in `tests/contract/test_okf_bundle_contract.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T013 [P] [US1] Add source discovery unit tests in `tests/unit/test_okf_sources.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T014 [P] [US1] Add exporter determinism and manifest unit tests in `tests/unit/test_okf_exporter.py` â€” Owner: @python-tester â€” Parallel: yes

### Implementation for User Story 1

- [X] T015 [US1] Implement source category discovery in `setup/src/cabal/okf/sources.py` â€” Owner: @python-architect
- [X] T016 [US1] Implement concept document generation in `setup/src/cabal/okf/exporter.py` â€” Owner: @python-architect
- [X] T017 [US1] Implement `index.md`, `log.md`, and `manifest.json` writing in `setup/src/cabal/okf/exporter.py` â€” Owner: @python-architect
- [X] T018 [US1] Expose export service function in `setup/src/cabal/okf/__init__.py` â€” Owner: @python-architect
- [X] T019 [US1] Wire `python -m cabal.okf export` in `setup/src/cabal/okf/__main__.py` â€” Owner: @python-architect
- [X] T020 [US1] Generate first OKF bundle under `docs/okf/prompt-lib/` after tests pass â€” Owner: main

**Checkpoint**: OKF export can be demonstrated independently.

---

## Phase 4: User Story 2 - Doctor the knowledge catalog (Priority: P1) MVP

**Status**: ✅ Complete (7/7 — T021–T027)
**Goal**: Validate generated OKF bundles and report deterministic human and JSON findings.

**Independent Test**: Run the doctor against valid and malformed bundle fixtures and verify exit semantics, finding codes, summary counts, and missing-resource diagnostics.

### Tests for User Story 2

> Write these tests first and confirm they fail before implementation.

- [X] T021 [P] [US2] Add doctor output and exit-code contract tests in `tests/contract/test_okf_doctor_contract.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T022 [P] [US2] Add malformed bundle finding tests in `tests/unit/test_okf_doctor.py` â€” Owner: @python-tester â€” Parallel: yes

### Implementation for User Story 2

- [X] T023 [US2] Implement doctor finding builders and summary counts in `setup/src/cabal/okf/doctor.py` â€” Owner: @python-architect
- [X] T024 [US2] Implement required-file, frontmatter, and resource validators in `setup/src/cabal/okf/doctor.py` â€” Owner: @python-architect
- [X] T025 [US2] Implement manifest and graph consistency validators in `setup/src/cabal/okf/doctor.py` â€” Owner: @python-architect
- [X] T026 [US2] Wire `python -m cabal.okf doctor` in `setup/src/cabal/okf/__main__.py` â€” Owner: @python-architect
- [X] T027 [US2] Add export-then-doctor integration test in `tests/integration/test_okf_export_doctor.py` â€” Owner: @python-tester

**Checkpoint**: Generated bundles can be trusted or rejected with actionable findings.

---

## Phase 5: User Story 3 - Reveal skill-agent references (Priority: P1) MVP

**Status**: ✅ Complete (8/8 — T028–T035)
**Goal**: Extract explicit skill-agent routes, preserve evidence, derive backlinks, and emit graph edges.

**Independent Test**: Run relation extraction against skill fixtures with `@agent` references and routing tables, then verify `routes_to` edges, evidence, target resolution, and backlinks.

### Tests for User Story 3

> Write these tests first and confirm they fail before implementation.

- [X] T028 [P] [US3] Add graph JSON contract tests for nodes, edges, and `routes_to` relations in `tests/contract/test_okf_graph_contract.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T029 [US3] Add explicit `@agent` extraction tests in `tests/unit/test_okf_relations.py` â€” Owner: @python-tester
- [X] T030 [US3] Add routing-table extraction and backlink tests in `tests/unit/test_okf_relations.py` â€” Owner: @python-tester

### Implementation for User Story 3

- [X] T031 [US3] Implement explicit agent token extraction in `setup/src/cabal/okf/relations.py` â€” Owner: @python-architect
- [X] T032 [US3] Implement Markdown routing-table extraction in `setup/src/cabal/okf/relations.py` â€” Owner: @python-architect
- [X] T033 [US3] Implement relation target resolution and backlink derivation in `setup/src/cabal/okf/relations.py` â€” Owner: @python-architect
- [X] T034 [US3] Implement graph snapshot builder in `setup/src/cabal/okf/graph.py` â€” Owner: @python-architect
- [X] T035 [US3] Integrate `routes_to` relations, backlinks, and `graph.json` writing in `setup/src/cabal/okf/exporter.py` â€” Owner: @python-architect

**Checkpoint**: MVP is complete when US1, US2, and US3 all pass independently.

---

## Phase 6: User Story 4 - Browse the graph visually (Priority: P2)

**Status**: ✅ Complete (8/8 — T036–T043)
**Goal**: Provide static and Cabal-native ways to browse the graph once the MVP graph contract is stable.

**Independent Test**: Generate graph JSON from fixtures and verify visual consumers render node groups, edge filters, selected-node details, and doctor overlays.

### Tests for User Story 4

- [X] T036 [P] [US4] Add static graph viewer integration tests in `tests/integration/test_okf_graph_viewer.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T037 [P] [US4] Add Cabal Knowledge screen worker tests in `tests/integration/test_okf_cabal_ui.py` â€” Owner: @python-tester â€” Parallel: yes

### Implementation for User Story 4

- [X] T038 [US4] Implement static graph viewer generation in `setup/src/cabal/okf/viewer.py` â€” Owner: @python-architect
- [X] T039 [US4] Wire graph/viewer command in `setup/src/cabal/okf/__main__.py` â€” Owner: @python-architect
- [X] T040 [US4] Implement Cabal Knowledge screen in `setup/src/cabal/views/knowledge.py` â€” Owner: @python-architect
- [X] T041 [US4] Add OKF status widget in `setup/src/cabal/widgets/okf_panel.py` â€” Owner: @python-architect
- [X] T042 [US4] Register Knowledge navigation in `setup/src/cabal/views/home.py` and `setup/src/cabal/app.py` â€” Owner: @python-architect
- [X] T043 [US4] Add Knowledge screen Textual styling in `setup/src/cabal/app.py` â€” Owner: @frontend-css

**Checkpoint**: Graph can be inspected visually without changing the graph contract.

---

## Phase 7: User Story 5 - Explain recommendations from graph context (Priority: P3)

**Status**: ✅ Complete (5/5 — T044–T048)
**Goal**: Use graph evidence to explain future agent, skill, or tool recommendations.

**Independent Test**: Feed task-signal fixtures into the recommendation layer and verify the selected candidate includes relation-backed evidence.

### Tests for User Story 5

- [X] T044 [P] [US5] Add recommendation evidence tests in `tests/unit/test_okf_recommendations.py` â€” Owner: @python-tester â€” Parallel: yes

### Implementation for User Story 5

- [X] T045 [US5] Implement task signal to graph route matcher in `setup/src/cabal/okf/recommendations.py` â€” Owner: @python-architect
- [X] T046 [US5] Add recommendation explanations to `setup/src/cabal/views/knowledge.py` â€” Owner: @python-architect
- [X] T047 [US5] Add recommendation CLI smoke tests in `tests/integration/test_okf_recommendations_cli.py` â€” Owner: @python-tester
- [X] T048 [US5] Document recommendation scope in `specs/008-okf-knowledge-graph/quickstart.md` â€” Owner: main

**Checkpoint**: Recommendations are advisory and explainable from graph evidence.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Status**: ✅ Complete (6/6 — T049–T054)
**Purpose**: Tighten docs, security coverage, generated output, and final verification.

- [X] T049 [P] Update implemented command examples in `specs/008-okf-knowledge-graph/quickstart.md` â€” Owner: main â€” Parallel: yes
- [X] T050 [P] Update regeneration and commit policy in `docs/okf/README.md` â€” Owner: main â€” Parallel: yes
- [X] T051 Regenerate final OKF bundle in `docs/okf/prompt-lib/` â€” Owner: main
- [X] T052 [P] Add explicit secret-redaction fixture coverage in `tests/unit/test_okf_security.py` â€” Owner: @python-tester â€” Parallel: yes
- [X] T053 Run focused OKF test suite covering `tests/contract/test_okf_bundle_contract.py`, `tests/contract/test_okf_doctor_contract.py`, and `tests/contract/test_okf_graph_contract.py` â€” Owner: @python-tester
- [X] T054 Audit implementation against `specs/008-okf-knowledge-graph/plan.md` and `specs/008-okf-knowledge-graph/tasks.md` â€” Owner: @code-plan-verifier

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1. Blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2. Starts MVP.
- **User Story 2 (Phase 4)**: Depends on Phase 2 and benefits from US1 fixtures, but malformed fixture tests remain independently runnable.
- **User Story 3 (Phase 5)**: Depends on Phase 2 and integrates with US1 exporter output.
- **User Story 4 (Phase 6)**: Depends on MVP graph contract from US3.
- **User Story 5 (Phase 7)**: Depends on graph quality from US3 and optionally UI shell from US4.
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. Delivers the first independently demonstrable export.
- **US2 (P1)**: Foundational only for core validation, but final integration should run after US1 export exists.
- **US3 (P1)**: Requires US1 exporter integration to write relations and graph output.
- **US4 (P2)**: Requires stable `graph.json` from US3.
- **US5 (P3)**: Requires relation evidence from US3; UI explanation work should wait for US4 if Cabal display is included.

### MVP Scope

MVP is Phases 1 through 5: setup, foundation, export, doctor, and skill-agent references. Stop after T035 if the goal is a minimal but meaningful OKF release.

---

## Parallel Execution Examples

### Setup

```text
T002 Create source fixtures in tests/fixtures/okf_repo/
T003 Create malformed bundle fixtures in tests/fixtures/okf_bundle_malformed/
T004 Add generated output policy in docs/okf/README.md
```

### User Story 1

```text
T012 Add bundle contract tests in tests/contract/test_okf_bundle_contract.py
T013 Add source discovery tests in tests/unit/test_okf_sources.py
T014 Add exporter tests in tests/unit/test_okf_exporter.py
```

### User Story 2

```text
T021 Add doctor contract tests in tests/contract/test_okf_doctor_contract.py
T022 Add malformed bundle tests in tests/unit/test_okf_doctor.py
```

### User Story 4

```text
T036 Add static graph viewer tests in tests/integration/test_okf_graph_viewer.py
T037 Add Cabal Knowledge screen tests in tests/integration/test_okf_cabal_ui.py
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 export and validate the generated OKF bundle shape.
3. Complete US2 doctor and validate malformed bundle behavior.
4. Complete US3 skill-agent routes, backlinks, and graph JSON.
5. Stop and validate: run the focused OKF contract and unit tests before adding visualization.

### Incremental Delivery

1. Export-only demo: US1 produces `docs/okf/prompt-lib/`.
2. Trust layer: US2 doctor gives pass/fail confidence.
3. Killer feature: US3 turns flat docs into the skill-agent graph.
4. Visual layer: US4 makes the graph browsable.
5. Operational layer: US5 makes recommendations explainable.

### Notes

- `[P]` means different files and no dependency on another incomplete task.
- `Parallel: yes` means concurrent writing agents must use isolated worktrees during implementation.
- Contract tests for OKF bundle, doctor, and graph JSON come before implementation.
- Generated OKF files are derived output. Fix source files first, then regenerate.

