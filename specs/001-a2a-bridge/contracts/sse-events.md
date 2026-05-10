# A2A Bridge v1 — SSE Event Stream

Server-Sent Events emitted on the response body of `tasks/sendSubscribe`. Each event is a `data:` line containing JSON. Events are framed per the SSE spec: `event:` line, `data:` line, blank line.

---

## Event types

### `task.state`

Emitted on every Task state transition. ALWAYS the first event of a stream (with `state: submitted`) and ALWAYS the last (with one of the terminal states).

```
event: task.state
data: {
  "task_id": "<UUIDv4>",
  "state": "submitted | working | completed | failed | cancelled",
  "ts": "<RFC 3339 UTC>",
  "reason": "<optional, only for failed/cancelled>"
}
```

**Reason payloads** (only present on `failed` or `cancelled`):
- `cancelled` — `reason` is one of: `client_cancelled`, `timeout`.
- `failed` — `reason` is one of: `cli_nonzero_exit`, `cli_malformed_output`, `internal_error`. The `data` object MAY include `exit_code: <int>` for `cli_nonzero_exit`, and `stderr_tail: "<last N chars of stderr>"` for any failure (truncated to 1024 chars).

### `task.artifact`

Emitted when the adapter has finalized an artifact from CLI output. Multiple `task.artifact` events MAY appear in a single stream (one per artifact produced). For v1 the Claude adapter emits exactly one `task.artifact` per task, immediately before the terminal `task.state`.

```
event: task.artifact
data: {
  "task_id": "<UUIDv4>",
  "artifact": {
    "id": "<UUIDv4>",
    "kind": "text",
    "mime_type": "text/plain | text/markdown",
    "content": "<text payload>",
    "produced_at": "<RFC 3339 UTC>"
  }
}
```

### `task.progress` (OPTIONAL for v1)

Free-form working progress updates derived from CLI streaming output. Adapters MAY emit any number of `task.progress` events between `task.state: working` and the terminal `task.state`. Clients MUST NOT depend on the content or count of `task.progress` events; they exist for UX only.

```
event: task.progress
data: {
  "task_id": "<UUIDv4>",
  "message": "<short human-readable progress note>",
  "ts": "<RFC 3339 UTC>"
}
```

v1 contract tests do NOT assert anything about `task.progress` other than that it is well-formed JSON if emitted.

---

## Stream framing rules

- The HTTP response opens with status `200`, `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Every event group ends with one blank line (`\n\n`).
- Comment-style keep-alive pings (`: keep-alive\n\n`) MUST be sent every 15 seconds the stream is idle.
- The stream MUST close cleanly within 1 second after the terminal `task.state` event.

---

## Event ordering rules

Within a single task's stream, the contract enforces:

1. The first event is always `task.state` with `state: submitted`.
2. At most one `task.state` with `state: working` follows.
3. Zero or more `task.progress` events MAY appear after `working`.
4. Zero or more `task.artifact` events MAY appear after `working`.
5. The last event is always `task.state` with one of the terminal states.
6. After the terminal `task.state`, NO further events are emitted; the stream is closed.

A contract test asserts this ordering for the happy path, the timeout-cancellation path, and the CLI non-zero-exit path.

---

## Per-event-type conformance scope

| Event | A2A spec mapping | v1 conformance | Notes |
|---|---|---|---|
| `task.state` | A2A spec §9 task lifecycle | Full conformance for the 5 v1 states | No state-history beyond the live transition |
| `task.artifact` | A2A spec §8 artifact framing | Full conformance for `kind: text` only | Other artifact kinds are out of scope (see contracts/README.md) |
| `task.progress` | A2A spec §9 working updates | Optional; v1 does NOT guarantee emission | Marked OPTIONAL in this contract so adapter implementations can defer it |

Any deviation from this contract during implementation MUST be recorded as an ADR per Constitution Principle I.
