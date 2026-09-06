# Contract: Run Progress SSE Events

**Surface**: job output streams served by `cabal.webapi.sse` for job kinds `codegen.run` and `evals.matrix`.  
**Contract tests**: `tests/contract/test_run_events.py` — MUST be written and observed failing before implementation (Constitution Gate 3).

---

## The governing constraint

The stream is **for liveness, not for the record** (research.md R4). Three properties of the existing infrastructure make this non-negotiable:

- `DEFAULT_RING_BUFFER_SIZE = 200` and `OUTPUT_TAIL_LIMIT = 200` — an eval matrix produces far more than 200 lines, so the stream *structurally cannot* hold the full history.
- `JOB_STREAM_SEGMENT_MAX_S = 30.0` — each response closes after 30 seconds; the client reconnects with `Last-Event-ID`.
- A client that was closed missed those frames entirely, and no replay can recover them.

**Therefore**: a client MUST be able to rebuild current state from *the artifact tree plus events since its last id*. Any design that requires having seen every frame is wrong.

This is the property the contract test exists to protect: connect, disconnect for longer than the ring buffer's depth, reconnect, and assert the client reaches correct state.

---

## Event types

Emitted as structured events, never scraped from log text. All payloads are JSON and pre-redacted by the existing `redact_value`.

### `run.progress` — codegen

```json
{ "run_id": "…", "stage": "architect", "stage_index": 2, "stage_count": 5, "status": "running" }
```

**Contract**: carries absolute position (`stage_index` of `stage_count`), not a delta. A client joining mid-run knows where things stand from one frame.

### `run.gate` — codegen

```json
{ "run_id": "…", "token": "…", "files": [ … ] }
```

Emitted when the pipeline pauses at the approval gate.

**Contract**: this event is a **notification, not the gate itself**. The durable gate is the on-disk pending intent (research.md R3), readable at `GET /api/codegen/pending`. A client that missed this frame still finds the gate. The contract test asserts the gate is discoverable with the stream never connected at all.

### `cell.complete` — evals

```json
{ "run_id": "…", "task": "…", "profile": "baseline", "repetition": 0, "outcome": "passed",
  "completed": 7, "total": 24 }
```

**Contract**: carries absolute `completed`/`total`, so progress is correct for a client that missed earlier cells. The authoritative completion set remains the cell directories on disk; this event is an invitation to re-read, not a substitute for reading.

### `run.state` — both

```json
{ "run_id": "…", "state": "succeeded" }
```

`state` ∈ `running` | `succeeded` | `failed` | `cancelled` | `interrupted`.

**Contract**: `interrupted` is emitted only by **read-time reconciliation** (research.md R2), never by the run itself — a process that died cannot report its own death. It is a presentation state and is **not** written to the `jobs` table's state column.

### `output.append` — both

A tail of human-readable output for the user watching now.

**Contract**: explicitly lossy. Consumers MUST NOT parse it for state. Anything a client needs is in a structured event or an artifact file.

---

## Reconnection

Standard `Last-Event-ID` per the existing grammar, with heartbeats every 10s within a segment.

**Contract**:
- A gap (requested id older than the ring buffer holds) is signalled explicitly, so the client knows to re-read artifacts rather than assuming continuity.
- A silent gap is a defect: it would let a client believe it has a complete picture when it does not.

---

## What is deliberately absent

**No `cost.update` event.** Cost is read from the run record after the fact (`contracts/codegen-api.md`). Streaming live cost would create a second, un-reconciled source for figures that SC-010 requires to match the CLI exactly.
