"""Contract test: ``gh issue list --json`` output schema (Constitution Gate 3).

Tests that ``GithubIssuesPollTrigger._process_stdout`` correctly parses the
wire format documented in ``specs/003-issue-triage/contracts/gh-issue-list.contract.md``.

Per Gate 3: this test MUST exist and FAIL (``ImportError``) before T009
creates ``triggers/github_issues_poll.py``.  Run with::

    uv run pytest tests/contract/test_gh_issue_list_schema.py

and observe it fail, then implement T009 and re-run to verify it passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Gate 3 import — fails with ImportError until T009 creates the module.
from orchestrator.triggers.github_issues_poll import GithubIssuesPollTrigger

from orchestrator import eventlog

_SAMPLE_ITEM: dict = {
    "number": 42,
    "title": "Login button broken on mobile",
    "body": "Steps to reproduce: ...",
    "state": "OPEN",
    "labels": [{"id": "abc123", "name": "bug", "description": "A bug", "color": "d73a4a"}],
    "author": {"login": "octocat", "id": "U_123", "name": "The Octocat"},
    "createdAt": "2026-05-12T08:00:00Z",
}


def _make_trigger(tmp_path: Path) -> GithubIssuesPollTrigger:
    db = tmp_path / "events.db"
    eventlog.bootstrap(db)
    conn = eventlog.connect(db)
    return GithubIssuesPollTrigger(
        repo="owner/repo",
        poll_seconds=30.0,
        eventlog_conn=conn,
    )


class TestGhIssueListSchema:
    def test_single_open_issue_yields_one_event(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert len(events) == 1

    def test_empty_array_yields_no_events(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        assert trigger._process_stdout("[]") == []

    def test_event_kind_is_issue_opened(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].kind == "issue.opened"

    def test_issue_number_in_payload(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].payload["issue_number"] == 42

    def test_title_in_payload(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].payload["title"] == "Login button broken on mobile"

    def test_labels_extracted_as_name_list(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].payload["labels"] == ["bug"]

    def test_empty_labels_tolerated(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        item = dict(_SAMPLE_ITEM)
        item["labels"] = []
        events = trigger._process_stdout(json.dumps([item]))
        assert events[0].payload["labels"] == []

    def test_author_login_in_payload(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].payload["author"] == "octocat"

    def test_body_in_payload(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        events = trigger._process_stdout(json.dumps([_SAMPLE_ITEM]))
        assert events[0].payload["body"] == "Steps to reproduce: ..."

    def test_empty_body_tolerated(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        item = dict(_SAMPLE_ITEM)
        item["body"] = ""
        events = trigger._process_stdout(json.dumps([item]))
        assert events[0].payload["body"] == ""

    def test_extra_fields_in_item_tolerated(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        item = dict(_SAMPLE_ITEM)
        item["unknownExtraField"] = "should be ignored"
        events = trigger._process_stdout(json.dumps([item]))
        assert len(events) == 1

    def test_multiple_issues_all_yielded(self, tmp_path: Path) -> None:
        trigger = _make_trigger(tmp_path)
        items = [
            dict(_SAMPLE_ITEM),
            {**_SAMPLE_ITEM, "number": 43, "title": "Second issue"},
        ]
        events = trigger._process_stdout(json.dumps(items))
        assert len(events) == 2
        numbers = {e.payload["issue_number"] for e in events}
        assert numbers == {42, 43}
