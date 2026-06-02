# mcp-bus

Local MCP server exposing three tool groups for inter-agent coordination:

- **Message bus** — agents post to and read from named channels (`bus_post`, `bus_read`, `bus_channels`).
- **Shared memory** — namespaced key-value store (`mem_set`, `mem_get`, `mem_list`, `mem_delete`).
- **Agent registry** — agents register capabilities and heartbeat for discovery (`agent_register`, `agent_list`, `agent_heartbeat`).

All state is durable in SQLite at `~/.claude/mcp-bus/bus.db` (WAL mode, stdlib `sqlite3`, no ORM). Transport is stdio via the official `mcp` Python SDK (FastMCP). No HTTP, no auth — localhost only.

## Run

```bash
cd services/mcp-bus
uv sync
uv run python -m mcp_bus
```

The server creates `~/.claude/mcp-bus/bus.db` and its schema on first run, then serves over stdio.

## Register with Claude Code

```bash
claude mcp add mcp-bus -- uv --directory /home/dawid/projects/prompt-lib/services/mcp-bus run python -m mcp_bus
```

Confirm it is registered and its tools are available:

```bash
claude mcp list
```

To remove it:

```bash
claude mcp remove mcp-bus
```
