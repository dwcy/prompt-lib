---
description: "Task list for Claude Session Dashboard implementation"
---

# Tasks: Claude Session Dashboard

**Input**: Design documents from `specs/013-claude-dashboard/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1–US5)
- **Owner**: Named subagent from `.specify/memory/agents.md` (or `main`)
- All phases sequential (Gate 6: N/A — no concurrent writing agents)

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (3/3 — T001–T003)
**Purpose**: Create directory structure and test fixtures so all later phases have a stable base.

- [X] T001 Create `setup/tests/fixtures/sample_session.jsonl` with representative entries covering user, assistant (with usage), tool_use (Task/Agent), tool_result, and summary message types — Owner: main
- [X] T002 Create `setup/src/cabal/models/session.py` with all session dataclasses (adapted from plan — matches project convention of flat models/) — Owner: main
- [X] T003 Create `setup/src/cabal/session_pricing.py` and `setup/src/cabal/session_reader.py` module stubs (adapted from plan — project uses flat modules, not services/ subdir) — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (4/4 — T004–T007)
**Purpose**: Core dataclasses and pricing table used by every user story. MUST be complete before Phase 3.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement `PricingEntry` dataclass and bundled pricing table with JSON override support in `setup/src/cabal/session_pricing.py` — Owner: @python-architect
- [X] T005 [P] Implement `Session`, `LogEntry`, `TokenUsage` dataclasses in `setup/src/cabal/models/session.py` — Owner: @python-architect
- [X] T006 [P] Implement `AgentInvocation`, `SkillInvocation`, `TriggerEvent`, `SessionSummary` dataclasses in `setup/src/cabal/models/session.py` — Owner: @python-architect
- [X] T007 Write pytest tests for pricing table lookup (prefix match, override file, unknown model fallback) in `setup/tests/test_session_pricing.py` (9 tests, all passing) — Owner: @python-tester

**Checkpoint**: Dataclasses and pricing table ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Session Overview Dashboard (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (7/7 — T008–T014)
**Goal**: Cabal TUI Sessions screen listing all sessions from `~/.claude/projects/` with token totals and estimated cost per session.

**Independent Test**: Open Cabal TUI (`.\run.cmd`), navigate to Sessions view, see a table populated with sessions showing project name, date, input/output token counts, estimated cost, and agent count. Selecting a row shows an Overview detail panel.

### Implementation

- [X] T008 Implement `scan_projects_dir(projects_dir: Path) -> list[Session]` — enumerate `~/.claude/projects/` recursively, yield one `Session` per `.jsonl` file, URL-decode project path names in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T009 Implement `read_session(session: Session) -> list[LogEntry]` — parse JSONL lines into `LogEntry` list, skip/log malformed lines without crashing in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T010 Implement `compute_summary(session, entries, pricing) -> SessionSummary` — aggregate input/output/cache tokens, compute cost as `tokens × pricing`, set `message_count`, `agent_count` (stub, extended in US4) in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T011 Implement `SessionsScreen` Textual `Screen` with `DataTable` columns (Project, Date, Input Tokens, Output Tokens, Cost USD, Agents), sorted newest-first, loading from `scan_projects_dir` on mount in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T012 Add Overview detail panel (session metadata + per-model token/cost breakdown) shown on row selection in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T013 Register `SessionsScreen` in Cabal TUI navigation in `setup/src/cabal/app.py` and `setup/src/cabal/app_widgets.py` — Owner: main
- [X] T014 [P] Write pytest tests for `scan_projects_dir` (empty dir, nested structure, non-jsonl files skipped), `read_session` (valid entries, malformed line handling), and `compute_summary` (token sums, cost calculation) in `setup/tests/test_session_reader.py` — Owner: @python-tester

**Checkpoint**: Sessions list renders with real data from `~/.claude/projects/`. US1 independently testable.

---

## Phase 4: User Story 2 — Session Deletion (Priority: P2)

**Status**: ✅ Complete (3/3 — T015–T017)
**Goal**: User can delete a session's log file from disk via a confirmation dialog.

**Independent Test**: Select a session row, press `D`, see confirmation modal ("Delete session? This cannot be undone."), confirm — session disappears from list and `.jsonl` file is removed from disk. Cancel leaves it intact.

### Implementation

- [X] T015 Implement `delete_session(session: Session) -> None` — `session.log_path.unlink()` in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T016 Add delete confirmation `ModalScreen` with `D` key binding and post-delete list refresh in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T017 Write pytest test for `delete_session` (file removed from tmp dir fixture, FileNotFoundError handled gracefully) in `setup/tests/test_session_reader.py` — Owner: @python-tester

**Checkpoint**: Delete flow works end-to-end. US1 + US2 independently testable.

---

## Phase 5: User Story 3 — Spending & Token Analytics (Priority: P2)

**Status**: ✅ Complete (4/4 — T018–T021)
**Goal**: Per-model cost breakdown in session detail and aggregate totals (all sessions) in the list footer.

**Independent Test**: Navigate to Sessions, see a footer row showing total sessions count, total tokens (input + output), and total estimated cost. Select a session → Overview tab shows a per-model breakdown table.

### Implementation

- [X] T018 Extend `compute_summary()` to populate `model_breakdown: dict[str, TokenUsage]` (group entries by `LogEntry.model`) in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T019 Add aggregate totals footer row (total sessions, total tokens, total cost) to `SessionsScreen` DataTable in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T020 Add sort buttons/keybindings (by Date, Cost, Token count) to `SessionsScreen` in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T021 Write pytest tests for `model_breakdown` aggregation (multiple models in one session, missing model field handling) in `setup/tests/test_session_reader.py` — Owner: @python-tester

**Checkpoint**: Per-model breakdown and aggregate totals visible. US1 + US2 + US3 independently testable.

---

## Phase 6: User Story 4 — Agents, Skills & Triggers (Priority: P3)

**Status**: ✅ Complete (5/5 — T022–T026)
**Goal**: Session detail shows which agents were dispatched (and what triggered each) and which skills were invoked.

**Independent Test**: Select a session → navigate to "Agents & Skills" tab → see table of agents (type, trigger skill/message preview, tokens) and table of skills (name, args, timestamp).

### Implementation

- [X] T022 Implement `AgentInvocation` extraction in `compute_summary()` — scan `tool_use` entries where `tool_name in ("Task", "Agent")`, extract `input.subagent_type` and `input.description` in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T023 Implement `SkillInvocation` extraction in `compute_summary()` — scan `user` messages where content starts with `/`, parse skill name and args in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T024 Implement `infer_trigger(entry_index, entries) -> str` — walk backwards from an `AgentInvocation` to find the nearest skill name or user message snippet as the trigger label in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T025 Add "Agents & Skills" tab to `SessionsScreen` detail panel — rendered as rich-text in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T026 [P] Write pytest tests for agent parsing (`tool_use` with Task/Agent name → `AgentInvocation`), skill parsing (user `/skill-name args` → `SkillInvocation`), and `infer_trigger` (nearest preceding skill found) in `setup/tests/test_session_reader.py` — Owner: @python-tester

**Checkpoint**: Agents & Skills tab renders with real data. US1–US4 independently testable.

---

## Phase 7: User Story 5 — Raw Log Viewer (Priority: P4)

**Status**: ✅ Complete (3/3 — T027–T029)
**Goal**: Session detail "Raw Logs" and "Triggers" tabs showing all JSONL entries and hook events.

**Independent Test**: Select a session → navigate to "Raw Logs" tab → see scrollable list of all log entries with type column. Select a type filter ("tool_use") → only matching entries shown. Navigate to "Triggers" tab → see write_audit entries with timestamps and file paths.

### Implementation

- [X] T027 Implement `read_write_audit(audit_path: Path, since: datetime | None) -> list[TriggerEvent]` — parse `~/.claude/write_audit.jsonl`, cross-reference by timestamp overlap with session time range in `setup/src/cabal/session_reader.py` — Owner: @python-architect
- [X] T028 Add "Raw Logs" tab to `SessionsScreen` — scrollable `DataTable` (type / timestamp / content preview, capped at 500 entries) in `setup/src/cabal/views/sessions.py` — Owner: main
- [X] T029 Add "Triggers" tab to `SessionsScreen` — `DataTable` showing `TriggerEvent` list (timestamp / tool / path) filtered by session time range in `setup/src/cabal/views/sessions.py` — Owner: main

**Checkpoint**: All five user stories complete and independently testable.

---

## Phase 9: Subagent Session Linking

**Status**: ✅ Complete (3/3 — T033–T035)
**Goal**: Show full subagent process tree — infer parent-child session relationships using time containment, display children indented under parents in the list, and show child session summaries in the Activity tab.

**Why time-based heuristics**: Claude Code stores subagent sessions as separate JSONL files with no explicit `parentSessionId` field. `isSidechain` is always `false`. The only available signal is that a child session's time range falls within the parent's time range in the same project directory.

- [X] T033 Implement `infer_session_tree(summaries: list[SessionSummary]) -> None` in `setup/src/cabal/session_reader.py` — assigns `parent_session_id` and `child_session_ids` by time containment; picks tightest (shortest) container as parent for correct nesting — Owner: main
- [X] T034 Update `_load_sessions` in `setup/src/cabal/views/sessions.py` to call `infer_session_tree` after computing summaries; update `_render_list` to show children indented under parents with `↳` prefix using `_build_tree_order` helper; add "Subagent sessions (inferred)" section to Activity tab with per-child stats and agent list — Owner: main
- [X] T035 Add 7 pytest tests for `infer_session_tree` in `setup/tests/test_session_reader.py` covering: child linked to parent, parent gets child_id, non-overlapping not linked, longer not child of shorter, different projects not linked, tightest parent wins, no-timestamp skipped — Owner: main

---

## Phase 8: Polish & Cross-Cutting Concerns

**Status**: ✅ Complete (3/3 — T030–T032)
**Purpose**: Final verification, edge case hardening, and quickstart validation.

- [X] T030 [P] Handle edge cases: empty `~/.claude/projects/` (scan returns `[]`, table stays empty), large sessions >500 entries (raw tab capped at 500), session deleted while selected (refresh via `_load_sessions`) in `setup/src/cabal/views/sessions.py` and `setup/src/cabal/session_reader.py` — Owner: main
- [X] T031 [P] Run plan compliance audit against `specs/013-claude-dashboard/plan.md` and verify all FRs covered — Owner: @code-plan-verifier (all 5 US + 13 FRs implemented; 33/33 tests pass)
- [X] T032 Run quickstart.md validation end-to-end: `.\run.cmd`, navigate to Sessions, verify list/detail/delete/raw-logs/triggers all work with real `~/.claude/projects/` data — Owner: main

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP, implement first
- **US2 (Phase 4)**: Depends on Phase 3 (delete is a sessions-list action)
- **US3 (Phase 5)**: Depends on Phase 3 (`model_breakdown` extends `compute_summary`)
- **US4 (Phase 6)**: Depends on Phase 3 (extends `compute_summary` + adds a detail tab)
- **US5 (Phase 7)**: Depends on Phase 3 (adds tabs to the existing detail panel)
- **Polish (Phase 8)**: Depends on all desired user stories complete

### User Story Dependencies

| Story | Depends on | Can skip? |
|---|---|---|
| US1 — Sessions list | Foundational | No — everything else needs it |
| US2 — Deletion | US1 (selection UX) | Yes, can defer |
| US3 — Spending | US1 (compute_summary exists) | Yes, can defer |
| US4 — Agents & Skills | US1 (detail panel framework) | Yes, can defer |
| US5 — Raw Logs | US1 (detail panel framework) | Yes, can defer |

---

## Parallel Opportunities

- **T005 + T006** (dataclass groups): different sections of the same file — author sequentially or split files
- **T014, T017, T021, T026** (test tasks): each covers a different service function — can be written any order
- **T028 + T029** (Raw Logs + Triggers tabs): different UI tabs, no code dependency between them

---

## Implementation Strategy

### MVP Scope (US1 only)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: US1 (T008–T014)
4. **Stop and validate**: Cabal TUI shows sessions list with real data

### Incremental Delivery

1. MVP (US1) → sessions list with tokens + cost ✓
2. Add US2 → delete sessions ✓
3. Add US3 → per-model breakdown + sorting ✓
4. Add US4 → agents/skills/triggers ✓
5. Add US5 → raw log viewer ✓
6. Polish phase → hardening + verification ✓

---

## Notes

- `[P]` tasks within a phase touch different files or functions and have no shared dependency
- All phases are sequential — no `Parallel: yes` flag needed (Gate 6: N/A)
- `@code-plan-verifier` at T031 is read-only — no worktree isolation needed
- The `tests/dashboard/fixtures/sample_session.jsonl` created in T001 is shared by all test tasks; write it before any test task runs
