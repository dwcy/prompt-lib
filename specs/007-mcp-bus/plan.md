# Implementation Plan: MCP Message Bus (v1)

**Branch**: `feat/007-mcp-bus` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)

## Summary

Build `mcp-bus`, a local MCP server at `services/mcp-bus/`, exposing 10 tools across three groups (message bus, shared memory, agent registry). State is durable in SQLite (`~/.claude/mcp-bus/bus.db`, WAL mode, stdlib `sqlite3`, no ORM). Transport is stdio via the official `mcp` Python SDK (FastMCP). No HTTP, no auth in v1.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: `mcp` (official Model Context Protocol SDK, FastMCP server), stdlib `sqlite3`, `pydantic` v2 (tool param models, ships with mcp). No FastAPI, no httpx.
**Storage**: SQLite at `~/.claude/mcp-bus/bus.db`, WAL mode, three tables.
**Testing**: pytest + pytest-asyncio. Contract tests assert tool I/O shapes; unit tests cover storage CRUD; one concurrency test asserts zero message loss under simultaneous writes.
**Target Platform**: Operator workstation (Linux/macOS/Windows), localhost only.
**Project Type**: MCP server (stdio daemon launched by Claude Code).

## Constitution Check

- **Gate 1 — Spec-First**: PASS. Tool surface is fully specified in [`contracts/mcp-tools.contract.md`](./contracts/mcp-tools.contract.md) before implementation.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table below.
- **Gate 3 — Contract Tests Before Implementation**: PASS. `tests/contract/` is authored before tool implementation in the task order.
- **Gate 4 — Reversible Config**: PASS. Registering the server adds one `mcpServers` entry; removing it is a one-line revert. DB lives outside the repo under `~/.claude/`.
- **Gate 5 — Minimal Skill & Agent Surface**: PASS. No new global skill or agent. The bus is a tool surface consumed by existing agents.

## Subagent Delegation

| Phase / concern | Owner |
|---|---|
| Project scaffold (`pyproject.toml`, package layout, entry point) | `@python-architect` |
| Storage layer (`storage.py` — SQLite schema, CRUD, WAL, transactions) | `@python-architect` |
| MCP tool wiring (`server.py` — FastMCP tool defs → storage) | `@python-architect` |
| Contract tests (`tests/contract/`) | `@python-tester` |
| Unit + concurrency tests (`tests/unit/`) | `@python-tester` |
| Settings registration + MCP.md update | main session |
| Quickstart + docs | main session |
| End-to-end validation | main session |
| Plan-conformance audit before commit | `@code-plan-verifier` |

## Project Structure

```
services/mcp-bus/
├── pyproject.toml
├── README.md
├── src/mcp_bus/
│   ├── __init__.py
│   ├── __main__.py          ← entry point: python -m mcp_bus
│   ├── server.py            ← FastMCP app + 10 tool definitions
│   ├── storage.py           ← SQLite layer (no ORM)
│   └── paths.py             ← resolves ~/.claude/mcp-bus/bus.db cross-platform
└── tests/
    ├── conftest.py          ← temp-db fixture
    ├── contract/
    │   └── test_tool_shapes.py
    └── unit/
        ├── test_storage.py
        └── test_concurrency.py
```

## SQLite Schema

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  channel     TEXT NOT NULL,
  from_agent  TEXT NOT NULL,
  content     TEXT NOT NULL,
  metadata    TEXT NOT NULL DEFAULT '{}',   -- JSON string
  created_at  TEXT NOT NULL                 -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel, id);

CREATE TABLE IF NOT EXISTS memory (
  namespace   TEXT NOT NULL,
  key         TEXT NOT NULL,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (namespace, key)
);

CREATE TABLE IF NOT EXISTS agents (
  name           TEXT PRIMARY KEY,
  capabilities   TEXT NOT NULL DEFAULT '[]',  -- JSON string array
  last_heartbeat TEXT NOT NULL
);
```

## Implementation Notes

- **Monotonic ids**: `AUTOINCREMENT` on `messages.id` guarantees unique increasing ids even under concurrent writes; SQLite serialises writes so no message is lost (WAL allows concurrent readers).
- **Timestamps**: generated in the storage layer at write time. The Python sandbox forbids `Date.now()` in workflow scripts, but this is a normal Python service — `datetime.now(timezone.utc).isoformat()` is fine here.
- **Metadata + capabilities**: stored as JSON strings, parsed on read. Tools accept/return real objects/arrays.
- **Connection per call**: open a short-lived connection per tool invocation (stdio server is low-frequency); enable WAL once at startup via `paths.ensure_db()`.
- **No ORM**: parameterised stdlib `sqlite3` only.

## Validation

| Check | Expected |
|---|---|
| `python -m mcp_bus` starts without error | server boots, registers 10 tools |
| `bus_post` then `bus_read` | message round-trips with id + timestamp |
| `bus_read(since_id=latest)` | empty list |
| `mem_set` / `mem_get` across namespaces | no collision |
| `mem_get` missing key | returns null |
| concurrent `bus_post` ×100 | 100 distinct ids, zero loss |
| restart server, re-read | all state persists |
| `claude mcp list` after registration | `mcp-bus` listed |
