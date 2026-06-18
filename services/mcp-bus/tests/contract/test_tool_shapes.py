from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="mcp SDK not installed; storage/unit tests still run")

from mcp_bus import server  # noqa: E402


def _callable(tool):
    """FastMCP's @mcp.tool() may return the original function or a wrapper.

    Resolve to the plain callable so the contract test exercises the same
    code path the MCP runtime invokes.
    """
    for attr in ("fn", "func", "__wrapped__"):
        target = getattr(tool, attr, None)
        if callable(target):
            return target
    return tool


bus_post = _callable(server.bus_post)
bus_read = _callable(server.bus_read)
bus_channels = _callable(server.bus_channels)
bus_prune = _callable(server.bus_prune)
mem_set = _callable(server.mem_set)
mem_get = _callable(server.mem_get)
mem_list = _callable(server.mem_list)
mem_delete = _callable(server.mem_delete)
agent_register = _callable(server.agent_register)
agent_list = _callable(server.agent_list)
agent_heartbeat = _callable(server.agent_heartbeat)


class TestBusShapes:
    def test_bus_post_returns_message_id_int(self, db):
        result = bus_post("c", "hi", "agent")
        assert set(result.keys()) == {"message_id"}
        assert isinstance(result["message_id"], int)

    def test_bus_read_item_keys(self, db):
        bus_post("c", "hi", "agent", {"k": "v"})
        messages = bus_read("c")

        assert isinstance(messages, list)
        item = messages[0]
        assert set(item.keys()) == {
            "message_id",
            "channel",
            "from_agent",
            "content",
            "metadata",
            "created_at",
        }
        assert isinstance(item["message_id"], int)
        assert isinstance(item["metadata"], dict)
        assert isinstance(item["created_at"], str)

    def test_bus_channels_returns_string_list(self, db):
        bus_post("alpha", "x", "agent")
        channels = bus_channels()
        assert channels == ["alpha"]
        assert all(isinstance(c, str) for c in channels)

    def test_bus_prune_returns_deleted_count(self, db):
        for i in range(3):
            bus_post("alpha", str(i), "agent")

        result = bus_prune(keep_last_per_channel=1)

        assert result == {"deleted": 2}


class TestMemoryShapes:
    def test_mem_set_returns_ok_true(self, db):
        assert mem_set("ns", "k", "v") == {"ok": True}

    def test_mem_get_returns_value_string(self, db):
        mem_set("ns", "k", "v")
        value = mem_get("ns", "k")
        assert value == "v"
        assert isinstance(value, str)

    def test_mem_get_missing_returns_none(self, db):
        assert mem_get("ns", "absent") is None

    def test_mem_list_returns_string_list(self, db):
        mem_set("ns", "k", "v")
        assert mem_list("ns") == ["k"]

    def test_mem_delete_returns_ok_true(self, db):
        assert mem_delete("ns", "absent") == {"ok": True}


class TestAgentShapes:
    def test_agent_register_returns_ok_true(self, db):
        assert agent_register("a", ["cap"]) == {"ok": True}

    def test_agent_list_item_keys(self, db):
        agent_register("a", ["fastapi"])
        agents = agent_list()

        assert isinstance(agents, list)
        item = agents[0]
        assert set(item.keys()) == {"name", "capabilities", "last_heartbeat"}
        assert isinstance(item["name"], str)
        assert isinstance(item["capabilities"], list)
        assert isinstance(item["last_heartbeat"], str)

    def test_agent_heartbeat_returns_ok_true(self, db):
        agent_register("a", [])
        assert agent_heartbeat("a") == {"ok": True}
