---

description: "Task list for GitHub Issue Triage Orchestrator (v1)"
---

# Tasks: GitHub Issue Triage Orchestrator (v1)

**Input**: Design documents from `/specs/003-issue-triage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Constitution**: `.specify/memory/constitution.md` v1.1.0 — contract test for `gh issue list --json` (Gate 3) is NON-NEGOTIABLE; T004 must be written and observed FAILING before T009 begins.

**Tests**: Included — contract test (Gate 3 mandatory), unit tests (matching 002 convention), integration test (INTEGRATION=1 gated).

**Organization**: Tasks grouped by user story; US1 is the MVP vertical slice.

## Format: `[ID] [P?] [Story] Description — file — Owner: @<agent>`

- **[P]**: Parallelizable (different files, no incomplete task dependencies)
- **[Story]**: US1–US4 map to spec.md user stories
- **Owner**: Named subagent from `.specify/memory/agents.md`
- Every implementation task includes the exact file path it produces or modifies

## Phase status convention

Every `## Phase X` heading is followed immediately by a `**Status**:` line — recompute on every checkbox change.

---

## Phase 1: Setup (Foundational Modifications)

**Status**: ✅ Complete (3/3 — T001–T003)
**Purpose**: Extend existing infrastructure in `services/orchestrator/` — no new files yet; all modifications are backward-compatible.

- [X] T001 Extend `TriggerEvent.kind` Literal to add `"issue.opened"` and add `@model_validator(mode="after")` that skips the 40-char hex check on `head_sha` when `kind == "issue.opened"` — `services/orchestrator/src/orchestrator/triggers/base.py` — Owner: @python-architect
- [X] T002 [P] Add `orchestrator_enable_issue_triage: bool = False` field to `Config` (env var `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE`) — `services/orchestrator/src/orchestrator/config.py` — Owner: @python-architect
- [X] T003 [P] Add `issue_cursor` table (`issue_number INTEGER PRIMARY KEY, repo TEXT NOT NULL, triaged_at TEXT NOT NULL`) to the `eventlog.py` schema migration (`_ensure_schema()`) — `services/orchestrator/src/orchestrator/eventlog.py` — Owner: @python-architect

---

## Phase 2: Foundational (Gate 3 — Contract Test + Conftest)

**Status**: ✅ Complete (2/2 — T004–T005)
**Purpose**: Satisfy Constitution Gate 3 and extend test fixtures. **T004 MUST be written and verified FAILING before T009 begins.**

**⚠️ CRITICAL**: T004 is a Gate 3 requirement — do not start Phase 3 implementation until T004 exists and fails.

- [X] T004 Write contract test verifying `gh issue list --json number,title,body,labels,author,createdAt,state` output matches the schema in `contracts/gh-issue-list.contract.md`: asserts array type, required fields, `labels[].name` is a string, `author.login` is a string, `createdAt` is ISO-8601, tolerates extra fields — `services/orchestrator/tests/contract/test_gh_issue_list_schema.py` — Owner: @python-tester
- [X] T005 [P] Extend `conftest.py` `fake_gh` fixture to handle `gh issue list --json …` (return canned JSON array fixture) and `gh issue comment <n> --body -` (capture stdin, return exit 0) — `services/orchestrator/tests/conftest.py` — Owner: @python-tester

**Checkpoint**: Gate 3 satisfied — contract test exists and fails against a fake schema; conftest extended.

---

## Phase 3: User Story 1 — Issue Detection and Lead-Agent Triage (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (6/6 — T006–T011)
**Goal**: Daemon detects newly-opened issues on the watched repo and dispatches each to a peer Claude Code agent; agent produces a structured triage decision logged as `triage.decision`; run lifecycle events emitted.

**Independent Test**: `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=true uv run orchestrator serve` → open issue on test repo → within one poll interval, daemon logs contain `run.started`, `triage.decision`, `run.completed`.

### Tests first (write and verify FAILING before T009)

- [X] T006 [P] [US1] Unit test for `TriggerEvent(kind="issue.opened")`: validates, `head_sha="0"*40` is accepted, `pr_number` stores `issue_number`, extra payload fields allowed — extend `services/orchestrator/tests/unit/test_trigger_base.py` — Owner: @python-tester
- [X] T007 [P] [US1] Unit test for `GithubIssuesPollTrigger`: new issue emits `TriggerEvent(kind="issue.opened")` with correct payload fields; auth/rate-limit errors emit correct event kinds; empty list emits nothing — `services/orchestrator/tests/unit/test_github_issues_poll.py` — Owner: @python-tester
- [X] T008 [P] [US1] Unit test for `IssueTiageAgent` core: valid ` ```json ` block in agent output parsed into `TriageDecision`; `triage.decision` and `run.completed` events logged; unparseable response → `run.failed` — `services/orchestrator/tests/unit/test_issue_triage.py` — Owner: @python-tester

### Implementation

- [X] T009 [US1] Implement `GithubIssuesPollTrigger` (inherits `Trigger` Protocol): `__init__(repo, poll_seconds, eventlog_conn, notifier | None)`, `events()` async iterator polling `gh issue list --json …`, converts items to `TriggerEvent(kind="issue.opened")`, maps stderr patterns to event kinds matching `github_poll.py` conventions — `services/orchestrator/src/orchestrator/triggers/github_issues_poll.py` — Owner: @python-architect
- [X] T010 [US1] Implement `IssueTiageAgent.run(trigger_event)`: extract issue fields from `payload`, build triage prompt (system instruction + issue title/body/labels/author truncated to 4000 chars), stream `DelegationClient.delegate(prompt)`, collect output, extract first ` ```json ` block into `TriageDecision` dataclass, log `run.queued` / `run.started` / `agent.message` / `triage.decision` / `triage.routed` / `run.completed` / `run.failed` — `services/orchestrator/src/orchestrator/agents/issue_triage.py` — Owner: @python-architect
- [X] T011 [US1] Extract `_consume_trigger(trigger, dispatch_table, stop_event, semaphore)` helper from `daemon.py`'s `_consume()`; add issue trigger + agent construction behind `config.orchestrator_enable_issue_triage` guard; `asyncio.gather` both trigger tasks; extend `dispatch` dict with `"issue.opened": issue_agent` — `services/orchestrator/src/orchestrator/daemon.py` — Owner: @python-architect

**Checkpoint**: US1 fully functional. `pytest tests/unit/test_github_issues_poll.py tests/unit/test_issue_triage.py tests/contract/test_gh_issue_list_schema.py` passes.

---

## Phase 4: User Story 2 — GitHub Comment with Triage Summary (Priority: P2)

**Status**: ✅ Complete (2/2 — T012–T013)
**Goal**: After successful triage, daemon posts a structured comment on the GitHub issue. `gh issue comment` failure is non-fatal.

**Independent Test**: After triage, `gh issue view <n> --comments` shows a comment containing `category`, `severity`, `assessment`, `routing`.

### Tests first

- [X] T012 [US2] Unit test for `_post_comment()`: success path emits `gh.comment.posted`; non-zero `gh` exit emits `gh.comment.failed` warning and run still reaches `run.completed` — extend `services/orchestrator/tests/unit/test_issue_triage.py` — Owner: @python-tester

### Implementation

- [X] T013 [US2] Implement `_post_comment(issue_number, decision, repo)` in `IssueTiageAgent`: runs `gh issue comment <n> --repo <repo> --body -` with formatted comment body via stdin; on exit 0 emits `gh.comment.posted`; on non-zero emits `gh.comment.failed` and continues; call it after `triage.decision` event — `services/orchestrator/src/orchestrator/agents/issue_triage.py` — Owner: @python-architect

**Checkpoint**: US1 + US2 functional. Triage comment appears on test issue after successful run.

---

## Phase 5: User Story 3 — Phone Push Notifications (Priority: P2)

**Status**: ✅ Complete (2/2 — T014–T015)
**Goal**: Operator phone receives ntfy push at issue detection, triage complete, and triage failure. Reuses existing `Notifier` from `notifier.py`.

**Independent Test**: Configure ntfy topic, subscribe phone, open test issue → three notifications arrive (detected, complete/failed).

### Tests first

- [X] T014 [US3] Unit test for notification calls: `notifier.notify()` called with info level at `issue.detected`; info level at `triage.decision`; error level at `run.failed` — extend `services/orchestrator/tests/unit/test_issue_triage.py` — Owner: @python-tester

### Implementation

- [X] T015 [US3] Add `notifier.notify()` calls to `IssueTiageAgent.run()`: info-level "Issue #N detected: {title}" at run start; info-level "Triage complete: {category} / {routing}" on `triage.decision`; error-level "Triage failed: {error}" on `run.failed` — `services/orchestrator/src/orchestrator/agents/issue_triage.py` — Owner: @python-architect

**Checkpoint**: US1 + US2 + US3 functional. Phone receives three notifications per triage run.

---

## Phase 6: User Story 4 — Duplicate Suppression (Priority: P3)

**Status**: ✅ Complete (3/3 — T016–T018)
**Goal**: Already-triaged issues do not trigger a second dispatch on subsequent polls. `run.skipped` event emitted with `reason: already_triaged`.

**Independent Test**: After successful triage, trigger another poll cycle. Daemon log shows `run.skipped issue_number=N reason=already_triaged`; no second triage run starts.

### Tests first

- [X] T016 [US4] Unit test for `GithubIssuesPollTrigger` with already-triaged cursor: issue present in `issue_cursor` → not yielded; emits `run.skipped` — extend `services/orchestrator/tests/unit/test_github_issues_poll.py` — Owner: @python-tester

### Implementation

- [X] T017 [US4] Add `issue_cursor` query to `GithubIssuesPollTrigger.events()`: before yielding each `TriggerEvent`, check `SELECT 1 FROM issue_cursor WHERE issue_number=? AND repo=?`; if found, emit `run.skipped` event via `eventlog` and `continue` — `services/orchestrator/src/orchestrator/triggers/github_issues_poll.py` — Owner: @python-architect
- [X] T018 [US4] Insert into `issue_cursor` after successful triage in `IssueTiageAgent.run()`: `INSERT OR REPLACE INTO issue_cursor (issue_number, repo, triaged_at) VALUES (?, ?, ?)` using the eventlog connection — `services/orchestrator/src/orchestrator/agents/issue_triage.py` — Owner: @python-architect

**Checkpoint**: All four user stories functional. Duplicate issues silently skipped.

---

## Phase 7: Polish & Cross-Cutting

**Status**: ✅ Complete (2/2 — T019–T020)
**Purpose**: End-to-end integration test + plan conformance gate.

- [X] T019 [P] Write integration test for full issue triage end-to-end (gated `INTEGRATION=1`): creates a real GitHub issue on the test repo, asserts `triage.decision` event in `events.db`, asserts comment on issue via `gh issue view` — `services/orchestrator/tests/integration/test_p5_issue_triage_end_to_end.py` — Owner: @python-tester
- [X] T020 Run plan-conformance audit: verify all spec FR-101–FR-113 are addressed, no unplanned files modified, no TODOs left, no mock data, no hardcoded fakes — Owner: @code-plan-verifier

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Gate 3)**: Depends on Phase 1 completion (conftest needs existing fake_gh fixture from 002).
- **Phase 3 (US1)**: Depends on Phase 2 — **T004 must exist and fail before T009**.
- **Phase 4 (US2)**: Depends on Phase 3 — `_post_comment` extends the agent built in T010.
- **Phase 5 (US3)**: Depends on Phase 3 — adds `notifier` calls to the agent built in T010.
- **Phase 4 and Phase 5**: Can be implemented in parallel (both extend `issue_triage.py` but in different methods) if using separate worktrees.
- **Phase 6 (US4)**: Depends on Phase 3 (extends T009 and T010); can proceed in parallel with Phases 4+5.
- **Phase 7 (Polish)**: Depends on all story phases complete.

### Task Dependencies Within US1

- T006, T007, T008 (unit tests) → write and verify failing → then T009, T010, T011
- T009 (poll trigger) must complete before T011 (daemon wiring)
- T010 (agent core) must complete before T011 (daemon wiring)

### Parallel Opportunities

Within Phase 1: T002 and T003 are independent (`config.py` vs `eventlog.py`) — run in parallel.  
Within Phase 2: T004 and T005 are independent — run in parallel.  
Within Phase 3 tests: T006, T007, T008 are independent — run in parallel.  
Phases 4 and 5: if two `@python-architect` agents are available, dispatch with `isolation: "worktree"` since both extend `issue_triage.py`.

---

## Parallel Example: Phase 1 (Setup)

```bash
# T002 and T003 have no shared files — dispatch concurrently:
Task T002: "Add orchestrator_enable_issue_triage field to Config in services/orchestrator/src/orchestrator/config.py"
Task T003: "Add issue_cursor CREATE TABLE to eventlog.py schema migration in services/orchestrator/src/orchestrator/eventlog.py"
```

## Parallel Example: Phase 3 (US1 Tests)

```bash
# T006, T007, T008 write to different test files — dispatch concurrently:
Task T006: "Unit test for TriggerEvent kind=issue.opened in tests/unit/test_trigger_base.py"
Task T007: "Unit test for GithubIssuesPollTrigger in tests/unit/test_github_issues_poll.py"
Task T008: "Unit test for IssueTiageAgent core in tests/unit/test_issue_triage.py"
```

---

## Implementation Strategy

### MVP (US1 only — Phases 1–3)

1. Complete Phase 1 (T001–T003): infrastructure changes.
2. Complete Phase 2 (T004–T005): Gate 3 contract test written and failing; conftest extended.
3. Complete Phase 3 (T006–T011): core trigger + agent + daemon wiring.
4. **STOP and VALIDATE**: `pytest tests/` passes; manual smoke test detects issue and logs `triage.decision`.
5. Demo the MVP before continuing.

### Incremental Delivery

1. Phases 1–3 → MVP: issue detected, triage logged. ✓
2. Phase 4 → comment posted on GitHub issue. ✓
3. Phase 5 → phone notifications. ✓
4. Phase 6 → no duplicate triage. ✓
5. Phase 7 → integration tested and audited. ✓

---

## Notes

- `[P]` tasks write to different files — safe to dispatch concurrently without worktrees.
- Phases 4 and 5 both extend `agents/issue_triage.py` — if dispatched concurrently, pass `isolation: "worktree"` per Constitution Gate 6.
- Verify T004 fails before starting T009 — Gate 3 contract-test-first rule.
- All env-var-only config — never touch `.env` files.
- Run `uv run ruff check .` after each implementation task; zero lint errors expected.
