from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_bus import storage

mcp = FastMCP("mcp-bus")


@mcp.tool()
def bus_post(
    channel: str,
    content: str,
    from_agent: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Post a message to a channel. The channel is created implicitly on first post."""
    message_id = storage.post_message(channel, content, from_agent, metadata)
    return {"message_id": message_id}


@mcp.tool()
def bus_read(
    channel: str,
    since_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read messages from a channel ordered by id ascending, optionally only those newer
    than since_id. limit defaults to 20, capped at 100."""
    return storage.read_messages(channel, since_id, limit)


@mcp.tool()
def bus_channels() -> list[str]:
    """List distinct channel names that have at least one message."""
    return storage.list_channels()


@mcp.tool()
def bus_prune(
    max_age_days: int | None = None,
    keep_last_per_channel: int | None = None,
) -> dict[str, int]:
    """Delete old bus messages by age and/or per-channel retention count."""
    deleted = storage.prune_messages(
        max_age_days=max_age_days,
        keep_last_per_channel=keep_last_per_channel,
    )
    return {"deleted": deleted}


@mcp.tool()
def mem_set(namespace: str, key: str, value: str) -> dict[str, bool]:
    """Set a key in a namespace, overwriting any existing value."""
    storage.mem_set(namespace, key, value)
    return {"ok": True}


@mcp.tool()
def mem_get(namespace: str, key: str) -> str | None:
    """Get a key from a namespace, or null if the key does not exist."""
    return storage.mem_get(namespace, key)


@mcp.tool()
def mem_list(namespace: str) -> list[str]:
    """List all keys in a namespace."""
    return storage.mem_list(namespace)


@mcp.tool()
def mem_delete(namespace: str, key: str) -> dict[str, bool]:
    """Delete a key from a namespace. No error if the key is absent."""
    storage.mem_delete(namespace, key)
    return {"ok": True}


@mcp.tool()
def agent_register(name: str, capabilities: list[str]) -> dict[str, bool]:
    """Register or update an agent's capabilities and set its heartbeat to now."""
    storage.agent_register(name, capabilities)
    return {"ok": True}


@mcp.tool()
def agent_list() -> list[dict[str, Any]]:
    """List all registered agents with their capabilities and last-heartbeat time."""
    return storage.agent_list()


@mcp.tool()
def agent_heartbeat(name: str) -> dict[str, bool]:
    """Refresh an agent's last-heartbeat timestamp. Errors if the agent is not registered."""
    storage.agent_heartbeat(name)
    return {"ok": True}
