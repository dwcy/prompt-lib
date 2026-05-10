"""Unit tests for ``triggers.github_poll`` cursor-diff logic (T016).

Pins the diff rules from ``data-model.md`` § Cursor:

* New ``pr_number`` → emit ``pr.opened`` + insert cursor row.
* Same ``pr_number`` + same ``head_sha`` → no event + ``last_seen`` updated.
* Same ``pr_number`` + different ``head_sha`` → emit ``pr.updated`` + cursor
  row updated.
* Closed PR (absent from poll) → no event, cursor row left in place.
* Multiple new PRs in one poll → emitted in ascending ``pr_number`` order.

Implementation guidance for T018
--------------------------------

The tests drive the trigger end-to-end through the ``fake_gh`` PATH-shim from
conftest. This was chosen over importing a private ``_diff`` helper because:

* The contract test (T014) already exercises the same external surface — these
  unit tests stay in the same shape so the implementer doesn't have to expose
  two different APIs.
* ``GithubPollTrigger`` is the only public name in the module; private
  parsing helpers are an implementation detail.

Constructor: ``GithubPollTrigger(repo, poll_seconds, eventlog_conn)``. The
trigger reads from the ``cursor`` table on the supplied connection and emits
``TriggerEvent`` records via ``async for event in trigger.events(): ...``.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from orchestrator import eventlog
from orchestrator.triggers.base import TriggerEvent
from orchestrator.triggers.github_poll import GithubPollTrigger

REPO = "owner/repo"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40

GH_LIST_ARGV = ["pr", "list"]


def _pr(*, number: int, head_ref_oid: str = SHA_A) -> dict[str, Any]:
    return {
        "number": number,
        "headRefOid": head_ref_oid,
        "updatedAt": "2026-05-10T12:34:56Z",
        "title": f"PR {number}",
        "url": f"https://github.com/owner/repo/pull/{number}",
        "headRefName": f"feature/{number}",
        "baseRefName": "main",
        "author": {"id": "X", "is_bot": False, "login": "octocat", "name": "Octo"},
    }


def _bootstrap(db_path: Path) -> sqlite3.Connection:
    eventlog.bootstrap(db_path)
    return eventlog.connect(db_path)


def _read_cursor(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                "SELECT pr_number, head_sha, last_seen FROM cursor ORDER BY pr_number"
            ).fetchall()
        )
    finally:
        conn.close()


async def _collect_one_poll(
    trigger: GithubPollTrigger, *, timeout: float = 2.0
) -> list[TriggerEvent]:
    collected: list[TriggerEvent] = []

    async def _run() -> None:
        async for event in trigger.events():
            collected.append(event)

    task = asyncio.create_task(_run())
    try:
        await asyncio.sleep(0.15)
    finally:
        await trigger.aclose()
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return collected


# ---------------------------------------------------------------------------
# New PR
# ---------------------------------------------------------------------------


async def test_new_pr_emits_pr_opened_and_inserts_cursor(
    tmp_db: Path, fake_gh: Any
) -> None:
    fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=7, head_ref_oid=SHA_A)]))
    conn = _bootstrap(tmp_db)
    try:
        trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
        events = await _collect_one_poll(trigger)
    finally:
        conn.close()

    assert len(events) == 1
    assert events[0].kind == "pr.opened"
    assert events[0].pr_number == 7
    assert events[0].head_sha == SHA_A

    cursor_rows = _read_cursor(tmp_db)
    assert len(cursor_rows) == 1
    assert cursor_rows[0]["pr_number"] == 7
    assert cursor_rows[0]["head_sha"] == SHA_A


# ---------------------------------------------------------------------------
# Unchanged head SHA
# ---------------------------------------------------------------------------


async def test_unchanged_head_sha_does_not_emit(
    tmp_db: Path, fake_gh: Any
) -> None:
    conn = _bootstrap(tmp_db)
    try:
        eventlog.cursor_upsert(
            conn, pr_number=7, head_sha=SHA_A, last_seen="2026-05-10T10:00:00+00:00"
        )
        conn.commit()
    finally:
        conn.close()

    fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=7, head_ref_oid=SHA_A)]))

    before = _read_cursor(tmp_db)
    before_last_seen = before[0]["last_seen"]

    conn = eventlog.connect(tmp_db)
    try:
        trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
        events = await _collect_one_poll(trigger)
    finally:
        conn.close()

    assert events == []

    after = _read_cursor(tmp_db)
    assert after[0]["pr_number"] == 7
    assert after[0]["head_sha"] == SHA_A
    assert after[0]["last_seen"] != before_last_seen


# ---------------------------------------------------------------------------
# Changed head SHA
# ---------------------------------------------------------------------------


async def test_changed_head_sha_emits_pr_updated_and_updates_cursor(
    tmp_db: Path, fake_gh: Any
) -> None:
    conn = _bootstrap(tmp_db)
    try:
        eventlog.cursor_upsert(
            conn, pr_number=7, head_sha=SHA_A, last_seen="2026-05-10T10:00:00+00:00"
        )
        conn.commit()
    finally:
        conn.close()

    fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=7, head_ref_oid=SHA_B)]))

    before = _read_cursor(tmp_db)
    before_last_seen = before[0]["last_seen"]

    conn = eventlog.connect(tmp_db)
    try:
        trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
        events = await _collect_one_poll(trigger)
    finally:
        conn.close()

    assert len(events) == 1
    assert events[0].kind == "pr.updated"
    assert events[0].pr_number == 7
    assert events[0].head_sha == SHA_B

    after = _read_cursor(tmp_db)
    assert after[0]["head_sha"] == SHA_B
    assert after[0]["last_seen"] != before_last_seen


# ---------------------------------------------------------------------------
# Closed PR (absent from poll)
# ---------------------------------------------------------------------------


async def test_closed_pr_no_event_cursor_left_in_place(
    tmp_db: Path, fake_gh: Any
) -> None:
    conn = _bootstrap(tmp_db)
    try:
        eventlog.cursor_upsert(
            conn, pr_number=7, head_sha=SHA_A, last_seen="2026-05-10T10:00:00+00:00"
        )
        conn.commit()
    finally:
        conn.close()

    fake_gh.queue(GH_LIST_ARGV, stdout="[]")

    conn = eventlog.connect(tmp_db)
    try:
        trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
        events = await _collect_one_poll(trigger)
    finally:
        conn.close()

    assert events == []

    after = _read_cursor(tmp_db)
    assert len(after) == 1
    assert after[0]["pr_number"] == 7
    assert after[0]["head_sha"] == SHA_A


# ---------------------------------------------------------------------------
# Multiple new PRs in one poll
# ---------------------------------------------------------------------------


async def test_two_new_prs_in_one_poll_emit_two_events_in_order_by_pr_number(
    tmp_db: Path, fake_gh: Any
) -> None:
    # Deliberately deliver them in descending order so we can assert the
    # trigger sorts by pr_number ascending before emitting.
    payload = [_pr(number=42, head_ref_oid=SHA_B), _pr(number=7, head_ref_oid=SHA_A)]
    fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps(payload))

    conn = _bootstrap(tmp_db)
    try:
        trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
        events = await _collect_one_poll(trigger)
    finally:
        conn.close()

    assert [e.kind for e in events] == ["pr.opened", "pr.opened"]
    assert [e.pr_number for e in events] == [7, 42]
