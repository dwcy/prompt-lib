# Data Model — Agent Orchestrator (002)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)
**Date**: 2026-05-10

This document defines the entities the orchestrator persists, validates, and exchanges. Storage details (SQLite schema, indexes) appear here; wire-format details for external surfaces appear under [`contracts/`](./contracts/).

---

## Entities

### TriggerEvent

A normalized event emitted by a `Trigger` source describing something the orchestrator should react to. Pure in-memory; never persisted directly (the resulting `Run` and its `Event`s are persisted instead).

| Field | Type | Validation | Notes |
|---|---|---|---|
| `kind` | `Literal["pr.opened", "pr.updated"]` | required, enum | More kinds added in v2/v3 (`pr.review_received`, `issue.opened`). |
| `repo` | `str` | matches `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` | Same `owner/repo` slug `gh` uses. |
| `pr_number` | `int` | `> 0` | GitHub PR number. |
| `head_sha` | `str` | matches `^[0-9a-f]{40}$` | Full 40-char SHA. |
| `payload` | `dict[str, Any]` | optional; default `{}` | Source-specific extras (e.g., raw `gh pr list` row, webhook envelope). |
| `detected_at` | `datetime` | timezone-aware UTC | Set by the trigger when the event is created. |

**Relationships**: 1 `TriggerEvent` → 1 `Run` (the dispatch creates exactly one run per event).

**Lifecycle**: ephemeral; lives in-memory only between trigger emission and dispatch.

---

### Run

A single end-to-end execution of an agent in response to one `TriggerEvent`. Persisted (write-through to the event log, materialized via the `runs` view).

| Field | Type | Validation | Notes |
|---|---|---|---|
| `run_id` | `UUID` (v7) | required | Time-ordered. |
| `kind` | `Literal["pr.review"]` | required, enum | `pr.fix`, `issue.plan_pr` added in v2/v3. |
| `repo` | `str` | matches `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` | Copied from the `TriggerEvent`. |
| `pr_number` | `int` | `> 0` | Copied from the `TriggerEvent`. |
| `head_sha` | `str` | matches `^[0-9a-f]{40}$` | Copied from the `TriggerEvent`. |
| `state` | enum (see state machine below) | required | Computed from the latest terminal event for this `run_id`. |
| `started_at` | `datetime` | timezone-aware UTC | Set when the dispatcher emits `run.started`. |
| `ended_at` | `datetime \| None` | timezone-aware UTC; `None` until terminal | Set when the run reaches a terminal state. |
| `artifact_url` | `str \| None` | URL or `None` | Permalink to the posted PR review comment, if any. |

**State machine**:

```
pending ──► running ──► completed
              │      └► failed
              │      └► skipped     (e.g. PR closed mid-run)
              └► orphaned             (only on daemon-restart cleanup)
```

- `pending`: a `run.queued` event was written but no `run.started` yet. (v1 dispatches synchronously, so this state is rare in practice.)
- `running`: at least one `run.started` event but no terminal event yet.
- `completed`: a `run.completed` event has been written; `artifact_url` is set.
- `failed`: a `run.failed` event has been written with a captured error reason.
- `skipped`: a `run.skipped` event has been written (the dispatcher decided not to post — e.g. PR closed before review could be posted).
- `orphaned`: NOT emitted by the daemon during normal operation. On daemon startup, any run whose latest event is `running`-implying with no terminal event AND whose started_at is older than the daemon's previous shutdown, has an `run.orphaned` event written by the recovery routine. This represents the "killed mid-run" case from FR-013 / SC-007.

**Persistence**: Runs are NOT a separately-mutated table. They are derived from the `events` table. A `runs` SQLite VIEW (or simple query helper in `eventlog.py`) computes the latest state per `run_id`.

**Relationships**: 1 `Run` → many `Event`s.

---

### Event

A timestamped, structured record of something that happened during a `Run`. Persisted append-only in the `events` table.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `id` | `int` | autoincrement primary key | Used by the dashboard's `tail_since(id)` cursor. |
| `ts` | `datetime` | ISO 8601 UTC string | Set by `eventlog.append_event()`. |
| `run_id` | `UUID` | required | Foreign key to the conceptual `Run`. |
| `kind` | `str` | enum (see below) | Open-ended namespace; v1 set listed below. |
| `level` | `Literal["info", "warn", "error", "needs_input"]` | required | Drives notifier priority mapping. |
| `payload_json` | `str` | valid JSON | Free-form structured data; per-kind shape documented inline. |

**v1 event kinds**:

| Kind | Level | Payload shape | Emitted by |
|---|---|---|---|
| `run.queued` | `info` | `{repo, pr_number, head_sha, kind: "pr.review"}` | `daemon.dispatch` (immediately on receiving `TriggerEvent`) |
| `run.started` | `info` | `{repo, pr_number, head_sha, peer_url}` | `agents.pr_review.run` (after building prompt, before delegation) |
| `agent.message` | `info` | `{text, partial: bool}` | `agents.pr_review.run` (one per `DelegationClient` SSE message event) |
| `agent.state` | `info` | `{state: "submitted" \| "working" \| ...}` | `agents.pr_review.run` (one per SSE state event) |
| `gh.review.posted` | `info` | `{artifact_url, comment_length}` | `agents.pr_review.run` (after successful `gh pr review`) |
| `run.completed` | `info` | `{artifact_url, duration_seconds}` | `agents.pr_review.run` (terminal) |
| `run.failed` | `error` | `{error: str, stage: "delegate" \| "post" \| "config"}` | `agents.pr_review.run` (terminal) |
| `run.skipped` | `warn` | `{reason: "pr_closed" \| "head_sha_changed" \| ...}` | `agents.pr_review.run` (terminal) |
| `run.orphaned` | `warn` | `{prior_state: "running"}` | `eventlog.recover_orphans()` on daemon start |
| `auth.failed` | `error` | `{which: "gh" \| "a2a", detail: str}` | `agents.pr_review.run` or `triggers.github_poll` |
| `push.failed` | `warn` | `{topic, status_code, detail}` | `notifier.send` (non-fatal) |

**Indexes** (created at schema bootstrap):
- `events_pk` — implicit on `id`
- `events_by_run` — `(run_id, id)` for the runs view
- `events_by_ts` — `(ts)` for time-ordered scans

**Why append-only**: any "state change" of a Run is just a new `Event` (e.g., `run.started` then later `run.completed`). The latest terminal event per `run_id` defines the run's current `state`. This eliminates UPDATE concurrency races and makes the audit trail trivial.

---

### Cursor

The polling-trigger bookmark: which `(pr_number, head_sha)` tuples we've already seen. Persisted in the `cursor` table.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `pr_number` | `int` | primary key, `> 0` | One row per open PR. |
| `head_sha` | `str` | matches `^[0-9a-f]{40}$` | The most recent head SHA we've reviewed (or attempted to review). |
| `last_seen` | `datetime` | UTC | Updated every poll where the PR is still open with this SHA. |

**Diff logic** (in `triggers/github_poll.py`):
- For each PR returned by `gh pr list --state open --json …`:
  - If `pr_number` is not in the cursor → emit `pr.opened`, insert row.
  - If `pr_number` is in the cursor with the same `head_sha` → no emit, update `last_seen`.
  - If `pr_number` is in the cursor with a different `head_sha` → emit `pr.updated`, update row.
- For each row in the cursor whose `pr_number` is NOT in the current poll → leave the row in place (or optionally archive it after N polls of absence — TBD in v2).

---

### Notification

A push-service message derived from an `Event` whose kind warrants out-of-band attention. Not persisted as its own entity (notifications are derived; failures to deliver are logged as `push.failed` events).

| Field | Type | Validation | Notes |
|---|---|---|---|
| `topic` | `str` | required, non-empty | From `ORCHESTRATOR_NTFY_TOPIC`. |
| `level` | `Literal["info", "warn", "error", "needs_input"]` | required | Mirrors the originating Event's level. |
| `title` | `str` | ≤ 200 chars | Short headline. |
| `body` | `str` | ≤ 1024 chars | One-line message; longer content goes in the dashboard, not the push. |
| `click_url` | `str \| None` | URL or `None` | Usually the PR URL on GitHub. |

**Level → ntfy priority + tags** (see `contracts/ntfy-publish.contract.md`):

| Level | ntfy priority header | tags |
|---|---|---|
| `info` | `3` | `🔵` |
| `warn` | `4` | `⚠️` |
| `error` | `5` | `🛑` |
| `needs_input` | `5` | `❓` |

**Which Events trigger a Notification (v1 policy)**:

| Event kind | Push? | Title | Body |
|---|---|---|---|
| `run.queued` | NO | — | Skipped to avoid two notifications per run. |
| `run.started` | YES (info) | `Reviewing PR #N` | `<repo> · <head_sha[:7]>` |
| `agent.message` | NO | — | Way too chatty for push. |
| `agent.state` | NO | — | Same. |
| `gh.review.posted` | NO | — | Combined with `run.completed`. |
| `run.completed` | YES (info) | `Review posted on PR #N` | `<duration>s · <comment_length> chars` |
| `run.failed` | YES (error) | `PR #N review FAILED` | `<error[:120]>` |
| `run.skipped` | YES (warn) | `PR #N review skipped` | `<reason>` |
| `run.orphaned` | YES (warn) | `Orphaned run for PR #N` | `Daemon restart left a run mid-flight` |
| `auth.failed` | YES (error) | `Auth failed: <which>` | `<detail[:160]>` |
| `push.failed` | NO | — | Cannot push that we couldn't push. Logged only. |

---

### TriggerSource

Not a runtime entity — a `typing.Protocol` defining the contract every trigger implementation must satisfy. Documented here for reference; full type definition lives in `src/orchestrator/triggers/base.py`.

```python
from typing import AsyncIterator, Protocol

class Trigger(Protocol):
    async def events(self) -> AsyncIterator[TriggerEvent]: ...
    async def aclose(self) -> None: ...
```

v1 ships exactly one implementation: `triggers.github_poll.GithubPollTrigger`. v2 will add `triggers.github_webhook.GithubWebhookTrigger`. Both are interchangeable to `daemon.py`.

---

## SQLite schema (DDL)

Locked into `eventlog.py`'s schema-bootstrap function; created on first daemon start.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = OFF;        -- runs is a view, not a real FK target
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,            -- ISO 8601 UTC
    run_id       TEXT    NOT NULL,            -- UUIDv7 string
    kind         TEXT    NOT NULL,
    level        TEXT    NOT NULL CHECK (level IN ('info','warn','error','needs_input')),
    payload_json TEXT    NOT NULL             -- JSON-encoded
);

CREATE INDEX IF NOT EXISTS events_by_run ON events (run_id, id);
CREATE INDEX IF NOT EXISTS events_by_ts  ON events (ts);

CREATE TABLE IF NOT EXISTS cursor (
    pr_number  INTEGER PRIMARY KEY,
    head_sha   TEXT    NOT NULL,
    last_seen  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
```

A simple computed `runs` view (or an equivalent `eventlog.runs_summary()` query) returns:

```sql
SELECT
    run_id,
    json_extract(payload_json, '$.repo')      AS repo,
    json_extract(payload_json, '$.pr_number') AS pr_number,
    json_extract(payload_json, '$.head_sha')  AS head_sha,
    MIN(CASE WHEN kind = 'run.started' THEN ts END)             AS started_at,
    MAX(CASE WHEN kind LIKE 'run.completed' THEN ts END)        AS completed_at,
    -- ... state derivation, see eventlog.py
FROM events
GROUP BY run_id;
```

The exact query lives in `eventlog.py` to keep it testable in Python.

---

## Validation rules

All Pydantic models live in `src/orchestrator/` next to the code that uses them:
- `TriggerEvent` — `triggers/base.py`
- `Run`, `Event`, `Notification` — `eventlog.py` (request/response shapes for the log API)

Models use Pydantic v2 with `model_config = ConfigDict(frozen=True, extra='forbid')` to make event payloads immutable and reject typos at construction time.

Free-form `payload` and `payload_json` fields are NOT typed at the model layer — per-kind payload shape is documented in this file (the `events` kind table) and validated by per-kind helper functions in `agents/pr_review.py` (e.g., `emit_run_completed(eventlog, run_id, *, artifact_url, duration_seconds)` which builds the payload dict with type-checked args).

This keeps the schema simple (one `events` table, one column per metadata field) while still letting the Python layer enforce per-kind shapes at call sites.
