# Feature Specification: MCP Message Bus — Inter-Agent Comms + Shared Memory (v1)

**Feature Branch**: `feat/007-mcp-bus`
**Created**: 2026-06-01
**Status**: Implemented — service lives at `services/mcp-bus/` with storage, tool-shape, and concurrency tests. Manual MCP registration validation depends on local Claude Code tooling.
**Input**: Agents dispatched by `/orchestrate` sometimes need to talk to each other and share state. Build an MCP server exposing a message bus, a shared key-value memory, and an agent registry — all natively callable as MCP tools by any Claude Code session or subagent.

---

## Problem

The `/orchestrate` skill (spec 006) dispatches subagents, but each runs in isolation:

- A backend agent cannot tell a frontend agent "the API contract changed"
- Two agents working on related slices cannot share intermediate decisions
- There is no durable place for agents to record state that outlives a single dispatch
- The main session cannot see which agents are active across sessions

Spec 001 (A2A bridge) proposed solving cross-agent comms with a custom JSON-RPC/SSE HTTP server. That is heavyweight and non-native. MCP is already the way Claude Code extends its tool surface — a single MCP server solves comms AND shared memory natively, with no HTTP layer.

## Goal

A local MCP server, `mcp-bus`, exposing three tool groups:

1. **Message bus** — agents post to and read from named channels
2. **Shared memory** — namespaced key-value store agents read/write
3. **Agent registry** — agents register capabilities + heartbeat so others can discover them

All durable in SQLite, all available via stdio MCP transport. No HTTP server, no auth in v1 (localhost only).

---

## User Scenarios

### Scenario 1 — Agent posts to a channel (P1) 🎯 MVP

A backend agent finishes designing an API contract and posts it to the `contract` channel via `bus_post`. A frontend agent reads the `contract` channel via `bus_read` and consumes the contract.

**Acceptance**: message posted with an id; reader retrieves it with full content + from_agent + timestamp; messages survive server restart.

### Scenario 2 — Incremental reads with a cursor (P1) 🎯 MVP

An agent polls a channel for new messages, passing the last message id it saw as `since_id`. Only messages newer than that id are returned.

**Acceptance**: `bus_read(channel, since_id=N)` returns only messages with id > N, in order; passing the latest id returns an empty list.

### Scenario 3 — Shared memory read/write (P1) 🎯 MVP

An agent writes a decision to shared memory (`mem_set("checkout-feature", "payment_provider", "stripe")`). Another agent reads it back (`mem_get("checkout-feature", "payment_provider")` → `"stripe"`).

**Acceptance**: value persists across agents and across server restarts; reading a missing key returns null; namespaces are isolated (same key in different namespaces does not collide).

### Scenario 4 — Agent registry + discovery (P2)

An agent registers itself (`agent_register("python-architect", ["fastapi", "sqlalchemy"])`). Another agent lists the registry (`agent_list`) to discover who is available and what they can do.

**Acceptance**: registered agent appears in `agent_list` with capabilities and last-heartbeat time; re-registering updates capabilities; `agent_heartbeat` refreshes the timestamp.

### Scenario 5 — Concurrent writers do not lose messages (P2)

Two agents post to the same channel at the same time. Both messages are stored; neither overwrites the other; ids are monotonic.

**Acceptance**: under concurrent `bus_post` calls, all messages are persisted with unique monotonic ids; `bus_read` returns all of them.

---

## Surfaces (tool groups)

### Message bus
- `bus_post(channel, content, from_agent, metadata={})` → `message_id`
- `bus_read(channel, since_id=None, limit=20)` → `Message[]`
- `bus_channels()` → `string[]` (distinct channel names that have messages)

### Shared memory
- `mem_set(namespace, key, value)` → `{ ok: true }`
- `mem_get(namespace, key)` → `value | null`
- `mem_list(namespace)` → `string[]` (keys in namespace)
- `mem_delete(namespace, key)` → `{ ok: true }`

### Agent registry
- `agent_register(name, capabilities[])` → `{ ok: true }`
- `agent_list()` → `Agent[]`
- `agent_heartbeat(name)` → `{ ok: true }`

(Full request/response shapes in [`contracts/mcp-tools.contract.md`](./contracts/mcp-tools.contract.md).)

---

## Out of scope (v1)

- **Auth / multi-user** — localhost stdio only; any process on the machine can use the bus
- **Cross-machine** — no network transport; single workstation
- **Pub/sub push** — readers poll with `since_id`; no server-initiated push (MCP stdio is request/response)
- **Message TTL / retention policy** — messages persist indefinitely in v1; pruning is v2
- **Value typing in memory** — values are stored/returned as strings (agents serialise JSON themselves if needed)
- **A2A to non-Claude agents** (Gemini, Codex) — that remains spec 001's redesign scope; this server is Claude-native MCP only

---

## Success criteria

- SC-001: a message posted by one agent is readable by another within the same session round-trip
- SC-002: all state survives a server restart (durable SQLite)
- SC-003: concurrent posts to one channel lose zero messages
- SC-004: namespace isolation holds — no key collision across namespaces
- SC-005: the server registers as an MCP server and its tools appear in a Claude Code session
