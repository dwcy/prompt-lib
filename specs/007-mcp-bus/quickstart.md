# Quickstart: mcp-bus

A local MCP server giving every Claude Code session and subagent a shared message bus, a key-value memory, and an agent registry.

Status: implemented in `services/mcp-bus/`. Manual registration validation requires local Claude Code tooling.

## Install

From the prompt-lib repo root:

```bash
uv tool install --from services/mcp-bus mcp-bus
```

Or run it without installing, from the service directory:

```bash
cd services/mcp-bus
uv sync
uv run mcp-bus      # starts the stdio server
```

## Register with Claude Code

```bash
claude mcp add mcp-bus -- mcp-bus
```

Restart Claude Code. Confirm it's connected:

```bash
claude mcp list      # mcp-bus should be listed
```

Inside a session, `/mcp` shows live status and the 10 available tools.

## The tools

### Message bus — agents talk to each other

```
bus_post(channel="contract", content="POST /api/orders {...}", from_agent="python-architect")
  → { "message_id": 1 }

bus_read(channel="contract")
  → [ { message_id, channel, from_agent, content, metadata, created_at } ]

bus_read(channel="contract", since_id=1)    # only newer than id 1
bus_channels()                               → ["contract", "decisions"]
```

Typical use: a backend agent posts the API contract to a channel; a frontend agent reads it before building the client.

### Shared memory — agents share decisions

```
mem_set(namespace="checkout-feature", key="payment_provider", value="stripe")
  → { "ok": true }

mem_get(namespace="checkout-feature", key="payment_provider")
  → "stripe"

mem_list(namespace="checkout-feature")       → ["payment_provider"]
mem_delete(namespace="checkout-feature", key="payment_provider")
```

Namespaces are isolated — the same key in two namespaces does not collide. Values are strings; serialise JSON yourself for structured data.

### Agent registry — agents discover each other

```
agent_register(name="python-architect", capabilities=["fastapi", "sqlalchemy"])
agent_list()
  → [ { name, capabilities, last_heartbeat } ]
agent_heartbeat(name="python-architect")     # refresh liveness
```

## How /orchestrate uses it

When `/orchestrate` dispatches parallel agents, they can coordinate through the bus instead of staying blind to each other:

1. Lead agent posts the shared contract to a channel
2. Each worker reads the channel before starting
3. Workers record decisions to shared memory under a feature namespace
4. The verifier reads both channel + memory to check consistency

## Durability

All state lives in `~/.claude/mcp-bus/bus.db` (SQLite, WAL mode). It survives server restarts and is shared across every Claude Code session on the machine. Concurrent writes do not lose messages.

## Limits (v1)

- Localhost only, no auth — any local process can use the bus
- No push; readers poll with `since_id`
- Messages persist indefinitely (no TTL yet)
- Not for non-Claude agents (Gemini/Codex) — that's spec 001's redesign
