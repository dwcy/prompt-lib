"""Unit tests for the Codex adapter's NDJSON parser and command factory.

Pins the Codex-specific translation of ``codex exec --json`` events into A2A
artifacts and the argv shape the runner spawns. These are the only
Codex-specific pieces; the surrounding server + runner mechanics are covered by
the CLI-agnostic contract tests.
"""

from __future__ import annotations

from a2a_bridge.adapters.codex.runner import codex_command_factory, parse_codex_event


class TestParseCodexEvent:
    def test_agent_message_item_becomes_text_artifact(self):
        event = {
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": "pong ok"},
        }

        artifact = parse_codex_event(event)

        assert artifact is not None
        assert artifact.kind == "text"
        assert artifact.mime_type == "text/plain"
        assert artifact.content == "pong ok"

    def test_thread_started_event_is_skipped(self):
        assert parse_codex_event({"type": "thread.started", "thread_id": "x"}) is None

    def test_turn_started_event_is_skipped(self):
        assert parse_codex_event({"type": "turn.started"}) is None

    def test_turn_completed_event_is_skipped(self):
        assert parse_codex_event({"type": "turn.completed", "usage": {}}) is None

    def test_non_agent_message_item_is_skipped(self):
        event = {
            "type": "item.completed",
            "item": {"id": "item_1", "type": "reasoning", "text": "thinking"},
        }

        assert parse_codex_event(event) is None

    def test_completed_item_without_text_is_skipped(self):
        event = {"type": "item.completed", "item": {"type": "agent_message"}}

        assert parse_codex_event(event) is None

    def test_empty_text_is_skipped(self):
        event = {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": ""},
        }

        assert parse_codex_event(event) is None

    def test_item_not_a_dict_is_skipped(self):
        assert parse_codex_event({"type": "item.completed", "item": "nope"}) is None


class TestCodexCommandFactory:
    def test_argv_is_exec_json_read_only_ephemeral(self):
        argv = codex_command_factory("hello world")

        assert argv[1:] == [
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "hello world",
        ]

    def test_prompt_is_the_final_argument(self):
        argv = codex_command_factory("summarise this")

        assert argv[-1] == "summarise this"
