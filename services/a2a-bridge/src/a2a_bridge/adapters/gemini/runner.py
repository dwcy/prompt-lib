"""Gemini-specific bindings for the generic CLI runner (T025).

The Gemini CLI emits NDJSON events of the shape ``{"type": "<kind>", ...}``; we
only translate ``output`` events into A2A artifacts. ``start`` and ``end``
events delimit the stream and carry no payload of interest. The argv shape is
the documented ``gemini -p <prompt> --output-format stream-json``.
"""

from __future__ import annotations

from a2a_bridge.protocol.tasks import Artifact


def parse_gemini_event(event: dict) -> Artifact | None:
    if event.get("type") == "output":
        content = event.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return Artifact(kind="text", mime_type="text/plain", content=content)
    return None


def gemini_command_factory(prompt: str) -> list[str]:
    return ["gemini", "-p", prompt, "--output-format", "stream-json"]
