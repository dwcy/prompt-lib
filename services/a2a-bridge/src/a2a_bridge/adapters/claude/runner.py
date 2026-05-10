"""Claude-specific bindings for the generic CLI runner (T031).

The Claude Code CLI emits NDJSON envelopes on stdout when invoked with
``--output-format stream-json --verbose``; only the assistant's text content
blocks become A2A artifacts. ``--bare`` strips the developer's ambient
context (MCP servers, hooks, project ``CLAUDE.md``) so the adapter is
deterministic regardless of where it runs (research.md R3).
"""

from __future__ import annotations

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

    Assistant ``content`` is always an array of typed blocks; only blocks with
    ``type == "text"`` carry a non-empty ``text`` field intended for the user.
    Tool-use / tool-result / thinking blocks are intentionally dropped — they
    are CLI-internal scaffolding, not part of the A2A artifact stream.
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
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)

    if not text_parts:
        return None

    return Artifact(kind="text", mime_type="text/plain", content="".join(text_parts))


def claude_command_factory(prompt: str) -> list[str]:
    """Build argv for the real Claude Code CLI invocation.

    ``--bare`` is mandatory: it prevents the adapter from inheriting the
    developer's MCP servers, hooks, and project ``CLAUDE.md`` (research.md R3).
    """
    return ["claude", "-p", prompt, "--bare", "--output-format", "stream-json", "--verbose"]
