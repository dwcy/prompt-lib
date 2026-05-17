"""GitHub Issues polling trigger (T009).

Polls ``gh issue list --json …`` on a fixed interval, diffs against the
``issue_cursor`` table, and yields ``TriggerEvent`` records for new
untriaged issues. Mirrors ``github_poll.py`` error-handling conventions.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from orchestrator import eventlog
from orchestrator.notifier import Notifier
from orchestrator.triggers.base import TriggerEvent

_GH_LIST_ARGS: tuple[str, ...] = (
    "issue",
    "list",
    "--state",
    "open",
    "--json",
    "number,title,body,labels,author,createdAt,state",
    "--limit",
    "100",
)

_SENTINEL_SHA = "0" * 40
_STDERR_TRUNCATE = 200


class GithubIssuesPollTrigger:
    """Async iterator over new GitHub issues derived from ``gh issue list``."""

    def __init__(
        self,
        *,
        repo: str,
        poll_seconds: float,
        eventlog_conn: sqlite3.Connection,
        notifier: Notifier | None = None,
    ) -> None:
        self._repo = repo
        self._poll_seconds = poll_seconds
        self._conn = eventlog_conn
        self._notifier = notifier
        self._stop = asyncio.Event()
        self._paused = False
        self._proc: asyncio.subprocess.Process | None = None

    async def _notify_auth_failed(self, detail: str) -> None:
        if self._notifier is None:
            return
        try:
            await self._notifier.send(
                level="error",
                title="Auth failed: gh",
                body=detail[:160],
            )
        except Exception:
            return

    async def events(self) -> AsyncIterator[TriggerEvent]:
        while not self._stop.is_set() and not self._paused:
            poll_task = asyncio.create_task(self._poll_once())
            try:
                stdout, stderr, returncode = await asyncio.shield(poll_task)
            except asyncio.CancelledError:
                stdout, stderr, returncode = await poll_task
                if returncode != 0:
                    await self._handle_error(stderr, returncode)
                else:
                    self._process_stdout(stdout)
                return

            if self._stop.is_set():
                if returncode != 0:
                    await self._handle_error(stderr, returncode)
                else:
                    for trigger_event in self._process_stdout(stdout):
                        yield trigger_event
                return

            if returncode != 0:
                paused = await self._handle_error(stderr, returncode)
                if paused:
                    return
                continue

            for trigger_event in self._process_stdout(stdout):
                yield trigger_event

            try:
                await asyncio.sleep(self._poll_seconds)
            except asyncio.CancelledError:
                return

    async def aclose(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            await proc.wait()
        except asyncio.CancelledError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    async def _poll_once(self) -> tuple[str, str, int]:
        gh = shutil.which("gh") or "gh"
        argv = (gh, *_GH_LIST_ARGS, "--repo", self._repo)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._proc = proc
        try:
            stdout_b, stderr_b = await proc.communicate()
        finally:
            self._proc = None
        return (
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
            proc.returncode if proc.returncode is not None else -1,
        )

    async def _handle_error(self, stderr: str, returncode: int) -> bool:
        """Map a non-zero gh exit to a typed eventlog entry. Returns True iff
        the polling loop should pause."""
        lowered = stderr.lower()
        detail = stderr[:_STDERR_TRUNCATE]

        if "not authenticated" in lowered:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="auth.failed",
                level="error",
                payload={"which": "gh", "detail": detail},
            )
            self._conn.commit()
            await self._notify_auth_failed(detail)
            self._paused = True
            return True

        if "not found" in lowered:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="auth.failed",
                level="error",
                payload={"which": "gh", "detail": detail},
            )
            self._conn.commit()
            await self._notify_auth_failed(detail)
            self._paused = True
            return True

        if "rate limit" in lowered:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.rate_limited",
                level="warn",
                payload={"detail": detail},
            )
            self._conn.commit()
            try:
                await asyncio.sleep(self._poll_seconds * 2)
            except asyncio.CancelledError:
                return True
            return False

        eventlog.append_event(
            self._conn,
            run_id="00000000-0000-0000-0000-000000000000",
            kind="gh.transient",
            level="warn",
            payload={"returncode": returncode, "stderr": detail},
        )
        self._conn.commit()
        try:
            await asyncio.sleep(self._poll_seconds)
        except asyncio.CancelledError:
            return True
        return False

    def _process_stdout(self, stdout: str) -> list[TriggerEvent]:
        try:
            rows = json.loads(stdout) if stdout.strip() else []
        except json.JSONDecodeError:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": {"raw": stdout[:_STDERR_TRUNCATE]}},
            )
            self._conn.commit()
            return []

        if not isinstance(rows, list):
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": {"raw": stdout[:_STDERR_TRUNCATE]}},
            )
            self._conn.commit()
            return []

        now = datetime.now(UTC)
        emitted: list[TriggerEvent] = []
        for row in rows:
            parsed = self._validate_row(row)
            if parsed is None:
                continue
            issue_number, payload = parsed

            if eventlog.issue_cursor_is_triaged(self._conn, issue_number, self._repo):
                eventlog.append_event(
                    self._conn,
                    run_id="00000000-0000-0000-0000-000000000000",
                    kind="run.skipped",
                    level="info",
                    payload={"issue_number": issue_number, "reason": "already_triaged"},
                )
                self._conn.commit()
                continue

            emitted.append(
                TriggerEvent(
                    kind="issue.opened",
                    repo=self._repo,
                    pr_number=issue_number,
                    head_sha=_SENTINEL_SHA,
                    detected_at=now,
                    payload=payload,
                )
            )

        return emitted

    def _validate_row(self, row: Any) -> tuple[int, dict[str, Any]] | None:
        if not isinstance(row, dict):
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row if isinstance(row, (str, int, float, bool)) else {}},
            )
            self._conn.commit()
            return None

        try:
            number_raw = row["number"]
            title = row["title"]
            body = row["body"]
            labels_raw = row["labels"]
            author_raw = row["author"]
        except KeyError:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(number_raw, int) or isinstance(number_raw, bool) or number_raw <= 0:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if isinstance(labels_raw, list):
            labels: list[str] = [
                item["name"]
                for item in labels_raw
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
        else:
            labels = []

        if isinstance(author_raw, dict):
            login = author_raw.get("login")
            author_login: str = login if isinstance(login, str) else ""
        else:
            author_login = ""

        payload: dict[str, Any] = {
            "issue_number": number_raw,
            "title": title if isinstance(title, str) else "",
            "body": body if isinstance(body, str) else "",
            "labels": labels,
            "author": author_login,
        }

        return number_raw, payload
