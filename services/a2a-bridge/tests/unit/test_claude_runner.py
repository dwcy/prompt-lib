"""Claude stream-json adapter coverage for forwarded subagent output."""

from __future__ import annotations

from a2a_bridge.adapters.claude.runner import (
    claude_command_factory,
    parse_claude_event,
)


def _assistant_event(*blocks: dict, parent_tool_use_id: str | None = None) -> dict:
    event = {
        "type": "assistant",
        "message": {"role": "assistant", "content": list(blocks)},
    }
    if parent_tool_use_id is not None:
        event["parent_tool_use_id"] = parent_tool_use_id
    return event


def test_command_factory_enables_forwarded_subagent_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "a2a_bridge.adapters.claude.runner.shutil.which",
        lambda _name: "/tools/claude",
    )

    command = claude_command_factory("review this")

    assert command[0] == "/tools/claude"
    assert "--forward-subagent-text" in command
    assert command[command.index("--output-format") + 1] == "stream-json"


def test_parser_keeps_normal_assistant_text() -> None:
    artifact = parse_claude_event(
        _assistant_event(
            {"type": "text", "text": "all "},
            {"type": "text", "text": "done"},
        )
    )

    assert artifact is not None
    assert artifact.content == "all done"


def test_parser_includes_forwarded_subagent_text_and_thinking() -> None:
    event = _assistant_event(
        {"type": "thinking", "thinking": "Inspect the launcher."},
        {"type": "text", "text": "The launcher owns the flag."},
        parent_tool_use_id="toolu_parent",
    )

    artifact = parse_claude_event(event)

    assert artifact is not None
    assert artifact.content == (
        "[subagent thinking]\nInspect the launcher.\nThe launcher owns the flag."
    )


def test_parser_drops_parent_assistant_thinking() -> None:
    artifact = parse_claude_event(
        _assistant_event({"type": "thinking", "thinking": "private"})
    )

    assert artifact is None
