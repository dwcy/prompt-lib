# Tasks: Cabal Web UI

**Input**: Design documents from `/specs/011-cabal-web-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Contract, unit, integration, and static asset tests are included because the plan requires contract-test ordering for the localhost data API, frontend behavior, and redaction/safety boundary.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format

- **[P]**: Can run in parallel if staffed sequentially or in isolated worktrees; this plan does not mark tasks `Parallel: yes`.
- **[Story]**: Maps to user stories from [spec.md](./spec.md).
- **Owner**: Named subagent from `.specify/memory/agents.md`, or `main` for orchestration/docs only.
- Include exact file paths in descriptions.

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (5/5 — T001–T005)
**Purpose**: Create the local web package, asset locations, and test scaffolding without changing existing Cabal TUI behavior.

- [X] T001 Create the Cabal web package skeleton in setup/src/cabal/web/__init__.py and setup/src/cabal/web/assets/index.html — Owner: @python-architect
- [X] T002 Create empty static asset entry files in setup/src/cabal/web/assets/app.js and setup/src/cabal/web/assets/styles.css — Owner: @frontend-architect
- [X] T003 Create web test module placeholders in tests/contract/test_cabal_web_api_contract.py, tests/contract/test_cabal_web_frontend_contract.py, and tests/contract/test_cabal_web_redaction_contract.py — Owner: @python-tester
- [X] T004 Create web unit/integration test placeholders in tests/unit/test_cabal_web_redaction.py, tests/unit/test_cabal_web_serializers.py, tests/integration/test_cabal_web_assets.py, and tests/integration/test_cabal_web_server.py — Owner: @python-tester
- [X] T005 Verify package/static asset inclusion requirements in setup/pyproject.toml and setup/build/cabal.spec — Owner: @python-architect

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (11/11 — T006–T016)
**Purpose**: Establish the read-only localhost API contract, shared envelope/redaction helpers, and static asset serving before story work begins.

**CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T006 Add redaction and local-safety contract tests in tests/contract/test_cabal_web_redaction_contract.py — Owner: @python-tester
- [X] T007 Add web data API envelope, method, 404, and endpoint-shape contract tests in tests/contract/test_cabal_web_api_contract.py — Owner: @python-tester
- [X] T008 Add frontend static contract tests for local assets, required views, endpoint constants, and no external CDN dependencies in tests/contract/test_cabal_web_frontend_contract.py — Owner: @python-tester
- [X] T009 Add recursive redaction unit tests for strings, nested dictionaries, lists, diagnostic text, and token-like URLs in tests/unit/test_cabal_web_redaction.py — Owner: @python-tester
- [X] T010 Implement recursive redaction and safe URL helpers in setup/src/cabal/web/redaction.py — Owner: @python-architect
- [X] T011 Implement versioned response envelope and diagnostic helpers in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T012 Implement shared serializers for SectionHealth, DiagnosticEvent, and safe strings in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T013 Implement read-only route dispatch for /api/health and /api/diagnostics in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T014 Implement localhost-only static/API HTTP server and mutating-method rejection in setup/src/cabal/web/server.py — Owner: @python-architect
- [X] T015 Implement CLI entrypoint with --host, --port, and --project arguments in setup/src/cabal/web/__main__.py — Owner: @python-architect
- [X] T016 Add integration tests for local bind defaults, static file serving, JSON content type, and mutating method rejection in tests/integration/test_cabal_web_server.py — Owner: @python-tester

**Checkpoint**: Foundation ready - the read-only local backend can serve static assets and safe health/diagnostic envelopes.

---

## Phase 3: User Story 1 - Explore Cabal Data From a Browser (Priority: P1) MVP

**Status**: ✅ Complete (11/11 — T017–T027)
**Goal**: A maintainer can start the local backend, open the browser app, and see live backend-fed overview data with independent loading/error states.

**Independent Test**: Start `python -m cabal.web --host 127.0.0.1 --port 8765 --project .`, open the app, and verify the Overview loads live backend data, capture time, section states, and retryable section errors without hardcoded fixture data.

### Tests for User Story 1

- [X] T017 [P] [US1] Add overview endpoint contract tests for /api/overview live summary fields and partial-section failures in tests/contract/test_cabal_web_api_contract.py — Owner: @python-tester
- [X] T018 [P] [US1] Add serializer unit tests for OverviewSummary, BackendHealth, SectionHealth, and DiagnosticEvent in tests/unit/test_cabal_web_serializers.py — Owner: @python-tester
- [X] T019 [P] [US1] Add frontend asset integration tests for Overview containers, loading labels, retry controls, and schema mismatch labels in tests/integration/test_cabal_web_assets.py — Owner: @python-tester

### Implementation for User Story 1

- [X] T020 [US1] Implement overview summary serialization from Cabal tool, OKF, project health, and diagnostics sources in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T021 [US1] Implement /api/overview route composition with section-level partial error handling in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T022 [US1] Build the semantic application shell with Overview, Tools, Knowledge, Project Health, and Diagnostics view containers in setup/src/cabal/web/assets/index.html — Owner: @frontend-architect
- [X] T023 [US1] Implement vanilla JavaScript navigation, endpoint fetch helpers, schema-version handling, independent section state, and retry behavior in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T024 [US1] Render Overview metrics, backend URL, freshness states, diagnostics count, and section cards from backend responses in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T025 [US1] Style the dark shell layout, side navigation, metric bands, section states, focus states, and responsive first screen in setup/src/cabal/web/assets/styles.css — Owner: @frontend-css
- [X] T026 [US1] Add server/app integration test for browser shell plus /api/overview response using tests/integration/test_cabal_web_server.py — Owner: @python-tester
- [X] T027 [US1] Update quickstart verification notes for launching the local web UI in specs/011-cabal-web-ui/quickstart.md — Owner: main

**Checkpoint**: User Story 1 is independently functional as the MVP browser dashboard.

---

## Phase 4: User Story 2 - Navigate the Tool Catalog Visually (Priority: P1)

**Status**: ✅ Complete (12/12 — T028–T039)
**Goal**: The Tools view lets users search, filter, group, and inspect Cabal tool catalog data with rich backend-fed metadata and status state.

**Independent Test**: Load the Tools view, search for known tools, filter by category/status/source/install channel, open a detail panel, and verify metadata matches `cabal.tool_catalog` and `/api/tools`.

### Tests for User Story 2

- [X] T028 [P] [US2] Add /api/tools contract tests for category objects, required tool fields, status counts, source counts, and install-channel counts in tests/contract/test_cabal_web_api_contract.py — Owner: @python-tester
- [X] T029 [P] [US2] Add tool serializer unit tests for ToolCategoryView and ToolItemView mapping from cabal.tool_catalog in tests/unit/test_cabal_web_serializers.py — Owner: @python-tester
- [X] T030 [P] [US2] Add frontend Tools view integration tests for search/filter controls, empty states, status labels, and detail drawer hooks in tests/integration/test_cabal_web_assets.py — Owner: @python-tester

### Implementation for User Story 2

- [X] T031 [US2] Implement ToolCategoryView, ToolItemView, and ToolCatalogPayload serializers in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T032 [US2] Implement tool status mapping for installed, missing, update_available, unsupported, manual_required, source_unavailable, loading, and error in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T033 [US2] Implement /api/tools route using cabal.tool_catalog, cabal.tools, and safe status probes in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T034 [US2] Add Tools view markup for category rail, search, filters, counts, results list, and detail drawer in setup/src/cabal/web/assets/index.html — Owner: @frontend-architect
- [X] T035 [US2] Implement Tools view state, search, category/status/source/install-channel filters, result counts, empty state, and detail selection in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T036 [US2] Render tool badges, source-link states, platform support, version metadata state, backup policy, safety notes, and redacted status details in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T037 [US2] Style Tools category rail, dense result rows, status badges, filters, and detail drawer in setup/src/cabal/web/assets/styles.css — Owner: @frontend-css
- [X] T038 [US2] Add integration test that /api/tools contains no raw token-shaped fixture values and contains all required catalog keys in tests/integration/test_cabal_web_server.py — Owner: @python-tester
- [X] T039 [US2] Update quickstart Tools verification scenario in specs/011-cabal-web-ui/quickstart.md — Owner: main

**Checkpoint**: User Stories 1 and 2 work independently; the web UI can serve as a read-only Tools catalog explorer.

---

## Phase 5: User Story 3 - Inspect Knowledge and Project Health (Priority: P2)

**Status**: ✅ Complete (13/13 — T040–T052)
**Goal**: The web app exposes OKF graph summaries and current project dashboard health with search, filters, evidence, and safe section rendering.

**Independent Test**: Open Knowledge and Project Health, verify graph-present and graph-missing states, filter graph concepts/relations, and confirm Git/GitHub/Supabase/Vercel sections render availability states without secrets.

### Tests for User Story 3

- [X] T040 [P] [US3] Add /api/knowledge contract tests for graph-present, graph-missing, counts, nodes, edges, and evidence fields in tests/contract/test_cabal_web_api_contract.py — Owner: @python-tester
- [X] T041 [P] [US3] Add /api/project-health contract tests for Git, GitHub, Supabase, Vercel section fields and token-free links in tests/contract/test_cabal_web_api_contract.py — Owner: @python-tester
- [X] T042 [P] [US3] Add KnowledgeGraphPayload and ProjectHealthPayload serializer unit tests in tests/unit/test_cabal_web_serializers.py — Owner: @python-tester
- [X] T043 [P] [US3] Add frontend Knowledge and Project Health asset tests for search/filter controls, graph empty state, and section state labels in tests/integration/test_cabal_web_assets.py — Owner: @python-tester

### Implementation for User Story 3

- [X] T044 [US3] Implement KnowledgeGraphPayload, KnowledgeNode, KnowledgeEdge, EvidenceItem, and KnowledgeCounts serializers in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T045 [US3] Implement ProjectHealthPayload and ProjectSection serializers from cabal.models.dashboard in setup/src/cabal/web/serializers.py — Owner: @python-architect
- [X] T046 [US3] Implement /api/knowledge route using docs/okf/prompt-lib/graph.json with successful empty state when missing in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T047 [US3] Implement /api/project-health route using existing dashboard collectors with repo-root default project scope in setup/src/cabal/web/api.py — Owner: @python-architect
- [X] T048 [US3] Add Knowledge and Project Health markup for controls, summaries, graph lanes, inspectors, and section panels in setup/src/cabal/web/assets/index.html — Owner: @frontend-architect
- [X] T049 [US3] Implement Knowledge search, node-type filter, relation filter, route inspector, and missing-graph state in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T050 [US3] Implement Project Health section rendering for Git, GitHub, Supabase, Vercel facts, hints, links, and availability states in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T051 [US3] Style Knowledge graph lanes, evidence inspector, and Project Health section states in setup/src/cabal/web/assets/styles.css — Owner: @frontend-css
- [X] T052 [US3] Add integration test that Knowledge and Project Health endpoints redact token-shaped fixture values in tests/integration/test_cabal_web_server.py — Owner: @python-tester

**Checkpoint**: User Stories 1, 2, and 3 work independently; the web UI connects Tools, OKF knowledge, and project health.

---

## Phase 6: User Story 4 - Use a Polished Dark Application Shell (Priority: P2)

**Status**: ✅ Complete (8/8 — T053–T060)
**Goal**: The whole app feels like a focused modern dark operational tool with responsive layouts and distinct interaction states.

**Independent Test**: View the app at desktop and narrow widths and verify navigation, panels, controls, graph/list views, loading/error states, buttons, and detail drawers stay readable without overlap or clipping.

### Tests for User Story 4

- [X] T053 [P] [US4] Add static CSS regression checks for no external fonts, no orb/blob decorations, stable responsive breakpoints, and required state class names in tests/integration/test_cabal_web_assets.py — Owner: @python-tester
- [X] T054 [P] [US4] Add frontend accessibility/static checks for focusable navigation, buttons, aria labels, and semantic regions in tests/contract/test_cabal_web_frontend_contract.py — Owner: @python-tester

### Implementation for User Story 4

- [X] T055 [US4] Refine global dark theme tokens, neutral surfaces, accent colors, success/warning/error/info states, and typography in setup/src/cabal/web/assets/styles.css — Owner: @frontend-css
- [X] T056 [US4] Refine responsive layout rules for side navigation, detail drawers, filters, dense tables/lists, and narrow widths in setup/src/cabal/web/assets/styles.css — Owner: @frontend-css
- [X] T057 [US4] Add keyboard-visible focus behavior, accessible names, disabled/loading/error button states, and safe external-link indicators in setup/src/cabal/web/assets/index.html — Owner: @frontend-architect
- [X] T058 [US4] Add frontend helpers for redacted copy text, selected text behavior, and safe external link opening in setup/src/cabal/web/assets/app.js — Owner: @frontend-architect
- [X] T059 [US4] Update quickstart manual visual checklist with desktop and narrow viewport acceptance steps in specs/011-cabal-web-ui/quickstart.md — Owner: main
- [X] T060 [US4] Document final MVP read-only constraints and deferred mutation-safety design in specs/011-cabal-web-ui/plan.md — Owner: main

**Checkpoint**: All user stories are complete and the web UI is visually ready for repeated local use.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Status**: ✅ Complete (7/7 — T061–T067)
**Purpose**: Final verification, compatibility, packaging, and audit tasks that span multiple stories.

- [X] T061 [P] Run focused web test suite from quickstart.md and record command results in specs/011-cabal-web-ui/quickstart.md — Owner: @python-tester
- [X] T062 [P] Run existing Cabal-focused tests for tool catalog, dashboard services, OKF behavior, and web-adjacent assets in tests/contract/, tests/unit/, tests/integration/, and setup/tests/ — Owner: @python-tester
- [X] T063 Verify no committed raw token-shaped values exist in setup/src/cabal/web/, tests/contract/test_cabal_web_*.py, tests/unit/test_cabal_web_*.py, and tests/integration/test_cabal_web_*.py — Owner: main
- [X] T064 Verify `python -m cabal.web --host 127.0.0.1 --port 8765 --project .` starts and serves the app according to specs/011-cabal-web-ui/quickstart.md — Owner: @python-tester
- [X] T065 Update setup/build/cabal.spec and setup/pyproject.toml if needed so static assets ship with source and packaged Cabal builds — Owner: @python-architect
- [X] T066 Perform manual desktop and narrow viewport visual verification and capture findings in specs/011-cabal-web-ui/quickstart.md — Owner: main
- [X] T067 Run final read-only `@code-plan-verifier` audit against specs/011-cabal-web-ui/plan.md and specs/011-cabal-web-ui/tasks.md — Owner: @code-plan-verifier

**Verification note**: Focused web suite passed. Existing Cabal regression slice was run and recorded in quickstart.md; it has two pre-existing OKF CLI contract failures for `index`/`analytics` commands that are not exposed by the current `cabal.okf` CLI.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can be implemented after or alongside US1 only with worktree isolation.
- **User Story 3 (Phase 5)**: Depends on Foundational completion; benefits from US1 navigation and shared fetch state.
- **User Story 4 (Phase 6)**: Depends on at least US1 and is best finalized after US2/US3 surfaces exist.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories after Foundational; suggested MVP.
- **User Story 2 (P1)**: No data dependency on US1, but uses the shared app shell and fetch helpers from US1 for best incremental delivery.
- **User Story 3 (P2)**: Uses shared shell/fetch helpers from US1 and patterns from US2 detail inspectors.
- **User Story 4 (P2)**: Cross-cutting visual polish across all implemented views.

### Within Each User Story

- Contract/static tests first and expected to fail before implementation.
- Serializers before API route composition.
- API route composition before frontend rendering that consumes the route.
- HTML structure before JavaScript render targets.
- CSS polish after HTML/JS states are in place.

### Parallel Opportunities

- `[P]` test tasks in the same phase touch different files or independent assertions and can run in parallel if dispatched with worktree isolation.
- Serializer and frontend tasks should remain sequential in MVP because they share response shapes and DOM state names.
- No task is marked `Parallel: yes` in this plan because the accepted plan calls for sequential implementation.

---

## Parallel Example: User Story 2

```text
Task: "Add /api/tools contract tests for category objects, required tool fields, status counts, source counts, and install-channel counts in tests/contract/test_cabal_web_api_contract.py"
Task: "Add tool serializer unit tests for ToolCategoryView and ToolItemView mapping from cabal.tool_catalog in tests/unit/test_cabal_web_serializers.py"
Task: "Add frontend Tools view integration tests for search/filter controls, empty states, status labels, and detail drawer hooks in tests/integration/test_cabal_web_assets.py"
```

If these are dispatched concurrently, each writing agent must use worktree isolation even though the task list does not preselect parallel dispatch.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Stop and validate the local backend plus browser Overview independently.

### Incremental Delivery

1. Setup + Foundation establishes safe localhost read API.
2. US1 delivers the browser dashboard MVP.
3. US2 adds the high-value Tools catalog explorer.
4. US3 connects Knowledge and Project Health.
5. US4 polishes the dark operational application experience.

### Sequential Team Strategy

1. `@python-tester` writes failing contracts.
2. `@python-architect` implements backend helpers/routes.
3. `@frontend-architect` implements vanilla UI behavior.
4. `@frontend-css` polishes the dark UI and responsive states.
5. `main` handles quickstart/docs/read-only decisions.
6. `@code-plan-verifier` audits before commit.

## Notes

- Do not add frontend framework tooling unless the plan is amended.
- Do not expose browser-triggered mutation endpoints in MVP.
- Keep all backend payloads redacted before they reach JavaScript.
- Preserve the existing Cabal Textual UI behavior while adding the web surface.
