"""GitHub polling trigger (T018).

Polls ``gh pr list --json …`` on a fixed interval, diffs the result against the
``cursor`` table in the eventlog DB, and yields ``TriggerEvent`` records for
new or updated PRs. Stderr signatures are mapped to typed eventlog entries per
``contracts/gh-pr-list.contract.md``; ``auth.failed`` and ``not found`` pause
the polling loop until the trigger is reconstructed.

The ``gh.parse.failed`` payload uses ``{"row": <raw row dict>}`` so the
offending element is preserved verbatim for forensics. ``data-model.md`` does
not pin the shape; this is the chosen contract.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from orchestrator import eventlog
from orchestrator.notifier import Notifier
from orchestrator.triggers.base import TriggerEvent

_GH_LIST_ARGS: tuple[str, ...] = (
    "pr",
    "list",
    "--state",
    "open",
    "--json",
    "number,headRefOid,updatedAt,title,url,headRefName,baseRefName,author",
    "--limit",
    "100",
)

_HEAD_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_STDERR_TRUNCATE = 200


class GithubPollTrigger:
    """Async iterator over PR-state changes derived from ``gh pr list``."""

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
        """Push an ``auth.failed`` notification; swallow exceptions so a
        notifier bug cannot abort the polling loop (matches ``pr_review.py``
        ``_notify`` pattern)."""
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
        the polling loop should pause (i.e. exit the generator)."""
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

        validated: list[tuple[int, str, str, dict[str, Any]]] = []
        for row in rows:
            parsed = self._validate_row(row)
            if parsed is None:
                continue
            validated.append(parsed)

        validated.sort(key=lambda item: item[0])

        emitted: list[TriggerEvent] = []
        now = datetime.now(UTC)
        for pr_number, head_sha, updated_at, row_dict in validated:
            cursor = eventlog.cursor_get(self._conn, pr_number)
            if cursor is None:
                eventlog.cursor_upsert(
                    self._conn,
                    pr_number=pr_number,
                    head_sha=head_sha,
                    last_seen=now,
                )
                self._conn.commit()
                emitted.append(
                    self._build_event(
                        kind="pr.opened",
                        pr_number=pr_number,
                        head_sha=head_sha,
                        updated_at=updated_at,
                        row=row_dict,
                        detected_at=now,
                    )
                )
            elif cursor.head_sha == head_sha:
                eventlog.cursor_upsert(
                    self._conn,
                    pr_number=pr_number,
                    head_sha=head_sha,
                    last_seen=now,
                )
                self._conn.commit()
            else:
                eventlog.cursor_upsert(
                    self._conn,
                    pr_number=pr_number,
                    head_sha=head_sha,
                    last_seen=now,
                )
                self._conn.commit()
                emitted.append(
                    self._build_event(
                        kind="pr.updated",
                        pr_number=pr_number,
                        head_sha=head_sha,
                        updated_at=updated_at,
                        row=row_dict,
                        detected_at=now,
                    )
                )

        return emitted

    def _validate_row(
        self, row: Any
    ) -> tuple[int, str, str, dict[str, Any]] | None:
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
            head_ref_oid = row["headRefOid"]
            updated_at = row["updatedAt"]
            title = row["title"]
            url = row["url"]
            head_ref_name = row["headRefName"]
            base_ref_name = row["baseRefName"]
            author = row["author"]
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

        if not isinstance(head_ref_oid, str) or not _HEAD_SHA_RE.match(head_ref_oid):
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(updated_at, str) or not _is_parseable_iso(updated_at):
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(title, str) or not title:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(url, str) or not url:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(head_ref_name, str) or not head_ref_name:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(base_ref_name, str) or not base_ref_name:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        if not isinstance(author, dict):
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        author_login = author.get("login")
        if not isinstance(author_login, str) or not author_login:
            eventlog.append_event(
                self._conn,
                run_id="00000000-0000-0000-0000-000000000000",
                kind="gh.parse.failed",
                level="warn",
                payload={"row": row},
            )
            self._conn.commit()
            return None

        return number_raw, head_ref_oid, updated_at, row

    def _build_event(
        self,
        *,
        kind: str,
        pr_number: int,
        head_sha: str,
        updated_at: str,
        row: dict[str, Any],
        detected_at: datetime,
    ) -> TriggerEvent:
        author = row.get("author") or {}
        author_login = author.get("login") if isinstance(author, dict) else None
        return TriggerEvent(
            kind=kind,  # type: ignore[arg-type]
            repo=self._repo,
            pr_number=pr_number,
            head_sha=head_sha,
            detected_at=detected_at,
            payload={
                "title": row.get("title"),
                "url": row.get("url"),
                "headRefName": row.get("headRefName"),
                "baseRefName": row.get("baseRefName"),
                "author_login": author_login,
                "updatedAt": updated_at,
            },
        )


def _is_parseable_iso(value: str) -> bool:
    candidate = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True
