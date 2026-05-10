# A2A Bridge v1 — Contracts

This directory enumerates the protocol surfaces the v1 bridge exposes. Each surface here MUST have a corresponding contract test in `services/a2a-bridge/tests/contract/` per Constitution Principle III, and every contract test task in `tasks.md` MUST be ordered before its implementation task.

## Files

- `agent-card.schema.json` — JSON Schema (draft 2020-12) for the Agent Card we publish at `/.well-known/agent-card.json`. Fragment of the A2A v1.0.0 Agent Card schema, restricted to the fields v1 actually uses.
- `jsonrpc-methods.md` — Per-method documentation for the JSON-RPC 2.0 methods v1 implements: request shape, response shape, error codes.
- `sse-events.md` — SSE event types the adapter emits on `tasks/sendSubscribe` streams: event names, `data:` payload shapes, ordering rules.
- `error-codes.md` — Mapping of A2A error conditions to JSON-RPC error codes used in error responses.

## What is NOT in scope for v1 contracts

The following A2A v1.0.0 surfaces are explicitly out of scope and have no contract tests in v1. Adding them in a future version requires extending this directory and `tasks.md` with the corresponding contract test tasks first.

- gRPC binding
- HTTP+JSON/REST binding
- Push notifications
- Task state history queries
- Multi-turn conversations within a single task
- Artifact kinds other than `text`
