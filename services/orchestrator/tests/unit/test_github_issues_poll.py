"""Unit tests for GithubIssuesPollTrigger (T007 + T016).

Per Constitution Gate 3, the contract test in
``tests/contract/test_gh_issue_list_schema.py`` covers the wire format.
These unit tests cover trigger lifecycle, error handling, and duplicate
suppression (US4, T016).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator import eventlog
from orchestrator.triggers.github_issues_poll import GithubIssuesPollTrigger

_ISSUE = {
    "number": 7,
    "title": "Bug: null pointer on login",
    "body": "Steps: ...",
    "state": "OPEN",
    "labels": [{"name": "bug"}],
    "author": {"login": "bob"},
    "createdAt": "2026-05-12T09:00:00Z",
}


def _make(tmp_path: Path) -> tuple[GithubIssuesPollTrigger, Path]:
    db = tmp_path / "events.db"
    eventlog.bootstrap(db)
    conn = eventlog.connect(db)
    trigger = GithubIssuesPollTrigger(
        repo="owner/repo",
        poll_seconds=30.0,
        eventlog_conn=conn,
    )
    return trigger, db


# ---------------------------------------------------------------------------
# _process_stdout
# ---------------------------------------------------------------------------


class TestProcessStdout:
    def test_new_issue_yields_trigger_event(self, tmp_path: Path) -> None:
        trigger, _ = _make(tmp_path)
        events = trigger._process_stdout(json.dumps([_ISSUE]))
        assert len(events) == 1
        ev = events[0]
        assert ev.kind == "issue.opened"
        assert ev.repo == "owner/repo"
        assert ev.pr_number == 7

    def test_payload_fields_populated(self, tmp_path: Path) -> None:
        trigger, _ = _make(tmp_path)
        events = trigger._process_stdout(json.dumps([_ISSUE]))
        p = events[0].payload
        assert p["issue_number"] == 7
        assert p["title"] == "Bug: null pointer on login"
        assert p["body"] == "Steps: ..."
        assert p["labels"] == ["bug"]
        assert p["author"] == "bob"

    def test_empty_stdout_yields_nothing(self, tmp_path: Path) -> None:
        trigger, _ = _make(tmp_path)
        assert trigger._process_stdout("[]") == []

    def test_invalid_json_emits_parse_failed_event(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        result = trigger._process_stdout("not-json")
        assert result == []
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "gh.parse.failed" for e in events)

    def test_missing_required_field_emits_parse_failed(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        bad_item = {k: v for k, v in _ISSUE.items() if k != "number"}
        result = trigger._process_stdout(json.dumps([bad_item]))
        assert result == []
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "gh.parse.failed" for e in events)

    def test_multiple_issues_all_returned(self, tmp_path: Path) -> None:
        trigger, _ = _make(tmp_path)
        second = {**_ISSUE, "number": 8, "title": "Second"}
        events = trigger._process_stdout(json.dumps([_ISSUE, second]))
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Error handling via _handle_error
# ---------------------------------------------------------------------------


class TestHandleError:
    def test_auth_failed_pauses_trigger(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        paused = asyncio.get_event_loop().run_until_complete(
            trigger._handle_error("not authenticated — gh auth login", 1)
        )
        assert paused is True
        assert trigger._paused is True
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "auth.failed" for e in events)

    def test_rate_limit_does_not_pause(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        # patch sleep to avoid waiting
        async def _fast_handle():
            trigger._poll_seconds = 0.0
            return await trigger._handle_error("API rate limit exceeded", 1)
        paused = asyncio.get_event_loop().run_until_complete(_fast_handle())
        assert paused is False
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "gh.rate_limited" for e in events)

    def test_transient_error_does_not_pause(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        async def _fast_handle():
            trigger._poll_seconds = 0.0
            return await trigger._handle_error("connection reset", 1)
        paused = asyncio.get_event_loop().run_until_complete(_fast_handle())
        assert paused is False
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "gh.transient" for e in events)


# ---------------------------------------------------------------------------
# Duplicate suppression (US4 — T016)
# ---------------------------------------------------------------------------


class TestDuplicateSuppression:
    def test_already_triaged_issue_not_yielded(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        # Pre-mark issue 7 as triaged
        eventlog.issue_cursor_mark_triaged(conn, 7, "owner/repo")
        conn.commit()
        events = trigger._process_stdout(json.dumps([_ISSUE]))
        assert events == []

    def test_already_triaged_emits_run_skipped(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        conn = eventlog.connect(db)
        eventlog.issue_cursor_mark_triaged(conn, 7, "owner/repo")
        conn.commit()
        trigger._process_stdout(json.dumps([_ISSUE]))
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.skipped" for e in events)

    def test_untriaged_issue_is_yielded(self, tmp_path: Path) -> None:
        trigger, db = _make(tmp_path)
        events = trigger._process_stdout(json.dumps([_ISSUE]))
        assert len(events) == 1
        assert events[0].payload["issue_number"] == 7

    def test_different_repo_not_suppressed(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        eventlog.bootstrap(db)
        conn = eventlog.connect(db)
        # Mark as triaged for a DIFFERENT repo
        eventlog.issue_cursor_mark_triaged(conn, 7, "other/repo")
        conn.commit()
        trigger = GithubIssuesPollTrigger(
            repo="owner/repo",
            poll_seconds=30.0,
            eventlog_conn=conn,
        )
        events = trigger._process_stdout(json.dumps([_ISSUE]))
        assert len(events) == 1
