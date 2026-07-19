"""Claude-specific bindings for the generic CLI runner (T031).

The Claude Code CLI emits NDJSON envelopes on stdout when invoked with
``--output-format stream-json --verbose``. The adapter also opts into
``--forward-subagent-text`` so nested-agent text and thinking remain visible
to A2A clients. ``--bare`` strips the developer's ambient context (MCP
servers, hooks, project ``CLAUDE.md``) so the adapter is deterministic
regardless of where it runs (research.md R3).
"""

from __future__ import annotations

import shutil

from a2a_bridge.protocol.tasks import Artifact


def parse_claude_event(event: dict) -> Artifact | None:
    """Translate a Claude Code stream-json NDJSON event into an Artifact, or skip.

    Observed event shape (Claude Code CLI 2.1.x, probed 2026-05-09 against
    ``claude -p "..." --bare --output-format stream-json --verbose``)::

        {"type":"system","subtype":"init", ...}                  # skip
        {"type":"assistant","message":{
            "role":"assistant",
            "content":[{"type":"text","text":"<reply>"}, ...],
            ...
         }, ...}                                                  # extract text blocks
        {"type":"user","message":{...}, ...}                      # tool_result, skip
        {"type":"result","subtype":"success", ...}                # final summary, skip

    Normal assistant events contribute their non-empty ``text`` blocks. Events
    forwarded from a subagent are identified by ``parent_tool_use_id``; their
    ``text`` and ``thinking`` blocks both become artifacts. Other thinking,
    tool-use, and tool-result blocks remain internal and are dropped.
    """
    if event.get("type") != "assistant":
        return None

    message = event.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if not isinstance(content, list):
        return None

    text_parts: list[str] = []
    is_forwarded_subagent = bool(event.get("parent_tool_use_id"))
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)
        elif block_type == "thinking" and is_forwarded_subagent:
            thinking = block.get("thinking")
            if isinstance(thinking, str) and thinking:
                text_parts.append(f"[subagent thinking]\n{thinking}")

    if not text_parts:
        return None

    separator = "\n" if is_forwarded_subagent else ""
    return Artifact(
        kind="text",
        mime_type="text/plain",
        content=separator.join(text_parts),
    )


def claude_command_factory(prompt: str) -> list[str]:
    """Build argv for the real Claude Code CLI invocation.

    ``--bare`` is mandatory: it prevents the adapter from inheriting the
    developer's MCP servers, hooks, and project ``CLAUDE.md`` (research.md R3).

    Resolves ``claude`` via ``shutil.which`` so Windows finds ``claude.cmd``
    (``asyncio.create_subprocess_exec`` does not honour ``PATHEXT``).
    """
    resolved = shutil.which("claude") or "claude"
    return [
        resolved,
        "-p",
        prompt,
        "--bare",
        "--output-format",
        "stream-json",
        "--verbose",
        "--forward-subagent-text",
    ]
