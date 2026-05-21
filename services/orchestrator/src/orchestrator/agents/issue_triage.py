"""Issue-triage agent (T010).

Wraps the consumer-side flow for the ``issue.triage`` run kind:

1. Extract issue fields from the trigger event payload.
2. Build the triage prompt and stream via DelegationClient.
3. Parse the first ```json block in the output into a TriageDecision.
4. Post a ``gh issue comment`` (non-fatal: failure logs ``gh.comment.failed``
   and the run still reaches ``run.completed``).
5. Mark the issue in ``issue_cursor`` on success (duplicate suppression).
6. Log ``triage.decision`` and ``run.completed`` on success; ``run.failed`` on
   any unrecoverable error.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sqlite3
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack
from typing import Any, Protocol

from orchestrator import eventlog
from orchestrator.notifier import Notifier
from orchestrator.triggers.base import TriggerEvent

_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
_ERROR_TRUNCATE = 200
_NOTIF_TRUNCATE = 120
_REQUIRED_KEYS = frozenset({"category", "severity", "assessment", "routing"})


class _DelegationClient(Protocol):
    async def __aenter__(self) -> _DelegationClient: ...

    async def __aexit__(
        self, exc_type: object, exc: object, tb: object
    ) -> object: ...

    def delegate(
        self,
        prompt: str,
        *,
        cwd: str | None = ...,
    ) -> AsyncIterator[Mapping[str, Any]]: ...


def _build_triage_prompt(trigger_event: TriggerEvent) -> str:
    payload = trigger_event.payload
    issue_number = payload.get("issue_number", trigger_event.pr_number)
    title = payload.get("title", "")
    body = payload.get("body", "")
    labels = payload.get("labels", [])
    author = payload.get("author", "")
    labels_str = ", ".join(labels) if labels else "none"

    return (
        f"You are a lead developer triaging a GitHub issue on `{trigger_event.repo}`.\n"
        "\n"
        f"Issue #{issue_number}: {title}\n"
        f"Author: @{author}\n"
        f"Labels: {labels_str}\n"
        "\n"
        "Issue body:\n"
        f"{body[:4000]}\n"
        "\n"
        "Analyse the issue and produce a triage decision. Respond with ONLY a "
        "fenced JSON block:\n"
        "\n"
        "```json\n"
        "{\n"
        '  "category": "<bug|feature|question|infra|other>",\n'
        '  "severity": "<P1|P2|P3|P4>",\n'
        '  "assessment": "<one paragraph summary>",\n'
        '  "routing": "<self|@agent-name>"\n'
        "}\n"
        "```\n"
        "\n"
        "Routing: use `self` if triage is complete and no further action is "
        "needed. Use `@agent-name` (e.g. `@python-architect`) to indicate which "
        "specialist should own this issue.\n"
    )


def _parse_triage_decision(text: str) -> dict[str, Any] | None:
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not _REQUIRED_KEYS.issubset(data.keys()):
        return None
    return data


class IssueTiageAgent:
    """Run a single issue-triage delegation end-to-end."""

    def __init__(
        self,
        *,
        delegation_client: _DelegationClient,
        eventlog_conn: sqlite3.Connection,
        notifier: Notifier | None = None,
    ) -> None:
        self._client = delegation_client
        self._conn = eventlog_conn
        self._notifier = notifier

    async def _notify(
        self,
        level: str,
        title: str,
        body: str,
        *,
        click_url: str | None = None,
    ) -> None:
        if self._notifier is None:
            return
        try:
            await self._notifier.send(
                level=level,  # type: ignore[arg-type]
                title=title,
                body=body,
                click_url=click_url,
            )
        except Exception:
            return

    async def run(self, trigger_event: TriggerEvent) -> None:
        run_id = str(uuid.uuid4())
        repo = trigger_event.repo
        issue_number = trigger_event.pr_number

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.queued",
            payload={"repo": repo, "issue_number": issue_number, "kind": "issue.triage"},
        )
        self._conn.commit()

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.started",
            payload={"repo": repo, "issue_number": issue_number},
        )
        self._conn.commit()

        await self._notify("info", f"Triaging issue #{issue_number}", repo)

        prompt = _build_triage_prompt(trigger_event)
        buffer: list[str] = []
        terminal_state: str | None = None
        terminal_reason: str | None = None

        try:
            async with AsyncExitStack() as stack:
                client = await stack.enter_async_context(self._client)
                async for event in client.delegate(prompt):
                    kind, data = _normalize_event(event)
                    if kind == "message":
                        buffer.append(str(data.get("text", "")))
                    elif kind == "state":
                        state = str(data.get("state", ""))
                        if state == "completed":
                            terminal_state = "completed"
                            break
                        elif state in {"failed", "cancelled"}:
                            terminal_state = state
                            terminal_reason = data.get("reason")
                            break
        except Exception as exc:
            error_text = str(exc)[:_ERROR_TRUNCATE]
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={"error": error_text, "stage": "delegate"},
            )
            self._conn.commit()
            await self._notify(
                "error", f"Triage FAILED for issue #{issue_number}", error_text[:_NOTIF_TRUNCATE]
            )
            return

        if terminal_state in {"failed", "cancelled"}:
            error_text = (
                str(terminal_reason)[:_ERROR_TRUNCATE] if terminal_reason else terminal_state or "failed"
            )
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={"error": error_text, "stage": "delegate"},
            )
            self._conn.commit()
            await self._notify(
                "error", f"Triage FAILED for issue #{issue_number}", error_text[:_NOTIF_TRUNCATE]
            )
            return

        if terminal_state != "completed":
            error_text = "delegate stream ended without terminal state"
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={"error": error_text, "stage": "delegate"},
            )
            self._conn.commit()
            await self._notify(
                "error", f"Triage FAILED for issue #{issue_number}", error_text[:_NOTIF_TRUNCATE]
            )
            return

        output = "".join(buffer)
        decision = _parse_triage_decision(output)
        if decision is None:
            error_text = "failed to parse triage decision from agent output"
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={"error": error_text, "stage": "parse", "output": output[:_ERROR_TRUNCATE]},
            )
            self._conn.commit()
            await self._notify(
                "error", f"Triage FAILED for issue #{issue_number}", error_text[:_NOTIF_TRUNCATE]
            )
            return

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="triage.decision",
            payload={
                "issue_number": issue_number,
                "category": decision["category"],
                "severity": decision["severity"],
                "assessment": decision["assessment"],
                "routing": decision["routing"],
            },
        )
        self._conn.commit()

        if decision["routing"] != "self":
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="triage.routed",
                payload={"issue_number": issue_number, "routing": decision["routing"]},
            )
            self._conn.commit()

        await self._post_comment(run_id, repo, issue_number, decision)

        eventlog.issue_cursor_mark_triaged(self._conn, issue_number, repo)
        self._conn.commit()

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.completed",
            payload={"issue_number": issue_number},
        )
        self._conn.commit()

        await self._notify(
            "info",
            f"Triage complete for issue #{issue_number}",
            f"{decision['category']} · {decision['severity']} · {decision['routing']}",
        )

    async def _post_comment(
        self,
        run_id: str,
        repo: str,
        issue_number: int,
        decision: dict[str, Any],
    ) -> None:
        comment_body = (
            f"**Triage Decision**\n\n"
            f"- Category: `{decision['category']}`\n"
            f"- Severity: `{decision['severity']}`\n"
            f"- Routing: `{decision['routing']}`\n\n"
            f"{decision['assessment']}\n"
        )
        gh = shutil.which("gh") or "gh"
        try:
            proc = await asyncio.create_subprocess_exec(
                gh,
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                repo,
                "--body",
                comment_body,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout_b, stderr_b = await proc.communicate()
            rc = proc.returncode if proc.returncode is not None else -1
        except Exception as exc:
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="gh.comment.failed",
                level="warn",
                payload={"issue_number": issue_number, "error": str(exc)[:_ERROR_TRUNCATE]},
            )
            self._conn.commit()
            return

        if rc != 0:
            stderr_str = stderr_b.decode("utf-8", errors="replace")[:_ERROR_TRUNCATE]
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="gh.comment.failed",
                level="warn",
                payload={"issue_number": issue_number, "returncode": rc, "stderr": stderr_str},
            )
            self._conn.commit()
            return

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="gh.comment.posted",
            payload={"issue_number": issue_number},
        )
        self._conn.commit()


def _normalize_event(event: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    """Pull ``(kind, data)`` out of bridge SSE events or legacy fake shapes."""
    if "event" in event:
        kind = str(event["event"])
        data = event.get("data") or {}
        if not isinstance(data, Mapping):
            data = {}
        if kind == "task.state":
            return "state", data
        if kind == "task.artifact":
            return _artifact_event_to_message(data)
        if kind == "task.progress":
            return "progress", data
        return kind, data
    if "kind" in event:
        kind = str(event["kind"])
        data = {k: v for k, v in event.items() if k != "kind"}
        return kind, data
    return "", {}


def _artifact_event_to_message(data: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    artifact = data.get("artifact")
    if not isinstance(artifact, Mapping):
        return "artifact", data

    content = artifact.get("content")
    if isinstance(content, str):
        text = content
    elif content is None:
        text = ""
    else:
        text = json.dumps(content, ensure_ascii=False)

    return (
        "message",
        {
            "text": text,
            "partial": False,
            "artifact_id": artifact.get("id"),
            "mime_type": artifact.get("mime_type"),
        },
    )
