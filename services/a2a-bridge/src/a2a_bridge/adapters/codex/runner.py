"""Codex-specific bindings for the generic CLI runner.

The OpenAI Codex CLI emits NDJSON events on stdout when invoked with
``codex exec --json``; only the agent's final message items become A2A
artifacts. ``--sandbox read-only`` keeps the delegated task from touching the
filesystem (the bridge is the orchestrator, not the model) and
``--skip-git-repo-check`` / ``--ephemeral`` make the invocation deterministic
regardless of where it runs (mirrors the Claude adapter's ``--bare`` intent,
research.md R3).
"""

from __future__ import annotations

import shutil

from a2a_bridge.protocol.tasks import Artifact


def parse_codex_event(event: dict) -> Artifact | None:
    """Translate a Codex ``exec --json`` NDJSON event into an Artifact, or skip.

    Observed event shape (Codex CLI 0.130.x, probed 2026-07-02 against
    ``codex exec --json --skip-git-repo-check --sandbox read-only --ephemeral``)::

        {"type":"thread.started","thread_id":"..."}              # skip
        {"type":"turn.started"}                                  # skip
        {"type":"item.completed","item":{
            "id":"item_0","type":"agent_message","text":"<reply>"
         }}                                                       # extract text
        {"type":"turn.completed","usage":{...}}                  # skip

    Only ``item.completed`` events whose ``item.type == "agent_message"`` carry
    user-facing text. Reasoning, command-execution, file-change, and todo-list
    items are intentionally dropped — they are CLI-internal scaffolding, not
    part of the A2A artifact stream.
    """
    if event.get("type") != "item.completed":
        return None

    item = event.get("item")
    if not isinstance(item, dict):
        return None

    if item.get("type") != "agent_message":
        return None

    text = item.get("text")
    if not isinstance(text, str) or not text:
        return None

    return Artifact(kind="text", mime_type="text/plain", content=text)


def codex_command_factory(prompt: str) -> list[str]:
    """Build argv for the real Codex CLI invocation.

    ``--sandbox read-only`` is mandatory: it prevents the delegated task from
    writing to the filesystem or running unsandboxed shell commands.
    ``--skip-git-repo-check`` lets the adapter run outside a git repo and
    ``--ephemeral`` keeps Codex from persisting session files.

    Resolves ``codex`` via ``shutil.which`` so Windows finds ``codex.cmd``
    (``asyncio.create_subprocess_exec`` does not honour ``PATHEXT``).
    """
    resolved = shutil.which("codex") or "codex"
    return [
        resolved,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        prompt,
    ]
