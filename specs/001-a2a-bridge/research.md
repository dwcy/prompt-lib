# Phase 0 Research — A2A Bridge v1

**Feature**: A2A Bridge for Multi-Agent CLI Delegation (v1)
**Branch**: `001-a2a-bridge`
**Date**: 2026-05-10

This file resolves all `NEEDS CLARIFICATION` items from `plan.md` Technical Context. Format: Decision → Rationale → Alternatives considered.

---

## R1 — A2A protocol spec version and conformance scope

**Decision**: Target **A2A v1.0.0** (released 2026-03-12), JSON-RPC 2.0 binding only for v1. Canonical specification document: <https://a2a-protocol.org/latest/specification/>. Conformance scope = the JSON-RPC binding plus Agent Card discovery; gRPC and HTTP+JSON/REST bindings are explicitly **out of scope** for v1.

**Rationale**:
- v1.0.0 is the first stable release and the version every other implementation will target in 2026. Picking it avoids needing a v0→v1 migration mid-project.
- JSON-RPC 2.0 is the most widely supported binding, the easiest to test with `curl`, and the natural fit for FastAPI's request/response model.
- The Agent Card discovery path moved from `/.well-known/agent.json` (pre-1.0) to **`/.well-known/agent-card.json`** in v0.3.0 and remains so in v1.0.0. We adopt the new path; no compatibility shim for the old one.
- A2A is governed by the Linux Foundation as of June 2025 — stable governance, no Google-only risk.

**Alternatives considered**:
- *Target v0.2.x for compatibility with older clients* — rejected: no evidence of any peer agent stuck on v0.2.x; would carry technical debt forever.
- *Implement all three bindings (JSON-RPC + gRPC + HTTP+JSON)* — rejected for v1: 3× the surface, 3× the contract tests, no requirement for it. v2 can add bindings as peers demand them.
- *Implement only HTTP+JSON/REST* — rejected: spec describes JSON-RPC as the reference binding and the test client (Inspector) targets it first.

---

## R2 — FastAPI SSE pattern for streaming task updates

**Decision**: Use **`fastapi.sse.EventSourceResponse`** (native, shipped in FastAPI ≥0.135.0). Pin `fastapi >= 0.135` in `pyproject.toml`. Do not pull in `sse-starlette`.

**Rationale**:
- Native FastAPI support means one fewer dependency, automatic keep-alive pings, automatic no-cache and proxy-buffering headers, and direct Pydantic-model serialization into the SSE `data:` field.
- `sse-starlette` is still a valid choice for older FastAPI versions, but pinning to ≥0.135 costs nothing (we are starting fresh) and gives us the documented native API.

**Recommended pattern** (from FastAPI docs):

```python
from collections.abc import AsyncIterable
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel

app = FastAPI()

class TaskUpdate(BaseModel):
    state: str
    message: str | None = None

@app.get("/tasks/{task_id}/stream", response_class=EventSourceResponse)
async def stream_task(task_id: str) -> AsyncIterable[TaskUpdate]:
    async for update in task_event_source(task_id):
        yield update
```

**Alternatives considered**:
- *`sse-starlette`* — rejected: extra dep with no win on a fresh project.
- *Long-polling via repeated `tasks/get`* — rejected: spec explicitly defines streaming via SSE for `tasks/sendSubscribe`; long-polling would be a deviation requiring an ADR per Constitution Principle I.

---

## R3 — Headless invocation flags for the three CLIs

For each CLI we will spawn via `asyncio.create_subprocess_exec`, the v1 invocation contract is:

| CLI | Non-interactive | JSON output | Streaming JSON | Notes |
|---|---|---|---|---|
| **Claude Code** (`claude`) | `claude -p "<prompt>"` | `--output-format json` | `--output-format stream-json --verbose` | Use `--bare` in CI / adapter context to skip auto-discovery of hooks/MCP/CLAUDE.md. Docs: <https://code.claude.com/docs/en/headless> |
| **Gemini CLI** (`gemini`) | `gemini -p "<prompt>"` | `--output-format json` | `--output-format stream-json` | Auto-triggers headless when stdin is non-TTY. Docs: <https://geminicli.com/docs/cli/headless/> |
| **Codex CLI** (`codex`) | `codex exec "<prompt>"` (alias `codex e`) | `codex exec --json "<prompt>"` | NDJSON event stream on stdout in `--json` mode | Final agent message → stdout, progress → stderr in non-JSON mode. Docs: <https://developers.openai.com/codex/noninteractive> |

**Decision**: Each adapter will invoke its CLI in **streaming JSON mode** so we can translate per-event progress into A2A SSE task updates. For v1 we only ship the Claude adapter and we delegate to Gemini, so:
- `services/a2a-bridge/adapters/claude/runner.py` → invokes `claude -p "<prompt>" --bare --output-format stream-json --verbose`.
- `services/a2a-bridge/adapters/gemini/runner.py` → invokes `gemini -p "<prompt>" --output-format stream-json`. (Built but only exercised via the delegation client in v1; the inbound Gemini server side is v2.)

**Rationale**:
- Streaming JSON gives us granular events to forward as A2A `working` updates instead of a single terminal `completed`. This delivers SC-001 (in-stream progress) and matches the spec's task lifecycle.
- `--bare` on Claude prevents the adapter from inheriting the developer's hook/MCP/CLAUDE.md context, which would make adapter behavior depend on machine state — a violation of the in-memory, isolated-task model.

**Alternatives considered**:
- *Plain `-p` with one final stdout dump* — rejected: forces adapter to emit a single `completed` event with no progress, missing the streaming UX promised by the spec.
- *Pipe stdin instead of `-p`* — rejected: `-p` is the documented and supported entry point for all three CLIs; piping to stdin works for some but not all and complicates timeout handling.

---

## R4 — Official A2A test client / inspector and pytest integration

**Decision**: For automated contract testing, use the official **`a2a-sdk`** package (`pip install a2a-sdk`, latest 1.0.2 as of 2026-05; source at <https://github.com/a2aproject/a2a-python>) driven from `pytest`. NOTE: the package on PyPI named `a2a` is an unrelated Scrapy utility — do not install it. For manual end-to-end verification, use the **A2A Inspector** web tool (clone <https://github.com/a2aproject/a2a-inspector>, `uv sync` + `npm install`, runs at `http://127.0.0.1:5001`). No formal cross-implementation conformance suite exists as of 2026-05.

**Rationale**:
- The Inspector is a manual-only web tool — no Python API, no pytest plugin. It is the official interactive validator for Agent Cards and live message flows but cannot block CI.
- The `a2a-sdk` package ships canonical client classes (Agent Card fetcher, JSON-RPC request builder, SSE consumer) that we can drive from `pytest-asyncio` to assert request/response shapes match the spec's wire format. This satisfies Constitution Principle III (contract tests for the protocol surface).
- The lack of a formal cross-implementation conformance suite means SC-002 ("zero spec violations") is verified by: (a) automated `a2a-python`-based contract tests in CI, and (b) one manual Inspector pass per release tagged in `quickstart.md`.

**Alternatives considered**:
- *Build our own A2A test harness* — rejected for v1: high effort, the `a2a-python` SDK already covers wire-format validation, and any custom harness would need its own conformance review.
- *Skip programmatic conformance testing and rely solely on the Inspector* — rejected: violates Constitution Principle III (contract tests required before implementation for protocol surfaces).

---

## R5 — Concurrency model for the inbound adapter

**Decision**: One `asyncio` event loop per adapter process. Each inbound task spawns its own CLI subprocess via `asyncio.create_subprocess_exec`. Per-task streams are independent `asyncio.Queue`s; no shared state between tasks beyond the read-only Agent Card and the bearer token.

**Rationale**:
- Matches FR-011 (concurrent tasks each get isolated CLI process and stream).
- Avoids the pitfalls of subprocess pools — pool reuse would risk cross-task state leakage, which the underlying CLIs' interactive history could amplify.
- The 3-concurrent-tasks performance target (Technical Context) is trivially achievable: each task is one Python coroutine plus one OS subprocess; modern dev laptops handle dozens.

**Alternatives considered**:
- *Subprocess pool with task multiplexing* — rejected: cross-contamination risk, no measurable v1 win.
- *Multi-process worker model (gunicorn / uvicorn workers)* — deferred to v2: unnecessary for the localhost-only v1 footprint.

---

## R6 — Where the developer-facing trigger lives in Claude Code

**Decision**: For v1, ship the delegation trigger as a **CLI subcommand of the bridge itself** (e.g. `a2a-bridge delegate gemini "<prompt>"`), not as a Claude Code skill or slash command. Document the developer flow in `quickstart.md` as: "the developer (or a Claude Code agent that wants to delegate) shells out to the `a2a-bridge` CLI".

**Rationale**:
- Constitution Principle V (Minimal Skill & Agent Surface) — adding a new global skill or slash command for v1 is premature. Claude Code can already shell out to a local CLI via the existing `Bash` tool with no new skill needed.
- A skill or slash command can be added in v2 once the wire format is stable and we know how often it is used. Adding it now would lock in an UX before we have feedback.
- The CLI is also the natural entry point for non-Claude callers (curl tests, future scripts), which keeps the surface uniform.

**Alternatives considered**:
- *Add a `/delegate` slash command* — rejected for v1: another global skill to maintain, can be retrofitted later.
- *Add a new `@delegator` subagent* — rejected: violates Principle V; the `Bash` tool already covers shelling out.
- *Hook on PreToolUse to auto-delegate certain prompts* — rejected: hidden control flow, hard to debug, no clear trigger heuristic.
