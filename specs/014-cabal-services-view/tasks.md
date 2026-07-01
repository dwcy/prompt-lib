---

description: "Task list for 014-cabal-services-view"
---

# Tasks: Local Agent Services in the Cabal UI

**Input**: Design documents from `/specs/014-cabal-services-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/internal-interfaces.md, quickstart.md

**Tests**: Included — `contracts/internal-interfaces.md` defines test obligations and `quickstart.md` lists a pytest run. These are **unit/integration** tests (no external protocol surface; Constitution Gate 3 = N/A), owned by `@python-tester`.

**Organization**: Grouped by user story (US1 → US2 → US3) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: Different file, no dependency on an incomplete task (could be parallelized).
- **Owner**: Named subagent from `.specify/memory/agents.md`.
- **Parallel: yes**: dispatched concurrently → requires `isolation: "worktree"`. **None in this feature** — all writing dispatched sequentially to a single specialist (`@python-architect`), so Gate 6 = N/A. `[P]` here means "independent file", not "dispatch concurrently".

## Constitution gate notes

- Gate 1/3 (protocol/contract tests): **N/A** — no wire protocol. Tests are ordinary unit/integration tests.
- Gate 4 (reversibility): **N/A** — all paths under `setup/src/cabal/`; no `global/` change.
- Gate 6 (parallel isolation): **N/A** — sequential single-writer dispatch; no `Parallel: yes` task.

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (1/1 — T001–T001)
**Purpose**: Create the data structures every later phase builds on.

- [X] T001 Create `setup/src/cabal/service_catalog.py` with module docstring, `ServiceStatus` enum (NOT_SET_UP / STOPPED / RUNNING / BLOCKED / INFO_ONLY), `InstallKind` enum, and the `ServiceDefinition` (frozen), `ServiceState`, `PrereqResult` dataclasses per data-model.md — no seed data yet — Owner: @python-architect

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (4/4 — T002–T005)
**Purpose**: Registry seed + read-only status path that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `SERVICE_DEFINITIONS` seed (orchestrator, a2a-bridge, mcp-bus) + `SERVICE_BY_KEY`, `all_services()`, `get_service()`, and `validate_catalog()` enforcing data-model validation rules in `setup/src/cabal/service_catalog.py` (orchestrator.depends_on=("a2a-bridge",); mcp-bus runnable=False, dashboard_command=None) — Owner: @python-architect
- [X] T003 [P] Unit test `tests/test_service_catalog.py` — `validate_catalog()` passes; seed invariants (3 services, mcp-bus info-only, orchestrator→a2a-bridge dependency) — Owner: @python-tester
- [X] T004 Create `setup/src/cabal/service_prereqs.py` with module docstring, `is_set_up(key)` (PATH probe via `shutil.which(console_name)`) and a `check(key) -> list[PrereqResult]` skeleton returning `[]` for now — Owner: @python-architect
- [X] T005 Create `setup/src/cabal/service_supervisor.py` read-only core: in-memory `dict[str, ServiceState]`, `status(key)`, `statuses()`, `reconcile(key)` with liveness probe (PID `poll()` / port-open for a2a-bridge / `which` for set-up), `INFO_ONLY` for mcp-bus; no start/stop yet — Owner: @python-architect

**Checkpoint**: Registry + status read available — US1 can render real statuses.

---

## Phase 3: User Story 1 - See the local agent services in one place (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (4/4 — T006–T009)
**Goal**: All three services shown together with description, run command, source, status, and the orchestrator→a2a-bridge dependency; no start/stop needed.

**Independent Test**: Launch the wizard, open Local Agent Services, confirm three grouped rows each with name, description, run command, source link, and a current status; mcp-bus has no Start control.

- [X] T006 [US1] Create `setup/src/cabal/views/services.py` `ServicesScreen` (Textual `Screen`, module docstring): compose a "Local Agent Services" group with one row per service showing label, description, `run_command`, source link, and a status Static; render orchestrator's dependency on a2a-bridge; mcp-bus row info-only (no Start/Stop). `render`-safe helper names per python.md Textual rules; no `subprocess` in the view — Owner: @python-architect
- [X] T007 [US1] Wire `setup/src/cabal/views/home.py`: add a "Local Agent Services" section + button and push `ServicesScreen` from `on_button_pressed` (depends on T006) — Owner: @python-architect
- [X] T008 [P] [US1] Textual smoke test `tests/test_services_screen.py` using `App.run_test()` + `pilot.pause()`: screen mounts, renders three rows, mcp-bus row has no Start button — Owner: @python-tester
- [X] T009 [US1] Add status-refresh worker to `ServicesScreen` (on mount / on_screen_resume) calling `service_supervisor.statuses()` and updating each row's status Static (depends on T005, T006) — Owner: @python-architect

**Checkpoint**: US1 fully functional — maintainer can see and understand all three services. MVP shippable.

---

## Phase 4: User Story 2 - Start and stop a runnable service (Priority: P2)

**Status**: ✅ Complete (5/5 — T010–T014)
**Goal**: Start/stop orchestrator and a2a-bridge from cabal with live status and actionable messages on missing prerequisites; mcp-bus excluded.

**Independent Test**: Start a2a-bridge → running; stop → stopped. Start with `A2A_BEARER_TOKEN` unset → blocked with actionable message (no crash). Start orchestrator with a2a-bridge down → blocked noting the dependency.

- [X] T010 [US2] Implement `service_prereqs.check(key)`: a2a-bridge (`A2A_BEARER_TOKEN` set, agent target present), orchestrator (gh auth, ntfy reachable, a2a-bridge peer reachable/running) — each unmet returns `PrereqResult(ok=False, message=<actionable>)` mapping the services' deterministic exit causes; in `setup/src/cabal/service_prereqs.py` (depends on T004) — Owner: @python-architect
- [X] T011 [US2] Extend `service_supervisor.py`: `start(key)` (run `check` first → spawn **detached** via `subprocess.Popen` with `CREATE_NEW_PROCESS_GROUP`, track pid → `RUNNING`; on unmet prereq → `BLOCKED` with joined messages, no spawn) and `stop(key)` (`terminate()`→`kill()` escalation on tracked pid → `STOPPED`); no-op safe for non-running / mcp-bus (depends on T005, T010) — Owner: @python-architect
- [X] T012 [P] [US2] Unit test `tests/test_service_supervisor.py` driving the state machine with a dummy long-running child (python sleeper): start→RUNNING, stop→STOPPED, external-exit→reconcile→STOPPED (no stale RUNNING), prereq-fail→BLOCKED (no spawn), mcp-bus→INFO_ONLY — Owner: @python-tester
- [X] T013 [P] [US2] Unit test `tests/test_service_prereqs.py`: missing `A2A_BEARER_TOKEN` → `ok is False` with non-empty message; set → `ok is True` — Owner: @python-tester
- [X] T014 [US2] Add Start/Stop buttons + handlers to `ServicesScreen` wired to `service_supervisor` via workers (no `subprocess` in the view); surface `BLOCKED` reason text; reflect dependency ordering in the message (depends on T011, T006) — Owner: @python-architect

**Checkpoint**: US1 + US2 work — maintainer can run services from the wizard with clear failures.

---

## Phase 5: User Story 3 - Prepare a service and reach its native view (Priority: P3)

**Status**: ✅ Complete (5/5 — T015–T019)
**Goal**: Set up a not-yet-installed service from cabal; open orchestrator's dashboard / surface a2a-bridge logs.

**Independent Test**: Setup a not-installed service → status moves to ready/stopped. Open orchestrator dashboard → `orchestrator dash` runs and returns to cabal; a2a-bridge shows a log pointer.

- [X] T015 [P] [US3] Create `setup/src/cabal/installers/a2a_bridge.py`: `a2a_bridge_install()` (uv tool install/upgrade from `REPO_DIR/services/a2a-bridge`, git-subdir fallback) and `a2a_bridge_status()` (PATH presence), `(bool, str)` shape like `installers/mcp_bus.py`; actionable message when `uv` missing — Owner: @python-architect
- [X] T016 [P] [US3] Create `setup/src/cabal/installers/orchestrator.py`: `orchestrator_install()` / `orchestrator_status()` (same pattern from `REPO_DIR/services/orchestrator`, ensuring the a2a-bridge path dependency resolves) — Owner: @python-architect
- [X] T017 [US3] Add a "Setup" action to `ServicesScreen` for `NOT_SET_UP` services calling the matching installer via a worker; refresh status on completion (depends on T015, T016, T014) — Owner: @python-architect
- [X] T018 [US3] Add "Open dashboard" for orchestrator via `App.suspend()` → run `orchestrator dash`, returning to cabal on exit; show a `log_hint` pointer for a2a-bridge (depends on T006) — Owner: @python-architect
- [X] T019 [P] [US3] Unit test `tests/test_service_installers.py`: installer returns `(False, <actionable>)` when `uv` is unavailable; status reflects PATH presence (monkeypatched) — Owner: @python-tester

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Status**: ✅ Complete (4/4 — T020–T023)
**Purpose**: Discipline, validation, and an independent audit before commit.

- [X] T020 [P] Verify python.md size discipline across new modules (each under soft cap, one responsibility, no `subprocess` in `views/services.py`) and add/confirm module docstrings — Owner: @python-architect
- [X] T021 Run `quickstart.md` validation: launch the wizard, confirm the three rows + statuses; run `python -m pytest tests/test_service_catalog.py tests/test_service_supervisor.py tests/test_service_prereqs.py tests/test_services_screen.py tests/test_service_installers.py -q` — Owner: main
- [X] T022 [P] Read-only plan-compliance audit of the implementation (verdict + findings) — Owner: @code-plan-verifier
- [X] T023 Confirm Tools/MCP screens unchanged (FR-012): mcp-bus still renders in the Tools MCP group; no regression — Owner: main

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 — no dependencies.
- **Foundational (Phase 2)**: T002–T005 depend on T001; **blocks all user stories**.
- **US1 (Phase 3)**: depends on Phase 2 (T005 for status, T002 for catalog).
- **US2 (Phase 4)**: depends on Phase 2 + T006 (screen exists).
- **US3 (Phase 5)**: depends on T006 + T014.
- **Polish (Phase 6)**: after all desired stories.

### Critical path

T001 → T002 → T005 → T006 → T007/T009 (US1 MVP) → T010 → T011 → T014 (US2) → T017/T018 (US3) → T020–T023.

### Within each story

- Models/data before services; services before view wiring.
- Tests ([P]) authored against the module they cover; run after the module exists.
- Same-file tasks are sequential (e.g. T005 then T011 both edit `service_supervisor.py`).

### Parallel opportunities (file-independent; still dispatched sequentially here)

- T003 (test) is file-independent from T002's module edit but validates it — run after.
- T012, T013, T019 are different test files — independent of each other.
- T015, T016 are different installer files — independent.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (T001) → Phase 2 (T002–T005) → Phase 3 (T006–T009).
2. **STOP and VALIDATE**: maintainer can see all three services with live status.
3. Commit the MVP slice.

### Incremental Delivery

1. Setup + Foundational → registry + status read ready.
2. US1 → see services (MVP) → commit.
3. US2 → start/stop + prereqs → commit.
4. US3 → setup + dashboard → commit.
5. Polish → audit + quickstart validation → commit.

### Dispatch note (Gate 6)

All implementation tasks go to `@python-architect` sequentially; test tasks to `@python-tester` after their target module exists; `@code-plan-verifier` for the read-only audit. No concurrent writers → no worktree isolation needed.

---

## Notes

- [P] = different file, independent; not a directive to dispatch concurrently here.
- Owner field maps each task to a named subagent from `.specify/memory/agents.md`.
- Commit after each story checkpoint (per global git rules + auto-commit at plan completion).
- `views/services.py` must never call `subprocess` directly — all process I/O via `service_supervisor` / installers (python.md).
