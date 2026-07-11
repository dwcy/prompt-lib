# Contract: Jobs & SSE Streams

Long-running operations and live streams. Contract tests: `tests/contract/test_webapi_jobs_sse_contract.py` — written first, observed failing (Gate 3).

## Job lifecycle

- Jobs are created ONLY by the backend: from an executed action ticket, or from read-side long operations (knowledge export/index, security scan refresh, provider clone, tool status sweep).
- States: `queued → running → succeeded | failed`; `queued|running → cancelled` via `POST /api/jobs/{id}/cancel` (auth + confirmation on the client; cancel is idempotent).
- Terminal jobs persist (SQLite) with `output_tail` (last 200 lines, redacted) and `exit_detail`; they survive backend restart and are listed by `GET /api/jobs` (FR-013, FR-052).
- At most one job per exclusive resource (e.g. one config apply at a time); a conflicting create → `409 job_conflict` with the blocking job id.

## SSE channels

- `GET /api/jobs/{id}/stream` — output + state of one job.
- `GET /api/services/{key}/logs/stream` — live service log tail.
- `GET /api/diagnostics/stream` — diagnostic feed for the shell status strip.

Transport rules:

1. `Content-Type: text/event-stream`; auth via `Authorization` header (EventSource polyfill/fetch-stream client) — token in query string is FORBIDDEN (would leak into logs).
2. Event grammar:
   - `event: output` `data: {"line": "<redacted line>", "seq": N}`
   - `event: state` `data: {"state": "running|succeeded|failed|cancelled", "exit_detail": "..."}`
   - `event: heartbeat` every ≤15 s (keeps proxies/webview alive; client marks stream stale after 2 missed beats)
3. Every `data` payload is JSON; every string is pre-redacted.
4. `Last-Event-ID` reconnect: client sends last `seq`; server replays from the ring buffer or, if evicted, sends `event: gap` with the count of dropped lines — never silently continues.
5. A stream for a terminal job emits current `state` immediately then closes; streaming a nonexistent job → `404` before stream start.

## Contract test assertions (minimum)

1. Job created via a fixture action passes through `queued/running` to a terminal state with monotonic `seq`.
2. Cancel on a running fixture job yields `state: cancelled` on the stream AND in `GET /api/jobs/{id}`.
3. Reconnect with `Last-Event-ID` replays without duplicates or silent gaps (gap event when forced eviction).
4. Seeded secret text emitted by a fixture subprocess is redacted in both stream events and persisted `output_tail`.
5. Terminal job survives backend process restart (SQLite round-trip) with state and tail intact.
6. Exclusive-resource conflict returns `409 job_conflict`.
