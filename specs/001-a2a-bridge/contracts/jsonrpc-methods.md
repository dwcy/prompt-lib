# A2A Bridge v1 — JSON-RPC 2.0 Methods

All methods are POSTed to `/jsonrpc` on each adapter, with `Authorization: Bearer <token>` and `Content-Type: application/json`. Requests follow JSON-RPC 2.0 (`jsonrpc: "2.0"`, `id`, `method`, `params`). Methods listed here are the entire surface the v1 bridge implements; any other method returns JSON-RPC error `-32601 Method not found`.

---

## `tasks/sendSubscribe`

Submit a new task and immediately open an SSE stream of lifecycle and artifact events.

**Request**:

```json
{
  "jsonrpc": "2.0",
  "id": "<client-chosen request id>",
  "method": "tasks/sendSubscribe",
  "params": {
    "task": {
      "messages": [
        { "role": "user", "content": "<prompt text>" }
      ]
    }
  }
}
```

**Initial HTTP response**:
- `200 OK`
- `Content-Type: text/event-stream`
- Body is an SSE stream as defined in `sse-events.md`. The first event is always `task.state` with `state: submitted` and a server-assigned `task_id`.

**Validation rules**:
- `params.task.messages` MUST be a non-empty array.
- `params.task.messages[0].role` MUST equal `"user"` for v1.
- `params.task.messages[0].content` MUST be a non-empty string.

**Errors**: see `error-codes.md`.

---

## `tasks/get`

Query the current state of a task by id. Used for polling clients and for adapter-to-adapter status checks.

**Request**:

```json
{
  "jsonrpc": "2.0",
  "id": "<client-chosen request id>",
  "method": "tasks/get",
  "params": { "task_id": "<server-assigned task id>" }
}
```

**Response (success)**:

```json
{
  "jsonrpc": "2.0",
  "id": "<echoed>",
  "result": {
    "task_id": "<id>",
    "state": "submitted | working | completed | failed | cancelled",
    "artifacts": [
      {
        "id": "<artifact id>",
        "kind": "text",
        "mime_type": "text/plain",
        "content": "<text payload>",
        "produced_at": "<RFC 3339 UTC>"
      }
    ],
    "created_at": "<RFC 3339 UTC>",
    "last_state_change_at": "<RFC 3339 UTC>"
  }
}
```

**Response (task unknown)**: JSON-RPC error `-32602 Invalid params` with `data: { reason: "task_not_found" }`.

---

## `tasks/cancel`

Request cancellation of a non-terminal task. The adapter terminates the underlying CLI subprocess and transitions the task to `cancelled`.

**Request**:

```json
{
  "jsonrpc": "2.0",
  "id": "<client-chosen request id>",
  "method": "tasks/cancel",
  "params": { "task_id": "<server-assigned task id>" }
}
```

**Response (success)**:

```json
{
  "jsonrpc": "2.0",
  "id": "<echoed>",
  "result": {
    "task_id": "<id>",
    "state": "cancelled",
    "cancelled_at": "<RFC 3339 UTC>"
  }
}
```

**Response (already terminal)**: JSON-RPC error `-32602 Invalid params` with `data: { reason: "task_already_terminal", state: "<current state>" }`.

---

## Discovery (NOT JSON-RPC, but in the contract surface)

`GET /.well-known/agent-card.json`

- No authentication required (per A2A spec; discovery is public).
- Returns the Agent Card JSON document validated against `agent-card.schema.json`.
- Status: `200 OK` with `Content-Type: application/json` on success; the only failure is server-not-running.

---

## Method-by-method conformance scope

| Method | A2A spec section | Our v1 conformance | Notes |
|---|---|---|---|
| `tasks/sendSubscribe` | A2A spec §9 (JSON-RPC binding) | Full conformance | Initial state is always `submitted` |
| `tasks/get` | A2A spec §9 | Full conformance for v1 task fields | Does NOT include `state_history` (capabilities flag is `false`) |
| `tasks/cancel` | A2A spec §9 | Full conformance | |
| GET `/.well-known/agent-card.json` | A2A spec §6 (Discovery) | Full conformance for the field subset in `agent-card.schema.json` | Optional fields the spec defines but v1 omits MUST NOT appear in the response (additionalProperties: false) |

Any deviation from full conformance during implementation MUST be recorded as an ADR per Constitution Principle I.
