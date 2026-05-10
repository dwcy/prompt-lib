"""PR-review agent (T019).

Wraps the consumer-side flow for the ``pr.review`` run kind:

1. Capture the diff via ``gh pr diff <n> --repo <repo>``.
2. Build the prompt from the trigger event + diff.
3. Stream the delegation client's events; map them to eventlog entries.
4. On terminal ``completed``, post the buffered review via
   ``gh pr review <n> --repo <repo> --comment -F -`` (stdin).
5. On terminal ``failed`` / ``cancelled`` or any raised exception, write a
   ``run.failed`` event and skip posting.

``run_id`` uses ``uuid4`` because Python's stdlib does not ship a built-in
UUIDv7 helper; the data-model marks v7 as the preferred shape but the schema
only requires the value to be a UUID string. v7 is a v2 follow-up.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack
from typing import Any, Protocol

from orchestrator import eventlog
from orchestrator.notifier import Notifier
from orchestrator.triggers.base import TriggerEvent
from orchestrator.worktree import WorktreeManager

_NO_REVIEW_RE = re.compile(r"^NO_REVIEW:\s*(.*)$")
_ERROR_TRUNCATE = 200
_NOTIF_ERROR_TRUNCATE = 120


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


def build_prompt(trigger_event: TriggerEvent, diff_text: str) -> str:
    """Render the PR-review prompt with the diff embedded in a fenced block."""
    payload = trigger_event.payload
    title = payload.get("title", "")
    url = payload.get("url", "")
    head_ref_name = payload.get("headRefName", "")
    base_ref_name = payload.get("baseRefName", "")
    author_login = payload.get("author_login", "")

    return (
        f"You are reviewing a pull request on `{trigger_event.repo}`.\n"
        "\n"
        f"PR number: #{trigger_event.pr_number}\n"
        f"PR title: {title}\n"
        f"Branch: {head_ref_name} -> {base_ref_name}\n"
        f"Author: @{author_login}\n"
        f"URL: {url}\n"
        "\n"
        "Diff:\n"
        f"```diff\n{diff_text}```\n"
        "\n"
        "Use the existing /review skill to produce a review comment. Output ONLY "
        "the review comment text - no preamble, no metadata, no markdown "
        "code-fences around the entire response. The orchestrator will pass your "
        "output verbatim to `gh pr review --comment -F -`.\n"
        "\n"
        "If the diff is empty or unreviewable (binary-only, etc.), output a "
        "single line:\n"
        '"NO_REVIEW: <one-line reason>"\n'
    )


def detect_no_review(text: str) -> tuple[bool, str | None]:
    """Return ``(True, reason)`` only when ``text`` is a single line starting with
    ``NO_REVIEW:``. Mid-paragraph occurrences are ignored."""
    stripped = text.strip()
    if not stripped:
        return False, None
    if "\n" in stripped:
        return False, None
    match = _NO_REVIEW_RE.match(stripped)
    if match is None:
        return False, None
    return True, match.group(1).strip()


class PrReviewAgent:
    """Run a single PR-review delegation end-to-end."""

    def __init__(
        self,
        *,
        delegation_client: _DelegationClient,
        eventlog_conn: sqlite3.Connection,
        notifier: Notifier | None = None,
        worktree_manager: WorktreeManager | None = None,
    ) -> None:
        self._client = delegation_client
        self._conn = eventlog_conn
        self._notifier = notifier
        self._worktree_manager = worktree_manager

    async def _notify(
        self,
        level: str,
        title: str,
        body: str,
        *,
        click_url: str | None = None,
    ) -> None:
        """Push one notification; swallow any exception so a notifier bug
        cannot abort the in-flight run (FR-009)."""
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
        pr_number = trigger_event.pr_number
        head_sha = trigger_event.head_sha
        peer_url = self._peer_url()
        pr_url = trigger_event.payload.get("url")
        pr_click_url = pr_url if isinstance(pr_url, str) else None

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.queued",
            payload={
                "repo": repo,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "kind": "pr.review",
            },
        )
        self._conn.commit()

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.started",
            payload={
                "repo": repo,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "peer_url": peer_url,
            },
        )
        self._conn.commit()

        await self._notify(
            "info",
            f"Reviewing PR #{pr_number}",
            f"{repo} · {head_sha[:7]}",
            click_url=pr_click_url,
        )

        started_at = time.monotonic()

        try:
            diff_text = await self._capture_diff(repo, pr_number)
        except Exception as exc:
            error_text = str(exc)[:_ERROR_TRUNCATE]
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={
                    "error": error_text,
                    "stage": "diff",
                },
            )
            self._conn.commit()
            await self._notify(
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        prompt = build_prompt(trigger_event, diff_text)
        buffer: list[str] = []
        terminal_state: str | None = None
        terminal_reason: str | None = None

        try:
            async with AsyncExitStack() as stack:
                cwd_str: str | None = None
                if self._worktree_manager is not None:
                    wt_path = await stack.enter_async_context(
                        self._worktree_manager.acquire(
                            key=f"pr-{pr_number}",
                            ref=f"pull/{pr_number}/head",
                        )
                    )
                    cwd_str = str(wt_path)
                client = await stack.enter_async_context(self._client)
                async for event in client.delegate(prompt, cwd=cwd_str):
                    kind, data = _normalize_event(event)
                    if kind == "message":
                        text = str(data.get("text", ""))
                        partial = bool(data.get("partial", False))
                        buffer.append(text)
                        eventlog.append_event(
                            self._conn,
                            run_id=run_id,
                            kind="agent.message",
                            payload={"text": text, "partial": partial},
                        )
                        self._conn.commit()
                    elif kind == "state":
                        state = str(data.get("state", ""))
                        if state in {"submitted", "working"}:
                            eventlog.append_event(
                                self._conn,
                                run_id=run_id,
                                kind="agent.state",
                                payload={"state": state},
                            )
                            self._conn.commit()
                        elif state == "completed":
                            terminal_state = "completed"
                            break
                        elif state in {"failed", "cancelled"}:
                            terminal_state = state
                            terminal_reason = data.get("reason")
                            break
                    else:
                        eventlog.append_event(
                            self._conn,
                            run_id=run_id,
                            kind=f"agent.{kind}",
                            payload=dict(data),
                        )
                        self._conn.commit()
        except Exception as exc:
            error_text = str(exc)[:_ERROR_TRUNCATE]
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={
                    "error": error_text,
                    "stage": "delegate",
                },
            )
            self._conn.commit()
            await self._notify(
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        if terminal_state == "failed":
            error_text = (
                str(terminal_reason)[:_ERROR_TRUNCATE] if terminal_reason else "failed"
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
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        if terminal_state == "cancelled":
            error_text = "cancelled by peer"
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={"error": error_text, "stage": "delegate"},
            )
            self._conn.commit()
            await self._notify(
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        if terminal_state != "completed":
            error_text = "delegate stream ended without terminal state"
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={
                    "error": error_text,
                    "stage": "delegate",
                },
            )
            self._conn.commit()
            await self._notify(
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        review_text = "".join(buffer)
        skipped, reason = detect_no_review(review_text)
        if skipped:
            skip_reason = reason or "agent_declined"
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.skipped",
                level="warn",
                payload={"reason": "agent_declined", "detail": reason or ""},
            )
            self._conn.commit()
            await self._notify(
                "warn",
                f"PR #{pr_number} review skipped",
                skip_reason,
                click_url=pr_click_url,
            )
            return

        try:
            artifact_url = await self._post_review(repo, pr_number, review_text)
        except Exception as exc:
            error_text = str(exc)[:_ERROR_TRUNCATE]
            eventlog.append_event(
                self._conn,
                run_id=run_id,
                kind="run.failed",
                level="error",
                payload={
                    "error": error_text,
                    "stage": "post",
                },
            )
            self._conn.commit()
            await self._notify(
                "error",
                f"PR #{pr_number} review FAILED",
                error_text[:_NOTIF_ERROR_TRUNCATE],
                click_url=pr_click_url,
            )
            return

        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="gh.review.posted",
            payload={
                "artifact_url": artifact_url,
                "comment_length": len(review_text),
            },
        )
        self._conn.commit()

        duration = time.monotonic() - started_at
        duration_rounded = round(duration, 3)
        eventlog.append_event(
            self._conn,
            run_id=run_id,
            kind="run.completed",
            payload={
                "artifact_url": artifact_url,
                "duration_seconds": duration_rounded,
            },
        )
        self._conn.commit()

        await self._notify(
            "info",
            f"Review posted on PR #{pr_number}",
            f"{duration_rounded}s · {len(review_text)} chars",
            click_url=artifact_url or pr_click_url,
        )

    def _peer_url(self) -> str:
        for attr in ("peer_url", "_peer_url"):
            value = getattr(self._client, attr, None)
            if isinstance(value, str):
                return value
        return ""

    async def _capture_diff(self, repo: str, pr_number: int) -> str:
        gh = shutil.which("gh") or "gh"
        proc = await asyncio.create_subprocess_exec(
            gh,
            "pr",
            "diff",
            str(pr_number),
            "--repo",
            repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        if proc.returncode not in (0, None):
            raise RuntimeError(
                f"gh pr diff exited {proc.returncode}: "
                f"{stderr_b.decode('utf-8', errors='replace')[:_ERROR_TRUNCATE]}"
            )
        return stdout_b.decode("utf-8", errors="replace")

    async def _post_review(self, repo: str, pr_number: int, review_text: str) -> str:
        gh = shutil.which("gh") or "gh"
        proc = await asyncio.create_subprocess_exec(
            gh,
            "pr",
            "review",
            str(pr_number),
            "--repo",
            repo,
            "--comment",
            "-F",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate(review_text.encode("utf-8"))
        if proc.returncode not in (0, None):
            raise RuntimeError(
                f"gh pr review exited {proc.returncode}: "
                f"{stderr_b.decode('utf-8', errors='replace')[:_ERROR_TRUNCATE]}"
            )
        return stdout_b.decode("utf-8", errors="replace").strip()


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
