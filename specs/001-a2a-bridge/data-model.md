# Phase 1 Data Model — A2A Bridge v1

**Feature**: A2A Bridge for Multi-Agent CLI Delegation (v1)
**Branch**: `001-a2a-bridge`
**Date**: 2026-05-10

Entities, fields, relationships, and state transitions for the v1 bridge. All entities are in-memory (FR-010); no persistence layer in v1.

---

## Entity: Task

A unit of work submitted to an adapter over the A2A wire.

**Fields**:
| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | UUIDv4 | adapter-generated on receipt | Returned in initial JSON-RPC response and on every subsequent SSE event |
| `method` | str | request | A2A method invoked (`tasks/send`, `tasks/sendSubscribe`, `tasks/get`, `tasks/cancel`) |
| `params` | dict | request | Validated against the per-method JSON schema in `contracts/` |
| `state` | enum | adapter-managed | One of: `submitted`, `working`, `completed`, `failed`, `cancelled` |
| `created_at` | datetime UTC | adapter | Used for timeout calculation and stdout logs |
| `last_state_change_at` | datetime UTC | adapter | Updated on every state transition |
| `peer_identity` | str | request (auth) | Bearer-token-mapped identifier (v1: a single identifier per token) |
| `process` | `asyncio.subprocess.Process` or None | adapter | The spawned CLI process; `None` after terminal state |
| `event_queue` | `asyncio.Queue[TaskEvent]` | adapter | One queue per task; SSE handler drains it |
| `artifacts` | list[Artifact] | adapter | Accumulated as the CLI emits output; finalized at terminal state |

**State transitions** (mandated by A2A spec, no extensions):

```
            submitted ──► working ──► completed
                │            │
                │            ├────► failed
                │            │
                └────────────└────► cancelled
```

**Transition rules**:
- `submitted → working`: emitted as soon as the CLI subprocess is spawned and writing.
- `working → completed`: CLI exited with code 0 and produced at least one artifact.
- `working → failed`: CLI exited with non-zero, OR adapter received malformed CLI output, OR a non-cancellation exception was raised mid-stream.
- `working → cancelled`: per-task timeout exceeded, OR explicit `tasks/cancel` JSON-RPC call received.
- Terminal states (`completed`, `failed`, `cancelled`) are sticky — no further transitions, event queue is closed.

**Validation**:
- `id` MUST be unique within the adapter process lifetime (UUIDv4 collision is the only concern; we accept the negligible probability).
- A task in any terminal state MUST NOT have a live `process` reference; the subprocess is reaped before the transition is emitted.

---

## Entity: Artifact

A structured output produced by a Task and emitted on the SSE stream.

**Fields**:
| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | UUIDv4 | adapter-generated | Each artifact has a stable id within its parent task |
| `task_id` | UUIDv4 | parent Task | FK to Task |
| `kind` | enum | adapter | One of: `text`, `file_reference`, `structured` (v1 ships only `text`) |
| `mime_type` | str | adapter | `text/plain` or `text/markdown` for v1 |
| `content` | str or dict | CLI output | The actual payload (v1: always str) |
| `produced_at` | datetime UTC | adapter | Timestamp of emission |

**Validation**:
- `kind = file_reference` requires `content` to be an absolute filesystem path that exists at emission time. v1 does not emit this kind; it is enumerated for forward-compat.
- `content` MUST be UTF-8-decodable text for `kind = text`.

---

## Entity: Adapter

The HTTP server wrapping a single CLI agent.

**Fields**:
| Field | Type | Source | Notes |
|---|---|---|---|
| `name` | str | config | E.g. `"claude-code"`, `"gemini"`. Surfaces in Agent Card |
| `bind_host` | str | config | Default `127.0.0.1` (v1 is localhost-only per FR-009) |
| `bind_port` | int | config | Per-adapter; default 8765 (claude), 8766 (gemini) |
| `bearer_token` | str | env (`A2A_BEARER_TOKEN`) | Required at startup; missing → adapter refuses to start |
| `cli_command` | list[str] | per-adapter constant | E.g. `["claude", "-p", "--bare", "--output-format", "stream-json", "--verbose"]` |
| `task_timeout_seconds` | int | config | Default 300; per-task; enforced by the adapter |
| `tasks` | dict[UUID, Task] | runtime | All tasks the adapter has handled in this process lifetime |
| `agent_card` | AgentCard | runtime | Built once at startup; served at `/.well-known/agent-card.json` |

**Validation**:
- Adapter MUST refuse to start if `A2A_BEARER_TOKEN` is unset or empty.
- Adapter MUST refuse to start if its underlying CLI is not on PATH.
- Adapter SHOULD log to stdout the bind address, the resolved CLI path, and the configured timeout at startup.

---

## Entity: AgentCard

The discovery document published at `/.well-known/agent-card.json`.

**Fields** (subset of A2A v1.0.0 Agent Card schema; full schema in `contracts/agent-card.schema.json`):
| Field | Type | Source | Notes |
|---|---|---|---|
| `name` | str | Adapter.name | E.g. `"claude-code-a2a-adapter"` |
| `description` | str | constant per adapter | Human-readable purpose |
| `url` | str | computed | `http://{bind_host}:{bind_port}` |
| `version` | str | constant | `"1.0.0"` (bridge version, not A2A spec version) |
| `protocols` | list[str] | constant | `["json-rpc-2.0"]` for v1 (gRPC and REST not implemented) |
| `capabilities` | object | constant | `{"streaming": true, "push_notifications": false, "state_history": false}` |
| `authentication` | object | constant | `{"schemes": ["bearer"]}` |
| `skills` | list[object] | per-adapter constant | Declares the high-level operations the wrapped CLI can perform |

**Validation**:
- Card MUST validate against the JSON schema fragment in `contracts/agent-card.schema.json` at adapter startup; failure prevents start.

---

## Entity: DelegationClient

The host-side component that sends an A2A task to a peer adapter and reconciles the response.

**Fields**:
| Field | Type | Source | Notes |
|---|---|---|---|
| `peer_url` | str | CLI arg or env | E.g. `http://127.0.0.1:8766` |
| `peer_bearer_token` | str | env (`A2A_PEER_BEARER_TOKEN`) | Distinct from the local adapter's token if peer is on a different trust boundary |
| `http_client` | `httpx.AsyncClient` | runtime | Reused across delegations within one CLI invocation |
| `current_task_id` | UUID or None | runtime | Set after the peer's initial JSON-RPC response |

**Behaviour**:
- Builds a JSON-RPC `tasks/sendSubscribe` request, opens an SSE connection, and pipes streamed events to stdout (or to a structured callback when used as a library).
- Surfaces failures (connect, auth, malformed response) as distinct exit codes so calling shells can branch on them.

---

## Entity: BearerToken

A shared secret used to authenticate adapter-to-adapter requests. Not an entity in the persistence sense — modelled as a string read from an environment variable at startup.

**Validation**:
- Token comparison MUST use `hmac.compare_digest` (constant-time) to avoid timing leaks.
- Tokens MUST be at least 32 bytes of entropy (32 hex chars / 24 base64 chars). Adapter logs a warning at startup if the configured token is shorter.
- Tokens are NEVER logged. Logs may indicate "auth ok" / "auth failed" but never the token value or any prefix/suffix of it.

---

## Relationships

```
Adapter 1 ──── * Task
Task    1 ──── * Artifact
Adapter 1 ──── 1 AgentCard
DelegationClient ──── (sends tasks to) ──── peer Adapter (over HTTP)
```

No relationship is persisted between process restarts (FR-010). The DelegationClient is created per CLI invocation and torn down with the process.
