from __future__ import annotations

import pytest

from mcp_bus import storage


class TestMessages:
    def test_post_then_read_round_trips_all_fields(self, db):
        message_id = storage.post_message(
            "contract",
            "POST /api/orders",
            "python-architect",
            {"priority": "high"},
            path=db,
        )

        messages = storage.read_messages("contract", path=db)

        assert len(messages) == 1
        msg = messages[0]
        assert msg["message_id"] == message_id
        assert msg["content"] == "POST /api/orders"
        assert msg["from_agent"] == "python-architect"
        assert msg["channel"] == "contract"
        assert msg["metadata"] == {"priority": "high"}
        assert isinstance(msg["created_at"], str) and msg["created_at"]

    def test_metadata_defaults_to_empty_object(self, db):
        storage.post_message("c", "hi", "a", path=db)
        assert storage.read_messages("c", path=db)[0]["metadata"] == {}

    def test_read_since_id_returns_only_newer_messages(self, db):
        first = storage.post_message("c", "1", "a", path=db)
        second = storage.post_message("c", "2", "a", path=db)
        third = storage.post_message("c", "3", "a", path=db)

        newer = storage.read_messages("c", since_id=first, path=db)

        assert [m["message_id"] for m in newer] == [second, third]

    def test_read_since_latest_returns_empty(self, db):
        latest = storage.post_message("c", "1", "a", path=db)
        assert storage.read_messages("c", since_id=latest, path=db) == []

    def test_read_limit_capped_at_100(self, db):
        for i in range(150):
            storage.post_message("c", str(i), "a", path=db)

        messages = storage.read_messages("c", limit=999, path=db)

        assert len(messages) == 100

    def test_read_returns_ascending_order(self, db):
        ids = [storage.post_message("c", str(i), "a", path=db) for i in range(5)]
        returned = [m["message_id"] for m in storage.read_messages("c", path=db)]
        assert returned == sorted(ids)

    def test_read_scopes_to_channel(self, db):
        storage.post_message("alpha", "a", "x", path=db)
        storage.post_message("beta", "b", "x", path=db)

        assert len(storage.read_messages("alpha", path=db)) == 1
        assert storage.read_messages("alpha", path=db)[0]["content"] == "a"

    def test_rejects_oversized_content(self, db):
        content = "x" * (storage.CONTENT_MAX_BYTES + 1)
        with pytest.raises(ValueError, match="content"):
            storage.post_message("c", content, "a", path=db)

    def test_rejects_oversized_metadata(self, db):
        metadata = {"x": "y" * storage.METADATA_MAX_BYTES}
        with pytest.raises(ValueError, match="metadata"):
            storage.post_message("c", "hi", "a", metadata, path=db)

    def test_post_prunes_old_messages_per_channel(self, db, monkeypatch):
        monkeypatch.setattr(storage, "CHANNEL_RETENTION_MAX", 3)
        for i in range(5):
            storage.post_message("c", str(i), "a", path=db)

        messages = storage.read_messages("c", limit=10, path=db)

        assert [m["content"] for m in messages] == ["2", "3", "4"]

    def test_prune_messages_keeps_last_per_channel(self, db):
        for i in range(5):
            storage.post_message("c", str(i), "a", path=db)

        deleted = storage.prune_messages(keep_last_per_channel=2, path=db)

        assert deleted == 3
        assert [m["content"] for m in storage.read_messages("c", path=db)] == ["3", "4"]


class TestChannels:
    def test_list_channels_returns_distinct_with_messages(self, db):
        storage.post_message("alpha", "1", "x", path=db)
        storage.post_message("alpha", "2", "x", path=db)
        storage.post_message("beta", "1", "x", path=db)

        assert storage.list_channels(path=db) == ["alpha", "beta"]

    def test_list_channels_empty_when_no_messages(self, db):
        assert storage.list_channels(path=db) == []


class TestMemory:
    def test_set_then_get_round_trips(self, db):
        storage.mem_set("ns", "k", "v", path=db)
        assert storage.mem_get("ns", "k", path=db) == "v"

    def test_get_missing_key_returns_none(self, db):
        assert storage.mem_get("ns", "absent", path=db) is None

    def test_set_upserts_overwrites_existing(self, db):
        storage.mem_set("ns", "k", "old", path=db)
        storage.mem_set("ns", "k", "new", path=db)

        assert storage.mem_get("ns", "k", path=db) == "new"
        assert storage.mem_list("ns", path=db) == ["k"]

    def test_namespace_isolation_no_collision(self, db):
        storage.mem_set("ns1", "shared", "one", path=db)
        storage.mem_set("ns2", "shared", "two", path=db)

        assert storage.mem_get("ns1", "shared", path=db) == "one"
        assert storage.mem_get("ns2", "shared", path=db) == "two"

    def test_list_returns_keys_in_namespace_only(self, db):
        storage.mem_set("ns1", "a", "1", path=db)
        storage.mem_set("ns1", "b", "2", path=db)
        storage.mem_set("ns2", "c", "3", path=db)

        assert storage.mem_list("ns1", path=db) == ["a", "b"]

    def test_list_empty_namespace_returns_empty(self, db):
        assert storage.mem_list("empty", path=db) == []

    def test_delete_removes_key(self, db):
        storage.mem_set("ns", "k", "v", path=db)
        storage.mem_delete("ns", "k", path=db)

        assert storage.mem_get("ns", "k", path=db) is None
        assert storage.mem_list("ns", path=db) == []

    def test_delete_absent_key_is_noop(self, db):
        storage.mem_delete("ns", "absent", path=db)
        assert storage.mem_get("ns", "absent", path=db) is None

    def test_rejects_oversized_memory_value(self, db):
        with pytest.raises(ValueError, match="value"):
            storage.mem_set("ns", "k", "x" * (storage.MEMORY_VALUE_MAX_BYTES + 1), path=db)


class TestAgents:
    def test_register_sets_capabilities_and_heartbeat(self, db):
        storage.agent_register("python-architect", ["fastapi", "sqlalchemy"], path=db)

        agents = storage.agent_list(path=db)

        assert len(agents) == 1
        agent = agents[0]
        assert agent["name"] == "python-architect"
        assert agent["capabilities"] == ["fastapi", "sqlalchemy"]
        assert isinstance(agent["last_heartbeat"], str) and agent["last_heartbeat"]

    def test_register_upserts_capabilities(self, db):
        storage.agent_register("a", ["one"], path=db)
        storage.agent_register("a", ["two", "three"], path=db)

        agents = storage.agent_list(path=db)
        assert len(agents) == 1
        assert agents[0]["capabilities"] == ["two", "three"]

    def test_list_orders_by_name(self, db):
        storage.agent_register("zeta", [], path=db)
        storage.agent_register("alpha", [], path=db)

        assert [a["name"] for a in storage.agent_list(path=db)] == ["alpha", "zeta"]

    def test_list_empty_returns_empty(self, db):
        assert storage.agent_list(path=db) == []

    def test_heartbeat_refreshes_timestamp(self, db):
        storage.agent_register("a", [], path=db)
        before = storage.agent_list(path=db)[0]["last_heartbeat"]

        storage.mem_set("_", "_", "_", path=db)  # advance wall clock cheaply
        storage.agent_heartbeat("a", path=db)
        after = storage.agent_list(path=db)[0]["last_heartbeat"]

        assert after >= before

    def test_heartbeat_on_unregistered_agent_raises(self, db):
        with pytest.raises(ValueError, match="not registered"):
            storage.agent_heartbeat("ghost", path=db)
