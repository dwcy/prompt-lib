---

description: "Task list for Agent Orchestrator — GitHub PR Review (v1)"
---

# Tasks: Agent Orchestrator — GitHub PR Review (v1)

**Input**: Design documents from `/specs/002-agent-orchestrator/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Constitution**: `.specify/memory/constitution.md` v1.0.0 — contract tests for protocol surfaces (Gate 3) are NON-NEGOTIABLE.

**Tests**: Required for this feature — three external surfaces require contract tests per Constitution Principle III (`gh pr list --json` parser, ntfy publish, A2A delegation consumer). Internal Python interfaces have unit tests at author's discretion (eventlog, config, trigger base).

**Organization**: Tasks grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec.md user stories (US1 — Automated PR Review · US2 — Live Dashboard · US3 — Phone Push Notifications · US4 — Replayable History)
- **Owner**: Named subagent from `.specify/memory/agents.md`. Dispatched via `Agent` tool in `/speckit-implement`.
- Every task includes the exact file path it produces or modifies.

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (6/6 — T001–T006)
**Purpose**: Initialize the `services/orchestrator/` Python package, lock dependencies, configure tooling. Mirror `services/a2a-bridge/` shape.

- [X] T001 Create `services/orchestrator/` directory and Python package skeleton at `services/orchestrator/src/orchestrator/__init__.py` plus empty subpackages `triggers/__init__.py`, `agents/__init__.py`, `dashboard/__init__.py`, and the `tests/` tree (`tests/__init__.py`, `tests/contract/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py`) — Owner: @python-architect
- [X] T002 [P] Create `services/orchestrator/pyproject.toml` declaring runtime deps (`typer>=0.12`, `httpx>=0.27`, `pydantic>=2`, `pydantic-settings>=2`, `textual>=0.80`, `rich>=13`, path dep on `../a2a-bridge`), dev deps via `[dependency-groups]` (`pytest`, `pytest-asyncio`, `pytest-httpx`, `ruff`), `[project.scripts] orchestrator = "orchestrator.cli:app"`, and `requires-python = ">=3.13"` — Owner: @python-architect
- [X] T003 [P] Create `services/orchestrator/.python-version` pinning Python 3.13 — Owner: @python-architect
- [X] T004 Run `uv sync` from `services/orchestrator/` to generate `services/orchestrator/uv.lock` and the project venv (depends on T002, T003) — Owner: @python-architect
- [X] T005 [P] Configure ruff in `services/orchestrator/pyproject.toml` (`[tool.ruff]` line-length 100, target Python 3.13, enable rule sets `E`, `F`, `I`, `B`, `UP`, `RUF`) matching `services/a2a-bridge/`'s config — Owner: @python-architect
- [X] T006 [P] Create `services/orchestrator/README.md` linking to `specs/002-agent-orchestrator/quickstart.md` and `specs/002-agent-orchestrator/spec.md`, with a one-paragraph "what this is" intro — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (7/7 — T007–T013)
**Purpose**: Build the config layer, the typed event log (writers + readers), and the Trigger abstraction every user story depends on. The eventlog's orphan-recovery routine is deliberately deferred to US4 (Phase 6) so it can be tested independently.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Test fixtures (shared)

- [X] T007 Create `services/orchestrator/tests/conftest.py` with shared fixtures: (a) `tmp_db` returning a `Path` to a fresh SQLite file, (b) `fake_gh` `monkeypatch.setenv("PATH", ...)` placing a Python shim that emits canned JSON or fixture stderr based on argv, (c) `httpx_mock` re-export from `pytest-httpx`, (d) `fake_delegation_client` yielding a configurable canned event sequence — Owner: @python-tester

### Config (env-only, no `.env`)

- [X] T008 [P] Unit test for `config.py`: required env vars rejected when missing, optional defaults applied, `ORCHESTRATOR_REPO` rejected when not matching `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`, `A2A_BEARER_TOKEN` rejected when empty, `ORCHESTRATOR_DB_PATH` defaults to `~/.claude/orchestrator/events.db` — `services/orchestrator/tests/unit/test_config.py` — Owner: @python-tester
- [X] T009 Implement `Config` model using `pydantic_settings.BaseSettings` in `services/orchestrator/src/orchestrator/config.py` with the env-var schema documented in research.md R8; pure env reads, NEVER touches `.env` files; raises clear `ValidationError` at startup if required vars are missing — Owner: @python-architect

### Trigger Protocol + TriggerEvent model

- [X] T010 [P] Unit test for `triggers/base.py`: `TriggerEvent` validates `kind` enum, `repo` slug regex, `pr_number > 0`, `head_sha` 40-char hex; rejects unknown kinds; serializes UTC `detected_at` as ISO 8601 — `services/orchestrator/tests/unit/test_trigger_base.py` — Owner: @python-tester
- [X] T011 Implement `Trigger` `typing.Protocol` (with `events()` async-iterator and `aclose()`) and `TriggerEvent` Pydantic v2 model (frozen, `extra='forbid'`) in `services/orchestrator/src/orchestrator/triggers/base.py` — Owner: @python-architect

### Event log (SQLite WAL, append-only)

- [X] T012 [P] Unit test for `eventlog.py` write & tail: schema bootstraps idempotently on a fresh file (WAL pragma set, 3 tables created, `schema_version=1` row inserted); `append_event` inserts a row with monotonic `id`; `tail_since(last_id)` returns only rows with `id > last_id`; concurrent reader sees the writer's row after commit; rejects `level` not in the CHECK enum — `services/orchestrator/tests/unit/test_eventlog.py` — Owner: @python-tester
- [X] T013 Implement `eventlog.py` in `services/orchestrator/src/orchestrator/eventlog.py`: `bootstrap(path)` (DDL + WAL + version row), `append_event(run_id, kind, level, payload)`, `tail_since(last_id) -> list[Event]`, `runs_summary() -> list[Run]` (computes the run state from the latest terminal event per `run_id` per data-model.md), `cursor_get(pr_number)` / `cursor_upsert(pr_number, head_sha)`. NO orphan-recovery here — that lands in T032 — Owner: @python-architect

**Checkpoint**: Foundation ready — User Story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Automated PR Review on a Configured Repo (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (9/9 — T014–T022)
**Goal**: When a contributor opens or updates a PR on the configured repo, the orchestrator detects it within one polling interval, dispatches it to a peer Claude Code adapter via the A2A bridge, and posts the agent's review back to the PR via `gh pr review --comment -F -`. Every state transition lands in the SQLite event log. Phone notifications and the dashboard are deliberately NOT in this story (US3 and US2 add them).

**Independent Test**: Configure the daemon against a throwaway test repo with the A2A bridge running, push a branch, run `gh pr create`. Within ~90 seconds `gh pr view <n> --comments` shows a review comment authored by the orchestrator's `gh` identity, and `sqlite3 events.db "select kind from events order by id"` shows the expected lifecycle (`run.queued`, `run.started`, `agent.message`*, `agent.state`*, `gh.review.posted`, `run.completed`).

### Contract tests for the protocol surfaces this story exercises ⚠️

> Per Constitution Principle III, contract tests for these external surfaces MUST be written and observed failing before any implementation.

- [X] T014 [P] [US1] Contract test for `gh pr list --json` parser per `contracts/gh-pr-list.contract.md` (accepts minimal required fields, accepts unknown extras, skips PRs missing `headRefOid` / invalid SHA / unparseable `updatedAt`, returns `[]` for empty input, emits `auth.failed` on `not authenticated` stderr, emits `auth.failed` on `not found` stderr, emits `gh.rate_limited` on `rate limit` stderr) using the `fake_gh` shim from conftest — `services/orchestrator/tests/contract/test_gh_pr_list_schema.py` — Owner: @python-tester
- [X] T015 [P] [US1] Contract test for the A2A delegation consumer per `contracts/a2a-delegation.contract.md` (consumes minimal `submitted → message → completed` sequence, concatenates partial message chunks, emits `agent.state` per state event, treats `failed` and `cancelled` as terminal, propagates unknown event kinds with `agent.<kind>`, emits `run.failed` when delegate raises, truncates exception message in payload, handles `NO_REVIEW:` sentinel as `skipped`, does NOT post when terminal is `failed` or `cancelled`) using `fake_delegation_client` — `services/orchestrator/tests/contract/test_a2a_delegation_consumer.py` — Owner: @python-tester

### Unit tests for US1-only logic

- [X] T016 [P] [US1] Unit test for `triggers/github_poll.py` diff logic: new `pr_number` → `pr.opened` event + cursor row inserted; same `pr_number` + same `head_sha` → no event + `last_seen` updated; same `pr_number` + different `head_sha` → `pr.updated` event + cursor row updated; closed PR (absent from poll) → no event, cursor row left in place — `services/orchestrator/tests/unit/test_github_poll.py` — Owner: @python-tester
- [X] T017 [P] [US1] Unit test for `agents/pr_review.py` prompt construction: prompt embeds `gh pr diff <n>` text verbatim within a fenced block, includes `repo`, `pr_number`, `headRefName`, `baseRefName`, `author.login`, `url`; output sentinel `NO_REVIEW: <reason>` triggers `run.skipped` event with `reason="agent_declined"` and zero `gh pr review` invocation — `services/orchestrator/tests/unit/test_pr_review.py` — Owner: @python-tester

### Implementation for US1

- [X] T018 [US1] Implement `triggers/github_poll.py` in `services/orchestrator/src/orchestrator/triggers/github_poll.py`: `GithubPollTrigger(repo, poll_seconds, eventlog)` exposing `events()` as an async generator. Wraps `gh pr list --repo <repo> --state open --json number,headRefOid,updatedAt,title,url,headRefName,baseRefName,author --limit 100` via `asyncio.create_subprocess_exec`. Parses output per `contracts/gh-pr-list.contract.md` (forward-compatible — accept unknown fields, reject missing required ones with a per-PR skip + `gh.parse.failed` event). Diffs against the `cursor` table. Maps stderr signatures (`not authenticated`, `not found`, `rate limit`) to typed events. Pauses the loop on `auth.failed`; sleeps and retries on `rate limit`. Depends on T014, T016 — Owner: @python-architect
- [X] T019 [US1] Implement `agents/pr_review.py` in `services/orchestrator/src/orchestrator/agents/pr_review.py`: `PrReviewAgent(delegation_client, eventlog)` exposing `async run(trigger_event)`. Runs `gh pr diff <n> --repo <repo>` to capture the diff. Builds the prompt per `contracts/a2a-delegation.contract.md`. Calls `delegation_client.delegate(prompt)` and consumes the SSE event stream, writing one event per A2A event to the eventlog. Detects `NO_REVIEW:` sentinel. On terminal `completed`, posts the accumulated message text via `gh pr review <n> --repo <repo> --comment -F -` (stdin), captures the resulting URL into a `gh.review.posted` event, then writes `run.completed`. On terminal `failed` / `cancelled`, writes `run.failed` and does NOT post. Catches and logs delegate-raise → `run.failed` with `stage="delegate"`. Depends on T015, T017 — Owner: @python-architect
- [X] T020 [US1] Implement `daemon.py` in `services/orchestrator/src/orchestrator/daemon.py`: `async def serve(config)` constructs the eventlog, the `DelegationClient` (lifetime-managed via `async with`), the `GithubPollTrigger`, and the `PrReviewAgent`. Runs `async for event in trigger.events(): asyncio.create_task(agent.run(event))` with a bounded concurrency semaphore (default 3 concurrent runs). Handles `SIGINT`/`SIGTERM` via `loop.add_signal_handler` (POSIX) or `signal.signal` (Windows fallback) for clean shutdown — finishes in-flight runs OR cancels them after a 5 s grace, then closes the trigger and the delegation client. NO notifier wiring here — that is added in T029 — Owner: @python-architect
- [X] T021 [US1] Implement `cli.py` in `services/orchestrator/src/orchestrator/cli.py`: Typer app with one subcommand `orchestrator serve` that loads `Config`, runs the pre-flight checks (`gh auth status`, A2A peer reachable via `httpx.AsyncClient.head`, ntfy reachable via `HEAD https://ntfy.sh/_health`), prints the startup banner (matching `setup/apply.py:87-104` gradient style), then invokes `daemon.serve`. NO `dash` subcommand here — added in T024 — Owner: @python-architect

### Integration test for US1

- [X] T022 [US1] Integration test for end-to-end PR review per spec.md User Story 1 acceptance scenarios (1: PR opened → review posted; 2: PR updated → second review posted, prior left intact; 3: peer agent down → `run.failed` event + zero PR comment; 4: PR on a different repo ignored). Skipped unless `INTEGRATION=1`. Spawns the A2A bridge in a real subprocess, points the daemon at a per-test ephemeral repo created via `gh repo create --private --confirm` and torn down in teardown — `services/orchestrator/tests/integration/test_p1_pr_review_end_to_end.py` — Owner: @python-tester

**Checkpoint**: User Story 1 (the MVP) is fully functional. The quickstart.md Step 7 must pass before moving on.

---

## Phase 4: User Story 2 — Live Console Dashboard (Priority: P2)

**Status**: ✅ Complete (3/3 — T023–T025)
**Goal**: A separate `orchestrator dash` Typer subcommand launches a Textual TUI that tails the SQLite event log, renders a `DataTable` of recent runs (running / completed / failed / skipped / orphaned), and a `Log` widget streaming event payloads. Updates are visible within 1 second of the daemon writing them (SC-003). The dashboard is read-only; it never writes to the event log.

**Independent Test**: With the daemon running and a PR-review run in progress, launch `orchestrator dash`. The runs table populates with the in-flight run; the row state transitions through `running → completed` (or `failed`) on screen; the event tail shows agent messages ordered by `id`. Killing the daemon mid-run leaves the dashboard usable; restarting the daemon causes new events to appear in the tail without restarting the dashboard.

### Implementation for US2

- [X] T023 [US2] Implement `dashboard/app.py` in `services/orchestrator/src/orchestrator/dashboard/app.py`: Textual `App` subclass `OrchestratorDash`. Layout (top-to-bottom): gradient banner header (mirror `setup/apply.py:87-104` palette and `render_banner` shape, but with the title `ORCHESTRATOR · <repo>`), `DataTable` of recent runs (mirror `setup/apply.py:785-825` column widths and status-glyph pattern: ✓/✗/⚠/○ for completed/failed/skipped/orphaned, ⟳ for running), `Log` widget showing the most-recent ~200 event payload lines, status footer `connected · <N> events · last poll: <relative time>`. `on_mount` opens the eventlog read-only and starts a `set_interval(0.5, self._refresh)` timer calling `eventlog.tail_since(self._last_id)` and `eventlog.runs_summary()` to update widgets. NO Worker pattern — SQLite reads are sub-millisecond. Reads `ORCHESTRATOR_DB_PATH` from the same `Config` as the daemon — Owner: @python-architect
- [X] T024 [US2] Add `orchestrator dash` subcommand to `services/orchestrator/src/orchestrator/cli.py` (alongside the existing `serve` from T021): loads `Config`, instantiates `OrchestratorDash`, calls `app.run()`. Exits cleanly on `Ctrl+C`. Depends on T021, T023 — Owner: @python-architect

### Integration test for US2

- [X] T025 [P] [US2] Integration test for dashboard tailing live events per spec.md User Story 2 acceptance scenarios (1: dashboard shows historical runs on launch; 2: new daemon-emitted event reflected within 1 s; 3: dashboard remains usable when daemon is killed; 4: closing-and-reopening preserves the historical record). Drives the dashboard via Textual's `App.run_test()` headless mode and writes events directly into a fixture SQLite file in a background asyncio task — `services/orchestrator/tests/integration/test_p2_dashboard_tail.py` — Owner: @python-tester

**Checkpoint**: User Stories 1 AND 2 work independently. Killing either process does not affect the other.

---

## Phase 5: User Story 3 — Phone Push Notifications at Each Step (Priority: P2)

**Status**: ✅ Complete (5/5 — T026–T030)
**Goal**: At every meaningful event-log transition (`run.started`, `run.completed`, `run.failed`, `run.skipped`, `run.orphaned`, `auth.failed`), the orchestrator pushes a notification to the operator's ntfy topic with the level → priority + tags mapping locked in research.md R4 / data-model.md. Push failures are non-fatal — they MUST NOT abort the underlying run (FR-009).

**Independent Test**: Set `ORCHESTRATOR_NTFY_TOPIC` to a fresh topic, subscribe a phone via the ntfy mobile app, run an end-to-end PR review. The phone receives at least two notifications (start + complete). Levels match the actual event level (info/warn/error). With the topic deliberately broken (set to a 64-char garbage string the server still accepts), the run still completes — only `push.failed` events appear in the log.

### Contract test for ntfy publish ⚠️

- [X] T026 [P] [US3] Contract test for ntfy publish per `contracts/ntfy-publish.contract.md` (POST URL uses configured base + topic; level → priority/tags mapping for all four levels; `Title` set; `Click` set when URL provided, omitted when None; body is UTF-8 plain text; body truncated at 1024 chars with `…` marker; `User-Agent` includes orchestrator + version; 4xx/5xx response → `push.failed` event without raising; network timeout → `push.failed` event without raising) using `httpx.MockTransport` — `services/orchestrator/tests/contract/test_ntfy_publish_request.py` — Owner: @python-tester

### Unit tests for US3

- [X] T027 [P] [US3] Unit test for `notifier.py` level → priority + tags mapping (info=3+🔵, warn=4+⚠️, error=5+🛑, needs_input=5+❓), title length cap at 200 chars, body truncation marker — `services/orchestrator/tests/unit/test_notifier.py` — Owner: @python-tester

### Implementation for US3

- [X] T028 [US3] Implement `notifier.py` in `services/orchestrator/src/orchestrator/notifier.py`: `Notifier(topic, base_url, eventlog, http_client)` with `async send(level, title, body, click_url=None)`. Constructs the request per the contract (headers + UTF-8 body); uses an `httpx.AsyncClient` injected at construction (single client per daemon lifetime, 5 s per-request timeout); on non-2xx or network error writes a `push.failed` event with `status_code` / `detail` and returns without raising. Depends on T026, T027 — Owner: @python-architect
- [X] T029 [US3] Wire the notifier into `services/orchestrator/src/orchestrator/daemon.py` (extends T020): construct one `Notifier` from `Config` and inject it into `PrReviewAgent`; the agent calls `notifier.send` from its `run.started`, `run.completed`, `run.failed`, `run.skipped`, `run.orphaned`, and `auth.failed` event-emit hooks per the data-model.md notification policy table. Push exceptions are caught at the call site so a notifier bug cannot abort an in-flight run. Depends on T020, T028 — Owner: @python-architect

### Integration test for US3

- [X] T030 [US3] Integration test for phone notifications per spec.md User Story 3 acceptance scenarios (1: run start → info push; 2: run complete → info push with click URL; 3: run fail → error push; 4: ntfy unreachable → run still completes, `push.failed` event recorded). Skipped unless `INTEGRATION=1`. Uses a local `httpx.MockTransport`-backed receiver to capture the POSTs (no real ntfy round-trip in CI; the real-phone test step is in `quickstart.md`) — `services/orchestrator/tests/integration/test_p3_phone_notification.py` — Owner: @python-tester

**Checkpoint**: User Stories 1 AND 2 AND 3 work independently. The operator can now run the daemon and receive end-to-end phone notifications.

---

## Phase 6: User Story 4 — Replayable History Across Restarts (Priority: P3)

**Status**: ✅ Complete (3/3 — T031–T033)
**Goal**: Daemon, dashboard, and machine restarts leave the historical event record intact (already true since Phase 2). On daemon startup, any run whose latest event is `running`-implying with no terminal event AND whose `run.started` timestamp predates the daemon's previous shutdown is marked `orphaned` via a `run.orphaned` event written by the recovery routine (FR-013, SC-007). In-flight tasks are NOT resumed; the next poll handles the still-open PR independently.

**Independent Test**: While a run is in progress, kill the daemon. Restart it. Within ~1 s of the next dashboard refresh, the killed run appears in the runs table as `orphaned` (not `running`, not `completed`). The dashboard's historical event tail still renders the prior activity. The next poll cycle re-detects the still-open PR and starts a fresh run.

### Unit test for US4

- [X] T031 [P] [US4] Unit test for orphan recovery: a run with `run.queued` + `run.started` but no terminal event AND `started_at < shutdown_marker_ts` → `run.orphaned` event appended; a run with `run.queued` + `run.started` + `run.completed` → no `orphaned` emitted (idempotent); a run started AFTER the previous shutdown marker (i.e., from this current daemon process) → no `orphaned` emitted (avoid false positives during normal startup race) — `services/orchestrator/tests/unit/test_orphan_recovery.py` — Owner: @python-tester

### Implementation for US4

- [X] T032 [US4] Add `recover_orphans(shutdown_marker_ts)` to `services/orchestrator/src/orchestrator/eventlog.py` (extends T013): scans `runs_summary()`, identifies the orphan set per the rules in data-model.md, appends one `run.orphaned` event per orphan; idempotent (running it twice produces zero new events the second time). Wire it into `daemon.serve` startup (extends T020): on boot, read the previous shutdown marker from a small `~/.claude/orchestrator/shutdown.marker` file (timestamp-only, plain text), call `recover_orphans`, write a fresh marker on graceful shutdown via the SIGINT/SIGTERM handler. Depends on T013, T020 — Owner: @python-architect

### Integration test for US4

- [X] T033 [US4] Integration test for replayable history per spec.md User Story 4 acceptance scenarios (1: dashboard relaunch shows identical historical record; 2: daemon kill mid-run + restart marks the run as `orphaned` within one dashboard refresh, and the next poll handles the still-open PR). Skipped unless `INTEGRATION=1`. Uses `os.kill(pid, SIGKILL)` (not SIGTERM) to simulate an ungraceful shutdown so the marker file is NOT updated; verifies the orphan-recovery routine still completes correctly on next start — `services/orchestrator/tests/integration/test_p4_replayable_history.py` — Owner: @python-tester

**Checkpoint**: All four user stories work independently. v1 is feature-complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Status**: ✅ Complete (3/3 — T034–T036)
**Purpose**: Final-mile improvements after every story is independently green.

- [X] T034 [P] Update `services/orchestrator/README.md` (created in T006) with a concrete usage block: pre-reqs (Python 3.13, uv, gh, A2A bridge running), env-var setup snippet (PowerShell + bash), the two `uv run orchestrator serve` / `dash` invocations, link to `specs/002-agent-orchestrator/quickstart.md` for the full walkthrough — Owner: main
- [X] T035 Run `specs/002-agent-orchestrator/quickstart.md` end-to-end on a real throwaway GitHub repo: all 10 steps pass, all 4 acceptance-scenario checks (review posted, peer-down failure, replayable history, dashboard auto-update) succeed within their stated time budgets, `uv run pytest` and `INTEGRATION=1 uv run pytest` are both green in `services/orchestrator/`, `uv run pytest` is still green in `services/a2a-bridge/` — Owner: main. Maintainer-confirmed complete; A2A Inspector conformance remains tracked separately in `specs/001-a2a-bridge/tasks.md` T039.
- [X] T036 Plan-conformance audit by `@code-plan-verifier` against `specs/002-agent-orchestrator/plan.md` and the constitution gates: report verdict (PASS / PASS-WITH-WARNINGS / FAIL), no implementation shortcuts, no mock data left behind, no unplanned global/ changes, no skill/agent additions, contract tests precede implementations in tasks.md ordering, every task has an Owner from agents.md — Owner: @code-plan-verifier

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. **BLOCKS** all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational completion.
  - US1 (P1) is the MVP — ship before US2/US3/US4.
  - After US1, US2 and US3 are independent (different files, different surfaces) and can proceed in parallel.
  - US4 depends on US1 (it tests the daemon-restart story which only makes sense after the daemon exists).
- **Polish (Phase 7)**: Depends on US1+US2+US3+US4 all complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundation (Phase 2).
- **US2 (P2)**: Depends on Foundation. Reads from the eventlog written by US1's daemon — but is INDEPENDENTLY TESTABLE because the integration test feeds a fixture SQLite file directly.
- **US3 (P2)**: Depends on Foundation. T029 modifies `daemon.py` (created in US1's T020) — so US3 implementation work depends on US1's implementation. The notifier itself (T026–T028) is independent; only the wiring (T029) crosses.
- **US4 (P3)**: Depends on Foundation + US1 (orphan recovery is invoked from the daemon's startup path).

### Within Each User Story

- Contract tests (Constitution Principle III) MUST be written and observed failing BEFORE the implementation tasks for the same surface.
- Unit tests precede implementation when the unit covers a specific module's logic.
- Models / abstractions before consumers (e.g., `Trigger` Protocol before `GithubPollTrigger`).
- Implementation before integration tests.

### Cross-task file dependencies

- `services/orchestrator/src/orchestrator/cli.py` is touched by T021 (US1) and T024 (US2) — sequential, NOT [P] across stories.
- `services/orchestrator/src/orchestrator/daemon.py` is touched by T020 (US1), T029 (US3), and T032 (US4) — sequential, NOT [P] across stories.
- `services/orchestrator/src/orchestrator/eventlog.py` is touched by T013 (Foundation) and T032 (US4) — T032 strictly extends; sequential.

### Parallel Opportunities

- All Setup tasks marked [P] (T002, T003, T005, T006) can run after T001 in parallel.
- Within Foundation: T008 ‖ T010 ‖ T012 in parallel (different test files, different modules under test); their implementations T009, T011, T013 in parallel after the corresponding tests fail.
- Within US1: T014 ‖ T015 ‖ T016 ‖ T017 in parallel (four different test files); after they fail, T018 and T019 in parallel (different files); then T020 then T021 (cli wires daemon).
- Across US2 and US3: after US1 ships, both stories can be developed by separate agents simultaneously — they touch different files except for the cli/daemon wiring touchpoints noted above.

---

## Parallel Example: User Story 1

```bash
# Round 1 — all four tests for US1 in parallel (each in its own test file):
Task: "Contract test gh-pr-list parser in services/orchestrator/tests/contract/test_gh_pr_list_schema.py"      # T014
Task: "Contract test A2A delegation consumer in services/orchestrator/tests/contract/test_a2a_delegation_consumer.py"  # T015
Task: "Unit test github_poll diff logic in services/orchestrator/tests/unit/test_github_poll.py"               # T016
Task: "Unit test pr_review prompt building in services/orchestrator/tests/unit/test_pr_review.py"              # T017

# Round 2 — once their tests fail, the two implementation files in parallel:
Task: "Implement triggers/github_poll.py in services/orchestrator/src/orchestrator/triggers/github_poll.py"    # T018
Task: "Implement agents/pr_review.py in services/orchestrator/src/orchestrator/agents/pr_review.py"            # T019

# Round 3 — sequential (daemon wires both, cli wires daemon):
Task: "Implement daemon.py wiring trigger → agent → eventlog"   # T020
Task: "Implement cli.py orchestrator serve subcommand"          # T021

# Round 4 — integration:
Task: "Integration test end-to-end PR review (INTEGRATION=1)"   # T022
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1: Setup (T001–T006).
2. Complete Phase 2: Foundational (T007–T013) — **blocks every user story**.
3. Complete Phase 3: User Story 1 (T014–T022).
4. **STOP and VALIDATE**: run quickstart.md Step 7 against a real throwaway repo. The agent must successfully post a review comment on a real PR.
5. Tag the MVP. Demo it. Decide whether US2/US3/US4 are wanted before continuing.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 (PR review with terminal logging) → MVP deployable. (No dashboard, no phone push yet — only the SQLite event log.)
3. + US2 (Live console dashboard) → operator-at-the-desk visibility.
4. + US3 (Phone push notifications) → walk-away mode.
5. + US4 (Replayable history + orphan recovery) → trust + post-mortem support.
6. Polish (T034–T036) → README, real-repo verification pass, plan-conformance audit.

### Parallel Team Strategy

If multiple agents are dispatched simultaneously after Foundation:

1. Agent A: US1 — the critical path. The MVP cannot ship without it.
2. Agent B: US2 dashboard implementation (T023) — uses a fixture SQLite file so it does not depend on Agent A's daemon being live.
3. Agent C: US3 contract test + notifier module (T026–T028) — pure module work that does NOT depend on the daemon.
4. After Agent A finishes T020/T021: Agent B integrates US2 into cli.py (T024); Agent C wires the notifier into the daemon (T029).
5. After both US2 and US3 are green: US4's T032 (eventlog orphan recovery + daemon startup wiring) can land.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps each task to a specific spec.md user story for traceability.
- `Owner` field maps each task to a named subagent from `.specify/memory/agents.md` per Constitution Principle II — never invent agent names.
- Contract tests for protocol surfaces (Gate 3) precede their implementing tasks in the linear ordering above. Internal Python interfaces have unit tests at author's discretion.
- Each user story is independently completable and independently testable — kill any story's phase mid-implementation and the prior stories' acceptance tests still pass.
- Verify tests fail before implementing the corresponding code (Principle III for contract tests; encouraged for unit tests).
- Commit after each task or logical group. Use `/git` (project memory: never invoke `speckit-git-*` skills).
- Stop at any checkpoint to validate a story independently. The MVP checkpoint (after T022) is the most important — it gates whether v1 is worth continuing into US2+.
- Avoid: vague tasks, same-file write conflicts in parallel claims, cross-story dependencies that break independent testability, missing Owner field, contract-tests-after-implementation ordering errors.
