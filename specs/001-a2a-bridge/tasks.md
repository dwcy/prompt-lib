---

description: "Task list for A2A Bridge for Multi-Agent CLI Delegation (v1)"
---

# Tasks: A2A Bridge for Multi-Agent CLI Delegation (v1)

**Input**: Design documents from `/specs/001-a2a-bridge/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Constitution**: `.specify/memory/constitution.md` v1.0.0 — contract tests for protocol surfaces are NON-NEGOTIABLE.

**Tests**: Required for this feature — Constitution Principle III makes contract tests for protocol surfaces binding.

**Organization**: Tasks grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md user stories (US1, US2, US3)
- **Owner**: Named subagent from `.specify/memory/agents.md`. Dispatched via `Agent` tool in `/speckit-implement`.
- Every task includes the exact file path it produces or modifies.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialise the `services/a2a-bridge/` Python package, lock dependencies, and configure tooling.

- [X] T001 Create `services/a2a-bridge/` directory and Python package skeleton at `services/a2a-bridge/src/a2a_bridge/__init__.py` plus empty subpackages `protocol/`, `adapters/`, `adapters/claude/`, `adapters/gemini/`, `client/` and the `tests/` tree (`tests/__init__.py`, `tests/contract/__init__.py`, `tests/integration/__init__.py`, `tests/unit/__init__.py`) — Owner: @python-architect
- [X] T002 [P] Create `services/a2a-bridge/pyproject.toml` declaring runtime deps (`fastapi>=0.135`, `httpx`, `pydantic>=2`, `uvicorn`, `typer`), dev deps via `[dependency-groups]` (`pytest`, `pytest-asyncio`, `ruff`, `a2a-sdk>=1.0` — note: the official A2A SDK is published as `a2a-sdk`, not `a2a`), `[project.scripts] a2a-bridge = "a2a_bridge.cli:app"`, and `requires-python = ">=3.13"` — Owner: @python-architect
- [X] T003 [P] Create `services/a2a-bridge/.python-version` pinning Python 3.13 — Owner: @python-architect
- [X] T004 Run `uv sync` from `services/a2a-bridge/` to generate `services/a2a-bridge/uv.lock` and the project venv — Owner: @python-architect
- [X] T005 [P] Configure ruff in `services/a2a-bridge/pyproject.toml` (`[tool.ruff]` line-length 100, target Python 3.13, enable rule sets `E`, `F`, `I`, `B`, `UP`, `RUF`) — Owner: @python-architect
- [X] T006 [P] Create `services/a2a-bridge/README.md` linking to `specs/001-a2a-bridge/quickstart.md` and `specs/001-a2a-bridge/spec.md` — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the protocol primitives, auth middleware, and base FastAPI app factory that every adapter depends on. Each protocol surface gets its contract test BEFORE its implementation per Constitution Principle III.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Structured stdout logger (FR-006, Constitution Principle III)

> Inserted post-`/speckit-analyze` to close the FR-006 coverage gap (analyze finding C1). Auth and all subsequent foundational modules import this logger.

- [X] T006a [P] Contract test for structured stdout logger: every emitted line is one valid JSON object with required fields `ts` (RFC 3339 UTC), `level`, `event`, and optional `task_id`, `peer`, `outcome`, `ref`; logger emits to stdout (not stderr); logger NEVER includes the bearer token value or any prefix/suffix of it; helper signatures `log_task_received`, `log_outbound_delegation`, `log_auth_ok`, `log_auth_fail`, `log_cli_exit` all behave per the schema — `services/a2a-bridge/tests/contract/test_structured_logger.py` — Owner: @python-tester
- [X] T006b Implement structured stdout logger in `services/a2a-bridge/src/a2a_bridge/protocol/logging.py`: `get_logger(name)` factory returning a stdlib `logging.Logger` configured with a JSON formatter to stdout, plus the typed helper functions `log_task_received`, `log_outbound_delegation`, `log_auth_ok`, `log_auth_fail`, `log_cli_exit` — Owner: @python-architect

### Bearer-token authentication

- [X] T007 [P] Contract test for bearer-token compare: constant-time HMAC, rejects empty/missing tokens, never logs token value, asserts auth ok/fail messages match the documented format — `services/a2a-bridge/tests/unit/test_bearer_token_compare.py` — Owner: @python-tester
- [X] T008 Implement bearer-token compare helper in `services/a2a-bridge/src/a2a_bridge/protocol/auth.py` (uses `hmac.compare_digest`, refuses tokens shorter than 32 chars at startup with a logged warning) — Owner: @python-architect
- [X] T009 [P] Contract test for auth middleware: requests without `Authorization: Bearer <token>` or with a wrong token return HTTP 401 BEFORE any JSON-RPC processing or task event is emitted — `services/a2a-bridge/tests/contract/test_auth_middleware.py` — Owner: @python-tester
- [X] T010 Implement FastAPI auth middleware in `services/a2a-bridge/src/a2a_bridge/adapters/base.py` that wraps `/jsonrpc` and skips `/.well-known/agent-card.json` — Owner: @python-architect

### JSON-RPC envelope and error codes

- [X] T011 [P] Contract test for JSON-RPC envelope error mapping per `contracts/error-codes.md` (-32700 parse error, -32600 invalid request, -32601 method not found, -32602 invalid params, -32603 internal error with UUID `ref`) — `services/a2a-bridge/tests/contract/test_jsonrpc_envelope.py` — Owner: @python-tester
- [X] T012 [P] Contract test for HTTP-level errors per `contracts/error-codes.md` (401 unauthorized, 405 method not allowed for non-POST, 415 unsupported media type for non-JSON content-type) — `services/a2a-bridge/tests/contract/test_error_codes.py` — Owner: @python-tester
- [X] T013 Implement JSON-RPC request/response envelopes, parser, and error helpers in `services/a2a-bridge/src/a2a_bridge/protocol/jsonrpc.py` — Owner: @python-architect

### Task state machine

- [X] T014 [P] Contract test for the Task state machine per `data-model.md` (only `submitted→working→{completed|failed|cancelled}` transitions allowed; terminal states are sticky; event queue closes on terminal; subprocess reaped before terminal transition emits) — `services/a2a-bridge/tests/unit/test_task_state_machine.py` — Owner: @python-tester
- [X] T015 Implement `Task` entity, state machine, and per-task `asyncio.Queue` in `services/a2a-bridge/src/a2a_bridge/protocol/tasks.py` — Owner: @python-architect

### Agent Card schema and builder

- [X] T016 [P] Contract test that built `AgentCard` JSON validates against `specs/001-a2a-bridge/contracts/agent-card.schema.json` for both Claude and Gemini adapters; negative cases for missing required fields, wrong protocols, and `additionalProperties` leakage — `services/a2a-bridge/tests/contract/test_agent_card_schema.py` — Owner: @python-tester
- [X] T017 Implement `AgentCard` model + builder + schema loader in `services/a2a-bridge/src/a2a_bridge/protocol/agent_card.py` (loads `agent-card.schema.json` at import; builder produces card from adapter name, host, port, skills) — Owner: @python-architect

### SSE event framing and ordering

- [X] T018 [P] Contract test for SSE event framing and ordering per `contracts/sse-events.md` (event names `task.state` / `task.artifact` / `task.progress`, JSON `data:` shape, mandatory ordering, keep-alive `: keep-alive` every 15s, stream closes within 1s after terminal) — `services/a2a-bridge/tests/contract/test_sse_event_ordering.py` — Owner: @python-tester
- [X] T019 Implement SSE event helpers (event types, framer, ordering enforcer, keep-alive task) in `services/a2a-bridge/src/a2a_bridge/protocol/sse.py` — Owner: @python-architect

### Base FastAPI app factory

- [X] T020 Implement base FastAPI app factory in `services/a2a-bridge/src/a2a_bridge/adapters/base.py`: registers `POST /jsonrpc` (auth required), `GET /.well-known/agent-card.json` (no auth), wires the `Task` registry, plumbs SSE responses via `fastapi.sse.EventSourceResponse` — Owner: @python-architect
- [X] T021 Add adapter-startup self-check in `services/a2a-bridge/src/a2a_bridge/adapters/base.py` that builds the AgentCard, validates it against the schema, and refuses to start the adapter on validation failure — Owner: @python-architect

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Outbound Delegation: Claude → Gemini (Priority: P1) 🎯 MVP

**Goal**: A developer (or Claude Code) invokes `a2a-bridge delegate gemini "<prompt>"` and receives a streamed result from a running Gemini adapter on localhost.

**Independent Test**: With the Gemini adapter running on `127.0.0.1:8766` and `A2A_BEARER_TOKEN` set, run `uv run a2a-bridge delegate gemini "Reply pong"`; observe streamed `task.state` events ending in `completed` and a `task.artifact` carrying `pong` within 30 seconds (matches SC-001).

### Contract tests for the JSON-RPC methods this story exercises ⚠️

> Per Constitution Principle III, contract tests for these protocol surfaces MUST be written and observed failing before any implementation.

- [X] T022 [P] [US1] Contract test for `tasks/sendSubscribe` per `contracts/jsonrpc-methods.md` (request shape, validation rules, initial `submitted` state, conformant lifecycle to `completed`, parameter validation errors) — `services/a2a-bridge/tests/contract/test_jsonrpc_methods_send_subscribe.py` — Owner: @python-tester
- [X] T023 [P] [US1] Contract test for `tasks/get` per `contracts/jsonrpc-methods.md` (response shape, `task_not_found` error envelope) — `services/a2a-bridge/tests/contract/test_jsonrpc_methods_get.py` — Owner: @python-tester
- [X] T024 [P] [US1] Contract test for `tasks/cancel` per `contracts/jsonrpc-methods.md` (happy path transition to `cancelled`, `task_already_terminal` error envelope) — `services/a2a-bridge/tests/contract/test_jsonrpc_methods_cancel.py` — Owner: @python-tester. NOTE: `TestCancelWorkingTask` (3 tests) is `@pytest.mark.skip` because httpx ASGITransport buffers full responses and cannot exercise mid-stream cancel; spec-compliant cancel-while-working is verified end-to-end in T030 against a real uvicorn server.

### Gemini adapter

- [X] T025 [P] [US1] Implement Gemini CLI runner in `services/a2a-bridge/src/a2a_bridge/adapters/gemini/runner.py` (Gemini-specific shim) PLUS the CLI-agnostic generic runner in `services/a2a-bridge/src/a2a_bridge/protocol/cli_runner.py` (so Phase 4 Claude reuses it). Spawns subprocess via `asyncio.create_subprocess_exec`, parses NDJSON events line-by-line, translates to `Task` lifecycle events, enforces per-task timeout, captures last 1024 bytes of stderr for failure reporting — Owner: @python-architect
- [X] T026 [US1] Implement Gemini adapter server in `services/a2a-bridge/src/a2a_bridge/adapters/gemini/server.py`: composes base app + Gemini runner; builds Agent Card with `name="gemini-a2a-adapter"` and `skills=[{id: "gemini-prompt", ...}]` — Owner: @python-architect

### DelegationClient

- [X] T027 [US1] Implement `DelegationClient` in `services/a2a-bridge/src/a2a_bridge/client/delegation.py`: async `httpx.AsyncClient`, opens SSE stream against peer `/jsonrpc`, sends `tasks/sendSubscribe`, parses streamed events, maps connect/auth/parse failures to distinct exit codes per spec SC-006 — Owner: @python-architect

### CLI subcommand

- [X] T028 [US1] Implement `a2a-bridge delegate <peer> <prompt>` subcommand in `services/a2a-bridge/src/a2a_bridge/cli.py`: reads `A2A_PEER_BEARER_TOKEN` (falling back to `A2A_BEARER_TOKEN`) and `--peer` URL, drives `DelegationClient`, prints streamed updates to stdout — Owner: @python-architect
- [X] T029 [US1] Wire the `a2a-bridge` console script entry in `services/a2a-bridge/pyproject.toml [project.scripts]` and re-run `uv sync` to refresh the entry point — Owner: @python-architect

### Integration test

- [X] T030 [US1] Integration test for end-to-end Claude→Gemini delegation per spec.md User Story 1 acceptance scenarios (happy path streamed delegation, peer-unreachable fast-fail, bearer-token-mismatch fast-fail) using a real Gemini adapter subprocess — `services/a2a-bridge/tests/integration/test_p1_outbound_delegation.py` — Owner: @python-tester. NOTE: real `gemini` test is `@pytest.mark.skipif` when binary absent; cancel-while-working scenario (deferred from contract tests) is also covered here against real uvicorn.

**Checkpoint**: User Story 1 is fully functional. The MVP demo from `quickstart.md` Step 7 must pass end-to-end before moving on.

---

## Phase 4: User Story 2 — Inbound Reception via Claude Adapter (Priority: P2)

**Goal**: An external client (curl during dev; eventually peer agents) POSTs a JSON-RPC task to the Claude adapter and receives streamed task lifecycle + artifact events.

**Independent Test**: Start the Claude adapter on `127.0.0.1:8765` with a known `A2A_BEARER_TOKEN`; curl a `tasks/sendSubscribe` request per `quickstart.md` Step 6; observe SSE events that pass `a2a-python` SDK schema validation and end in `completed`.

### Claude adapter

- [X] T031 [US2] Implement Claude CLI runner in `services/a2a-bridge/src/a2a_bridge/adapters/claude/runner.py`: Claude-specific shim built on the generic `CliRunner`. `claude_command_factory` returns `["claude", "-p", prompt, "--bare", "--output-format", "stream-json", "--verbose"]`. `parse_claude_event` extracts text content from `type: assistant` events' `message.content[].text` blocks; skips `system`, `user` (tool_result echoes), and `result` envelopes. — Owner: @python-architect
- [X] T032 [US2] Implement Claude adapter server in `services/a2a-bridge/src/a2a_bridge/adapters/claude/server.py`: composes base app + Claude runner; builds Agent Card with `name="claude-code-a2a-adapter"` and `skills=[{id: "claude-prompt", ...}]` — Owner: @python-architect

### CLI subcommand

- [X] T033 [US2] Implement `a2a-bridge serve <agent>` subcommand in `services/a2a-bridge/src/a2a_bridge/cli.py`: dispatches to `claude.server` or `gemini.server`, validates `A2A_BEARER_TOKEN` is set and ≥32 chars, starts uvicorn bound to `127.0.0.1` on `--port` (defaults: claude→8765, gemini→8766) — Owner: @python-architect

### Integration test

- [X] T034 [US2] Integration test for inbound curl-driven flows per spec.md User Story 2 acceptance scenarios (happy path, missing/wrong bearer token returns 401 with no events, CLI non-zero exit emits `failed` with stderr tail, per-task timeout emits `cancelled` with reason `timeout`) using a real Claude adapter subprocess — `services/a2a-bridge/tests/integration/test_p2_inbound_curl.py` — Owner: @python-tester. NOTE: real-Claude test gated on `A2A_REAL_CLI_TESTS=1` env var (Claude has no comparable env-var auth like Gemini's `GEMINI_API_KEY`).

**Checkpoint**: Claude adapter is a peer in the mesh. Stories 1 AND 2 work independently end-to-end.

---

## Phase 5: User Story 3 — Agent Card Discovery (Priority: P3)

**Goal**: Any developer or peer agent can fetch the Agent Card from a running adapter via unauthenticated HTTP GET.

**Independent Test**: GET `http://127.0.0.1:8765/.well-known/agent-card.json` and `http://127.0.0.1:8766/.well-known/agent-card.json`; both return 200 with JSON that validates against `specs/001-a2a-bridge/contracts/agent-card.schema.json`.

- [ ] T035 [US3] Verify Agent Card discovery route is wired in the base FastAPI app factory (no auth, returns AgentCard JSON validated against `agent-card.schema.json`); if T020 left this incomplete, finish it in `services/a2a-bridge/src/a2a_bridge/adapters/base.py` — Owner: @python-architect
- [ ] T036 [US3] Integration test for Agent Card discovery per spec.md User Story 3 acceptance scenarios (200 with valid card, schema validation passes, no auth required) for both Claude and Gemini adapters — `services/a2a-bridge/tests/integration/test_p3_agent_card_discovery.py` — Owner: @python-tester

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, manual conformance pass, ADRs for any deviations, and documentation polish.

- [ ] T037 [P] Concurrency integration test per spec.md SC-007: 3+ inbound tasks in flight simultaneously on the Claude adapter, each gets its own CLI process and SSE stream, no cross-contamination, all complete with correct artifacts — `services/a2a-bridge/tests/integration/test_concurrency.py` — Owner: @python-tester
- [ ] T038 [P] End-to-end `quickstart.md` validation pass: walk through every numbered step on a clean machine; record observed timings against plan.md performance budgets (p95 task acceptance <100ms, cold start <2s, 30s end-to-end); update `quickstart.md` if any step is incorrect — Owner: main
- [ ] T039 [P] Manual A2A Inspector pass for SC-002: clone <https://github.com/a2aproject/a2a-inspector>, point it at both adapters, confirm zero spec violations on the validation panel; record the result in `services/a2a-bridge/CHANGELOG.md` (create file if missing) — Owner: main
- [ ] T040 [P] If any spec deviation was discovered during implementation, write an ADR per Constitution Principle I in `specs/001-a2a-bridge/contracts/adr-NNN-<slug>.md` for each one — Owner: main
- [ ] T041 Polish `services/a2a-bridge/README.md`: install, run, troubleshooting, links to `specs/001-a2a-bridge/spec.md` and `specs/001-a2a-bridge/quickstart.md` — Owner: main

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories. Within Phase 2, every contract test (`@python-tester`) MUST land and fail before its implementation (`@python-architect`) per Constitution Principle III.
- **Phase 3 (US1)**: Depends on Phase 2 completion. Contract tests T022–T024 land before T025–T029.
- **Phase 4 (US2)**: Depends on Phase 2 completion. Re-uses contract tests from Phase 3 (same JSON-RPC methods); only adds story-specific integration test T034.
- **Phase 5 (US3)**: Depends on Phase 2 (Agent Card builder T017 must exist). Can run in parallel with Phase 4.
- **Phase 6 (Polish)**: Depends on the user stories selected for the release being complete. T037 needs Phase 4 done (it tests the Claude adapter). T038–T041 need at least the MVP (Phase 3) done.

### Within each phase

- Tests (contract + integration) MUST be written and FAIL before implementation tasks they cover.
- Models / state machines before services that use them.
- Services before HTTP endpoints that compose them.
- HTTP endpoints before CLI subcommands that drive them.

### Parallel Opportunities

- Phase 1 setup tasks marked `[P]` (T002, T003, T005, T006) can run in parallel after T001 creates the directory layout.
- Phase 2 contract tests `[P]` (T007, T009, T011, T012, T014, T016, T018) can all run in parallel — they target different files.
- Phase 2 implementations (T008, T010, T013, T015, T017, T019, T020, T021) must wait for their corresponding contract tests; among themselves the protocol modules T013 / T015 / T017 / T019 are independent and can be parallelised once their tests have landed.
- Phase 3 contract tests T022 / T023 / T024 can run in parallel — different files.
- Phase 3 Gemini runner T025 (file: `runner.py`) and DelegationClient T027 (file: `client/delegation.py`) are independent of each other and can be parallelised once contract tests land.
- Phases 4 and 5 can run in parallel after Phase 2 completes (different developer sessions / different agents).
- Phase 6 tasks T037–T040 are all `[P]` and target different files / outputs.

---

## Parallel Example: Phase 2 contract tests

```text
# Spawn @python-tester to write all foundational contract tests in parallel:
Task: "T007 [P] Bearer-token compare contract test"
Task: "T009 [P] Auth middleware contract test"
Task: "T011 [P] JSON-RPC envelope contract test"
Task: "T012 [P] HTTP-level errors contract test"
Task: "T014 [P] Task state machine contract test"
Task: "T016 [P] AgentCard schema contract test"
Task: "T018 [P] SSE event framing contract test"
```

All seven write to different files under `services/a2a-bridge/tests/`, none depends on another, and they collectively gate the foundational phase per Principle III.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational) — contract tests gated, all green.
3. Complete Phase 3 (US1 — outbound Claude → Gemini delegation).
4. **STOP and VALIDATE**: Walk Steps 1–7 of `quickstart.md`. Confirm a Claude→Gemini delegation completes within 30s (SC-001) and fail-fast paths return within 5s (SC-006).
5. If those pass, the MVP is shippable.

### Incremental delivery

1. Setup + Foundational → foundation ready.
2. Add US1 (P1) → MVP, demo to self.
3. Add US2 (P2) → bidirectional, run `quickstart.md` Steps 1–6 plus 7.
4. Add US3 (P3) → discovery exercised, run `quickstart.md` Step 5.
5. Add Polish → concurrency, Inspector pass, README.

### Subagent dispatch model

- Every task with `Owner: @python-architect` MUST be dispatched via `Agent(subagent_type="python-architect", ...)` during `/speckit-implement`.
- Every task with `Owner: @python-tester` MUST be dispatched via `Agent(subagent_type="python-tester", ...)`.
- Tasks with `Owner: main` are executed in the main thread (cross-cutting orchestration, ADRs, manual validation passes).
- The main thread is responsible for sequencing, gating contract tests before impl, and surfacing failures across subagent boundaries.

---

## Notes

- `[P]` tasks = different files, no dependencies on uncommitted-by-another-task code.
- `[Story]` label maps task to a specific user story for traceability.
- `Owner` field maps task to a named subagent from `.specify/memory/agents.md`.
- Each user story is independently completable and testable; checkpoints between phases are mandatory pause points.
- Contract tests MUST fail before implementation begins (Constitution Principle III) — this is verified by running the test suite before each impl task lands.
- Commit after each task or logical group.
- Stop at any checkpoint to validate independently.
- Avoid: vague tasks, same-file conflicts within a `[P]` group, cross-story dependencies that break independence, missing Owner field.

---

## Total: 41 tasks

| Phase | Count | Owners |
|---|---|---|
| 1 — Setup | 6 | 5× @python-architect, 1× main |
| 2 — Foundational | 15 | 7× @python-tester, 8× @python-architect |
| 3 — US1 (P1, MVP) | 9 | 4× @python-tester, 5× @python-architect |
| 4 — US2 (P2) | 4 | 1× @python-tester, 3× @python-architect |
| 5 — US3 (P3) | 2 | 1× @python-tester, 1× @python-architect |
| 6 — Polish | 5 | 1× @python-tester, 4× main |

Owner distribution: 17× `@python-architect`, 14× `@python-tester`, 10× `main` (cross-cutting / scaffolding / docs / ADRs / manual passes).
