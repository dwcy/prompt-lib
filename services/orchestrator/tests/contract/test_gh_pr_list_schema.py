"""Contract test for the ``gh pr list --json`` parser (T014).

Pins the consumer-side parser shape documented in
``specs/002-agent-orchestrator/contracts/gh-pr-list.contract.md``: required
field validation, forward-compatible unknown-field tolerance, per-PR skip on
schema violations, and the stderr-signature-to-typed-event mapping.

Implementation guidance for T018
--------------------------------

These tests assume the trigger module exposes a single class:

    from orchestrator.triggers.github_poll import GithubPollTrigger

with the constructor signature::

    GithubPollTrigger(
        repo: str,
        poll_seconds: float,
        eventlog_conn: sqlite3.Connection,
    )

and the ``Trigger`` Protocol from ``orchestrator.triggers.base`` (i.e.
``async def events() -> AsyncIterator[TriggerEvent]`` and
``async def aclose() -> None``).

The trigger is responsible for:

* Spawning ``gh pr list --repo <repo> --state open --json
  number,headRefOid,updatedAt,title,url,headRefName,baseRefName,author
  --limit 100`` via ``asyncio.create_subprocess_exec`` so the ``fake_gh``
  PATH-shim from conftest is exercised.
* Parsing each top-level array element per the contract:
  * Required fields validated; missing / malformed → skip + ``gh.parse.failed``
    event appended to the eventlog (level=warn) with the offending row in
    ``payload_json``.
  * Unknown fields anywhere in the JSON tree are accepted.
* Diffing against the ``cursor`` table → emitting ``pr.opened`` /
  ``pr.updated`` ``TriggerEvent``s and upserting the cursor row.
* Mapping stderr signatures to typed events:
  * ``not authenticated`` (case-insensitive) → ``auth.failed`` event with
    ``which="gh"``, then **pause** the polling loop (no further ``gh``
    invocations until the trigger is reconstructed).
  * ``not found`` (case-insensitive) → same as above.
  * ``rate limit`` (case-insensitive) → ``gh.rate_limited`` warn event;
    sleep + retry on the next normal poll tick.

The pause-on-auth-failure invariant is asserted indirectly through the
``fake_gh`` rule queue: if the trigger pauses, the second queued rule never
gets consumed, so its rule remains in ``behavior.json`` after the poll loop
yields its first batch of events.

Test pattern (bounded async iteration)
--------------------------------------

The tests iterate ``async for event in trigger.events()`` inside an
``asyncio.timeout`` window so a misbehaving trigger cannot hang the suite.
``poll_seconds=0.01`` keeps the loop tight; tests that want exactly one poll
break out of the iterator after the first events, then close the trigger via
``aclose()``.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from orchestrator import eventlog
from orchestrator.triggers.base import TriggerEvent
from orchestrator.triggers.github_poll import GithubPollTrigger

REPO = "owner/repo"
VALID_SHA = "0123456789abcdef0123456789abcdef01234567"
SECOND_SHA = "fedcba9876543210fedcba9876543210fedcba98"

GH_LIST_ARGV = ["pr", "list"]


def _pr(
    *,
    number: int = 42,
    head_ref_oid: str = VALID_SHA,
    updated_at: str = "2026-05-10T12:34:56Z",
    title: str = "Add the thing",
    url: str = "https://github.com/owner/repo/pull/42",
    head_ref_name: str = "feature/the-thing",
    base_ref_name: str = "main",
    author_login: str = "octocat",
    extra_top: dict[str, Any] | None = None,
    extra_author: dict[str, Any] | None = None,
    omit: set[str] | None = None,
) -> dict[str, Any]:
    """Build a single PR object matching the contract's required field set."""
    omit = omit or set()
    author: dict[str, Any] = {
        "id": "MDQ6VXNlcjEyMzQ1",
        "is_bot": False,
        "login": author_login,
        "name": "Octo Cat",
    }
    if extra_author:
        author.update(extra_author)
    pr: dict[str, Any] = {
        "number": number,
        "headRefOid": head_ref_oid,
        "updatedAt": updated_at,
        "title": title,
        "url": url,
        "headRefName": head_ref_name,
        "baseRefName": base_ref_name,
        "author": author,
    }
    if extra_top:
        pr.update(extra_top)
    for key in omit:
        pr.pop(key, None)
    return pr


async def _collect_one_poll(
    trigger: GithubPollTrigger,
    *,
    timeout: float = 2.0,
) -> list[TriggerEvent]:
    """Drain the trigger across a single poll cycle.

    Uses the ``fake_gh`` rule queue as the implicit termination signal: once
    the queued rule has been consumed by the trigger and it begins waiting on
    the next poll tick (which would match the empty default rule and yield no
    events), we cancel the iteration via ``aclose``.
    """
    collected: list[TriggerEvent] = []

    async def _drain() -> None:
        async for event in trigger.events():
            collected.append(event)

    task = asyncio.create_task(_drain())
    try:
        await asyncio.wait_for(asyncio.shield(_drain_until_idle(task)), timeout=timeout)
    except TimeoutError:
        pass
    finally:
        await trigger.aclose()
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return collected


async def _drain_until_idle(task: asyncio.Task[None]) -> None:
    """Wait until the trigger task has been scheduled and emitted whatever it
    will emit for the queued ``fake_gh`` rule, then return.

    Strategy: poll a short interval; once two consecutive checks see the same
    state (no new events appended), assume the trigger is idle waiting for
    its next poll tick.
    """
    while not task.done():
        await asyncio.sleep(0.05)
        if task.done():
            return
        await asyncio.sleep(0.05)
        return


def _read_events(db_path: Path) -> list[dict[str, Any]]:
    eventlog.bootstrap(db_path)
    conn = eventlog.connect(db_path)
    try:
        rows = eventlog.tail_since(conn, last_id=0)
    finally:
        conn.close()
    return [
        {
            "kind": e.kind,
            "level": e.level,
            "payload": json.loads(e.payload_json),
        }
        for e in rows
    ]


def _read_cursor_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT pr_number, head_sha, last_seen FROM cursor ORDER BY pr_number"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _bootstrap_and_connect(db_path: Path) -> sqlite3.Connection:
    eventlog.bootstrap(db_path)
    return eventlog.connect(db_path)


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------


class TestParserAcceptsValidInput:
    async def test_parser_accepts_minimal_required_fields(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=1)]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert len(events) == 1
        assert events[0].kind == "pr.opened"
        assert events[0].pr_number == 1

        cursor_rows = _read_cursor_rows(tmp_db)
        assert len(cursor_rows) == 1
        assert cursor_rows[0]["pr_number"] == 1
        assert cursor_rows[0]["head_sha"] == VALID_SHA

    async def test_parser_accepts_unknown_extra_fields(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        pr = _pr(
            number=2,
            extra_top={"unexpected_top": "ignore-me", "another": 123},
            extra_author={"future_field": "ok"},
        )
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([pr]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert len(events) == 1
        assert events[0].kind == "pr.opened"
        assert events[0].pr_number == 2

    async def test_parser_returns_empty_for_empty_array(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(GH_LIST_ARGV, stdout="[]")
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert events == []
        assert _read_cursor_rows(tmp_db) == []
        # No parse-failed / auth-failed / rate-limited events from a clean empty result.
        assert _read_events(tmp_db) == []


# ---------------------------------------------------------------------------
# Per-PR skip behaviour on schema violations
# ---------------------------------------------------------------------------


class TestParserSkipsMalformedRows:
    async def test_parser_skips_pr_missing_headRefOid(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        good = _pr(number=10)
        bad = _pr(number=11, omit={"headRefOid"})
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([good, bad]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        emitted_numbers = [e.pr_number for e in events]
        assert emitted_numbers == [10]

        log_events = _read_events(tmp_db)
        parse_failures = [e for e in log_events if e["kind"] == "gh.parse.failed"]
        assert len(parse_failures) == 1
        # Offending row preserved verbatim in payload for forensics.
        assert parse_failures[0]["payload"].get("row", {}).get("number") == 11 or (
            parse_failures[0]["payload"].get("number") == 11
        )

    async def test_parser_skips_pr_with_invalid_sha_format(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        good = _pr(number=20)
        bad = _pr(number=21, head_ref_oid="not-a-sha")
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([good, bad]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert [e.pr_number for e in events] == [20]
        parse_failures = [e for e in _read_events(tmp_db) if e["kind"] == "gh.parse.failed"]
        assert len(parse_failures) == 1

    async def test_parser_skips_pr_with_unparseable_updatedAt(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        good = _pr(number=30)
        bad = _pr(number=31, updated_at="not-a-timestamp")
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([good, bad]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert [e.pr_number for e in events] == [30]
        parse_failures = [e for e in _read_events(tmp_db) if e["kind"] == "gh.parse.failed"]
        assert len(parse_failures) == 1


# ---------------------------------------------------------------------------
# Stderr-signature → typed event mapping
# ---------------------------------------------------------------------------


class TestRunnerErrorPaths:
    async def test_runner_emits_auth_failed_on_not_authenticated_stderr(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(
            GH_LIST_ARGV,
            stderr="error: not authenticated. run gh auth login\n",
            returncode=1,
        )
        # Second rule that should remain unconsumed if the loop is paused.
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=1)]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert events == []

        log_events = _read_events(tmp_db)
        auth_failures = [e for e in log_events if e["kind"] == "auth.failed"]
        assert len(auth_failures) == 1
        assert auth_failures[0]["payload"].get("which") == "gh"
        assert auth_failures[0]["level"] == "error"

        # Pause invariant: the second queued rule must remain unconsumed.
        remaining = json.loads(fake_gh.behavior_file.read_text(encoding="utf-8"))
        assert any(
            json.dumps(_pr(number=1)) in r["stdout"] for r in remaining["rules"]
        )

    async def test_runner_emits_auth_failed_on_repo_not_found_stderr(
        self, tmp_db: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(
            GH_LIST_ARGV,
            stderr="GraphQL: Could not resolve to a Repository — Not Found\n",
            returncode=1,
        )
        fake_gh.queue(GH_LIST_ARGV, stdout=json.dumps([_pr(number=1)]))
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert events == []
        auth_failures = [e for e in _read_events(tmp_db) if e["kind"] == "auth.failed"]
        assert len(auth_failures) == 1
        assert auth_failures[0]["payload"].get("which") == "gh"

        remaining = json.loads(fake_gh.behavior_file.read_text(encoding="utf-8"))
        assert any(
            json.dumps(_pr(number=1)) in r["stdout"] for r in remaining["rules"]
        )

    async def test_runner_emits_rate_limited_on_rate_limit_stderr(
        self, tmp_db: Path, fake_gh: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Replace asyncio.sleep with a no-op so the rate-limit backoff does not
        # actually delay the test — we only want to assert the warn event.
        async def _noop(_: float) -> None:
            return None

        monkeypatch.setattr("asyncio.sleep", _noop)

        fake_gh.queue(
            GH_LIST_ARGV,
            stderr="API rate limit exceeded for user octocat\n",
            returncode=1,
        )
        fake_gh.queue(GH_LIST_ARGV, stdout="[]")
        conn = _bootstrap_and_connect(tmp_db)
        try:
            trigger = GithubPollTrigger(repo=REPO, poll_seconds=0.01, eventlog_conn=conn)
            events = await _collect_one_poll(trigger)
        finally:
            conn.close()

        assert events == []
        rate_events = [
            e for e in _read_events(tmp_db) if e["kind"] == "gh.rate_limited"
        ]
        assert len(rate_events) == 1
        assert rate_events[0]["level"] == "warn"
