# Phase 0 Research — Agent Orchestrator (002)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-05-10
**Status**: All NEEDS CLARIFICATION resolved (none were inserted by `/speckit-specify`).

This document records the technology decisions for v1, the rationale for each, and the alternatives considered. Each decision is keyed `R<n>` and referenced from `plan.md`, `data-model.md`, and `contracts/`.

---

## R1 — Orchestration framework: hand-rolled async pipeline (skip LangChain & LangGraph in v1)

**Decision**: v1 ships a hand-rolled `asyncio` pipeline (`Trigger → Agent → eventlog + notifier`). No LangChain. No LangGraph.

**Rationale**: v1 is a strictly linear flow with one trigger source, one agent role, one publisher per event. LangGraph buys branching, retry, checkpointing, and graph state — none of which v1 needs. Adopting LangGraph now would introduce `StateGraph`, `Channel`, `Checkpointer`, and a `GraphState` Pydantic model layer for a 200-line happy path. LangChain itself has shifted toward LangGraph for agent orchestration; using LangChain primitives directly is no longer the recommended modern pattern. The orchestrator's "agent" is Claude Code reached via the existing A2A bridge — Claude Code is the LLM-bearing component, the orchestrator is the dispatcher. Wrapping Claude Code in `langchain.ChatModel` would re-implement what `DelegationClient` already does.

**Alternatives considered**:
- **LangGraph for v1**: Rejected. Buys nothing v1 needs; locks the architecture to a graph state model that doesn't fit a single-node pipeline. Reconsider in v4 if/when the Issue → Plan → PR agent has real branching/retry needs.
- **LangChain Runnables (`RunnableSequence`, `RunnableLambda`)**: Rejected. Same overhead as LangGraph without the benefits. The composition we need is `async def` chaining — the language already provides it.
- **Temporal.io / Prefect / Dagster**: Rejected. Workflow engines aimed at distributed execution; v1 is a single localhost daemon.
- **A `Pipeline` class with hand-rolled state machine**: Rejected for v1 — premature abstraction. Promote to a real state machine if v2's PR-fix loop introduces retry semantics.

---

## R2 — Agent execution: A2A bridge `DelegationClient`, NOT `claude -p` subprocess

**Decision**: The orchestrator dispatches every agent run by calling `a2a_bridge.client.delegation.DelegationClient.delegate(prompt)` against a locally running Claude Code adapter (`a2a-bridge serve claude`, default `127.0.0.1:8765`). The orchestrator does NOT spawn `claude -p` directly.

**Rationale**: The existing A2A bridge (delivered by feature `001-a2a-bridge`, 199 tests passing, phases 1–6 complete) already exposes a typed async client returning structured SSE events (`message`, `state`, `complete`). These events are what the dashboard tails and what the eventlog persists. Subprocess parsing of `claude -p` stdout would require a regex/JSON-stream parser that the bridge already encapsulates — pure duplication. The bridge also handles bearer-token auth, SSE reconnection, and per-task timeout, all of which the orchestrator would otherwise re-implement.

**Alternatives considered**:
- **Subprocess (`asyncio.create_subprocess_exec("claude", "-p", prompt)`)**: Rejected. Forces the orchestrator to parse Claude Code's output format and own retry/timeout semantics. May return as a v2 fallback adapter if a non-A2A target is ever needed.
- **Direct Anthropic SDK call**: Rejected. Bypasses the local Claude Code agent definition, skills, and rules — the entire point of using *Claude Code* as the agent (vs. raw model calls) is that the agent inherits global skills (`/git`, `/pr`, `/review`) and the operator's CLAUDE.md preferences.

**Implications**:
- `services/orchestrator/pyproject.toml` adds `a2a-bridge` as a path dependency on the sibling `services/a2a-bridge/` package.
- Quickstart requires Terminal 1 to run `a2a-bridge serve claude` before Terminal 2 starts the orchestrator daemon.
- v1 `pr_review.py` builds the prompt with `gh pr diff <n>` text inlined and dispatches a single delegation call per PR head SHA.

---

## R3 — GitHub trigger: polling via `gh pr list --json`, NOT webhooks (v1)

**Decision**: v1 uses an async polling loop wrapping `gh pr list --state open --json number,headRefOid,updatedAt,title,url --repo <owner/repo>` every `ORCHESTRATOR_POLL_SECONDS` (default 30). New or changed `(pr_number, headRefOid)` tuples — diffed against an SQLite `cursor` table — emit `TriggerEvent`s. Webhooks are explicitly v2.

**Rationale**: Webhooks require the orchestrator to expose a public HTTPS endpoint; the operator runs on a Windows workstation behind NAT (FR-015) with no public ingress. A webhook-mode v1 would require ngrok/cloudflared/Cloudflare Tunnel as a hard prerequisite — non-trivial setup and an extra external dependency for a personal-use daemon. Polling at 30 s satisfies SC-001 (poll-to-notification ≤ 35 s) and works behind any NAT. The cost is a `gh pr list` call every 30 s — negligible given GitHub's 5,000 req/h authenticated rate limit (the orchestrator uses ~120 req/h).

The Trigger Protocol abstraction (R5) means a `WebhookTrigger` can be added in v2 as a drop-in `Trigger` implementation without touching `daemon.py` or `agents/pr_review.py`.

**Alternatives considered**:
- **Webhook receiver in v1 with ngrok/cloudflared**: Rejected. Adds a third-party dependency and a public endpoint to a localhost-only design. Defer to v2 when usage justifies it.
- **GitHub App with webhook**: Rejected for v1 (heavier setup, requires app registration, ownership model conflicts with personal-use intent). Could be the v2 production posture.
- **Polling the GitHub REST API directly with `httpx`**: Rejected. `gh` already handles OAuth/PAT, retries, and pagination. Re-implementing those is wasted effort.

**`gh pr list --json` output shape locked in `contracts/gh-pr-list.contract.md`** — Gate 3 contract test verifies our parser stays aligned with `gh`'s schema.

---

## R4 — Phone notifications: ntfy.sh public server, NOT Pushover/Telegram/Slack/email-to-push

**Decision**: v1 uses public `ntfy.sh` as the push transport. The operator chooses a topic name (treated as a low-grade secret), subscribes their phone via the ntfy iOS/Android app, and the orchestrator publishes via `POST https://ntfy.sh/<topic>` with priority + tags headers.

**Rationale**: ntfy is the lowest-friction option that meets the requirements:
- **No account**: the topic name is the only identifier; no signup, no API key.
- **Free**: public ntfy.sh has no rate-limited free tier — it's just free.
- **Open-source mobile app**: iOS and Android apps subscribe by topic; no SaaS lock-in.
- **HTTP POST with body**: trivial integration via `httpx.AsyncClient.post(url, content=body, headers={"Priority": ..., "Tags": ..., "Click": ..., "Title": ...})`.
- **Self-host upgrade path**: if topic-name leakage ever matters, the operator runs their own ntfy server and changes one env var.

**Alternatives considered**:
- **Pushover**: Rejected. Requires an account, an API key, and is paid (one-time fee). Higher friction for a personal-use daemon.
- **Telegram Bot**: Rejected. Requires bot creation via BotFather, a chat ID, and stored bot token (which we'd refuse to write to `.env`). More moving parts.
- **Slack incoming webhook**: Rejected. Mobile push is OK but requires a workspace and channel setup. Overkill for a single-user notifier.
- **Email-to-push (e.g., via SMTP to phone provider's MMS gateway)**: Rejected. Carrier-specific, fragile, slow, and US-centric.
- **APNs/FCM directly**: Rejected. Requires Apple/Google developer setup — absurd overhead.

**Level → ntfy priority mapping** (locked):
- `info` → priority `3` (default), tag `🔵`
- `warn` → priority `4` (high), tag `⚠️`
- `error` → priority `5` (max — vibrates phone), tag `🛑`
- `needs_input` → priority `5` (max), tag `❓`

**`ntfy-publish` contract pinned in `contracts/ntfy-publish.contract.md`**.

---

## R5 — Trigger abstraction: `typing.Protocol` returning `AsyncIterator[TriggerEvent]`

**Decision**: A `Trigger` `typing.Protocol` exposes a single async-iterator method:

```python
class Trigger(Protocol):
    async def events(self) -> AsyncIterator[TriggerEvent]: ...
```

`TriggerEvent` is a Pydantic v2 model: `kind: Literal["pr.opened", "pr.updated"]`, `repo: str`, `pr_number: int`, `head_sha: str`, `payload: dict[str, Any]`, `detected_at: datetime`. v1 ships `GithubPollTrigger`. v2 will ship `GithubWebhookTrigger`. Both implement the same Protocol; `daemon.py` consumes the iterator without knowing which trigger it has.

**Rationale**: An async iterator is the simplest typed-Python shape that matches "stream of events as they arrive". `Protocol` (PEP 544) gives structural typing — no inheritance from a base class, no `abc.ABCMeta`. The dispatch loop is trivially `async for event in trigger.events(): await dispatch(event)`. A future webhook trigger would be a `GithubWebhookTrigger` whose `events()` method returns an async iterator backed by an asyncio queue fed by a FastAPI route handler — same Protocol, completely different implementation.

**Alternatives considered**:
- **Callback-based `Trigger.subscribe(handler)`**: Rejected. Inversion of control makes the dispatch loop harder to reason about and complicates back-pressure.
- **`asyncio.Queue` directly without a Protocol**: Rejected. No type safety on the event shape; harder to test triggers in isolation.
- **`abc.ABC` base class**: Rejected. Inheritance is unnecessary; Protocol gives us all the typing without the runtime baggage.

---

## R6 — Event log: SQLite (stdlib `sqlite3`), append-only, polled by dashboard

**Decision**: `~/.claude/orchestrator/events.db` (override via `ORCHESTRATOR_DB_PATH`). One `events` table (`id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, run_id TEXT NOT NULL, kind TEXT NOT NULL, level TEXT NOT NULL, payload_json TEXT NOT NULL`), one `runs` table for the dashboard's run-status view, one `cursor` table (`pr_number INTEGER PRIMARY KEY, head_sha TEXT NOT NULL, last_seen TEXT NOT NULL`) for the polling trigger. Single-writer (the daemon) + multiple-reader (the dashboard) pattern. WAL mode enabled. The dashboard polls `tail_since(id)` on a 500 ms `set_interval`.

**Rationale**:
- **Stdlib only** — no extra dep, no service to start.
- **Survives restart of every component** — daemon, dashboard, OS reboot. Required by FR-006 / SC-008.
- **Debuggable with `sqlite3` CLI** — operator can `sqlite3 events.db "select * from events order by id desc limit 50"` to inspect history.
- **Append-only** — no UPDATE/DELETE on events (run-state transitions are NEW events; the `runs` view is computed). Simpler invariants, easier audit.
- **WAL mode** — single-writer + multi-reader is exactly WAL's sweet spot. No "database is locked" surprises.
- **Polling at 500 ms is fine** — even with 10 K events the table is trivially indexed by `id`. SQLite reads through WAL are non-blocking against the writer.

**Alternatives considered**:
- **In-process pub/sub (asyncio.Queue + WebSocket)**: Rejected. Forces dashboard to share a process with the daemon (or use a real network broker). Loses durability — a daemon crash erases history.
- **Redis pub/sub or NATS**: Rejected. External service for a single-user localhost daemon. Overkill.
- **JSONL file tail**: Rejected. No transactional cursor; dashboard would need to track byte-offsets and handle file truncation. SQLite's autoincrement `id` plus `tail_since(last_id)` is strictly simpler.
- **DuckDB**: Rejected. Cool, but solves analytics — overkill for an event tail.

---

## R7 — Dashboard: separate Textual process tailing the event log on a 500 ms `set_interval`

**Decision**: `orchestrator dash` is a separate Typer subcommand that launches a `textual.app.App`. Visual style mirrors the setup TUI: gradient banner header (style of `render_banner` lines 87–104), `DataTable` of recent runs, Textual `Log` widget for the event tail, status footer. Updates are polled via Textual's `set_interval(0.5, self._refresh)` calling `eventlog.tail_since(self._last_id)`. No Workers in v1 — SQLite reads are sub-millisecond and the timer pattern is the simplest correct shape.

**Rationale**:
- **Separate process** decouples crash domains: daemon can be killed and restarted without affecting the dashboard, and vice versa. The SQLite event log is the join point.
- **500 ms refresh** is well under SC-003's 1 s target with comfortable margin and is invisibly fast to a human eye.
- **`set_interval` not Workers** — simplifies the v1 code. We can promote to a Worker if profiling ever shows the timer blocking the UI thread (it won't for SQLite reads).
- **Style mirroring the setup wizard** keeps the operator's mental model consistent — both TUIs in this repo look like the same family of tools.

**Alternatives considered**:
- **Single-process Textual + asyncio orchestrator**: Rejected. Couples crash domains and complicates back-pressure between the agent loop and UI.
- **Web-based dashboard (Flask + browser)**: Rejected. Overkill; introduces an HTTP server, browser tab, and CORS dance for a single-user localhost daemon.
- **Plain `tail -f` of a JSONL log**: Rejected. Loses the structured-data view (runs table, status footer, level coloring) that the operator actually wants.

---

## R8 — Configuration: `pydantic-settings` from environment only — NEVER `.env` files

**Decision**: All config is read via `pydantic_settings.BaseSettings` from process env. No `.env` files are read OR written by the orchestrator. Quickstart provides a copy-paste shell snippet (`$env:ORCHESTRATOR_REPO=...` / `export ORCHESTRATOR_REPO=...`) and explicit instructions to set them in the operator's shell profile.

**Rationale**: CLAUDE.md hard rule: "Never generate, write, or edit `.env` … files. … Provide exact copy-paste instructions and the content as a code block — do not write the file." Reading from env without ever materializing a `.env` file complies cleanly. Operators who want a `.env`-style workflow can use a tool like `direnv` themselves — outside the orchestrator's responsibility.

**Env vars** (all required unless marked):
- `ORCHESTRATOR_REPO` — `owner/repo` slug (required)
- `ORCHESTRATOR_NTFY_TOPIC` — string topic name on `ntfy.sh` (required)
- `ORCHESTRATOR_POLL_SECONDS` — int, default `30` (optional)
- `ORCHESTRATOR_DB_PATH` — path; default `~/.claude/orchestrator/events.db` (optional)
- `A2A_PEER_URL` — URL of the running Claude adapter; default `http://127.0.0.1:8765` (required if the default doesn't match)
- `A2A_BEARER_TOKEN` — bearer token configured for the running adapter (required)
- `ORCHESTRATOR_NTFY_BASE` — defaults to `https://ntfy.sh` (optional, for self-host)

**Alternatives considered**:
- **`.env` file via `python-dotenv`**: Rejected per CLAUDE.md.
- **Config file (TOML / YAML)**: Rejected. Adds a parser, a file path to manage, and a place for secrets to leak. Env vars are the universal Python service convention.
- **CLI flags only**: Rejected. Operator would need to remember every flag on every invocation; daemon vs dashboard would need duplicate flags.

---

## R9 — Test strategy: contract / integration / unit, with `INTEGRATION=1` gate

**Decision**: Three test directories under `tests/`:
- `tests/contract/` — Constitution Gate 3 surface conformance. Uses `httpx.MockTransport` for ntfy and a fake `gh` script (Python entry-point on PATH that emits canned JSON) for `gh pr list`. These tests pin the parser/builder against the documented external schemas and run on every CI pass.
- `tests/integration/` — Real subprocess + real test repo. Gated by `INTEGRATION=1` env var and skipped by default. Run manually before each release per the quickstart.
- `tests/unit/` — Everything else (config, eventlog row math, notifier level mapping, trigger diff logic). pytest + pytest-asyncio.

**Rationale**: Mirrors the proven test layout of `services/a2a-bridge/`. Gate 3 binds only the contract surface; unit tests stay optional per Constitution Principle III. Integration tests need credentials and a real repo, so gating them keeps CI runs fast and keeps PRs from accidentally creating test PRs against random repos.

**Alternatives considered**:
- **Property-based tests for ntfy/gh shapes (`hypothesis`)**: Considered for v2 once the schemas are stable; deferred for v1.
- **Mocking the entire A2A client**: Rejected — `001-a2a-bridge`'s tests already pin that surface; we instead use a tiny `FakeDelegationClient` that yields canned SSE events, ensuring our consumer logic is covered without re-testing the bridge.

---

## R10 — Run identity & cursor: `run_id` is a UUIDv7; the polling cursor is keyed by `(repo, pr_number)`

**Decision**: Each `Run` has `run_id: UUID` generated as UUIDv7 (time-ordered, sortable by creation). The polling cursor stores `(pr_number, head_sha, last_seen)` per repo; a head-SHA change is the trigger condition for `pr.updated`. PR closure is detected by absence in the `--state open` poll output — closed PRs are NOT marked failed; their open runs are left as-is (the next poll simply doesn't re-emit them).

**Rationale**: UUIDv7 (RFC 9562) gives sortable primary keys without `id INTEGER AUTOINCREMENT`-style coupling between event-log row order and run order; helps when multiple runs interleave. `(pr_number, head_sha)` is the minimum unique key for "this commit on this PR has not been reviewed yet" — we don't depend on `updatedAt` (which can shift for non-code reasons).

**Alternatives considered**:
- **UUIDv4**: Rejected. Loses the time-ordering useful for debugging.
- **Monotonic int run_id**: Rejected. Couples run identity to the event-log sequence — fine for v1, awkward if multiple workers ever run.
- **Last-event timestamp as cursor**: Rejected. Time-based cursors are brittle under clock skew and missed events.

---

## Summary table

| Decision | Choice | Status |
|---|---|---|
| R1 | Hand-rolled async pipeline (no LangChain/LangGraph) | LOCKED for v1 |
| R2 | A2A bridge `DelegationClient` for agent execution | LOCKED |
| R3 | Polling via `gh pr list --json` (no webhooks v1) | LOCKED |
| R4 | ntfy.sh public server for phone push | LOCKED |
| R5 | `typing.Protocol` Trigger + `AsyncIterator[TriggerEvent]` | LOCKED |
| R6 | SQLite (stdlib) append-only event log, WAL mode | LOCKED |
| R7 | Separate Textual dashboard process, 500 ms `set_interval` | LOCKED |
| R8 | `pydantic-settings` env-only; no `.env` ever | LOCKED |
| R9 | Three test tiers; `INTEGRATION=1` gate | LOCKED |
| R10 | UUIDv7 run_id; `(pr_number, head_sha)` cursor | LOCKED |
