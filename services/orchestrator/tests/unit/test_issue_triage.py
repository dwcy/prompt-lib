"""Unit tests for IssueTiageAgent (T008 + T012 + T014).

Tests cover:
- Core triage: JSON block parsed → TriageDecision → triage.decision event (T008)
- Comment posting: _post_comment success/failure non-fatal semantics (T012)
- Notification calls at detection, completion, failure (T014)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator import eventlog
from orchestrator.agents.issue_triage import IssueTiageAgent
from orchestrator.triggers.base import TriggerEvent

_VALID_TRIAGE_JSON = json.dumps(
    {
        "category": "bug",
        "severity": "P2",
        "assessment": "The login button is broken on iOS Safari due to a CSS z-index issue.",
        "routing": "@frontend-architect",
    }
)

_SELF_ROUTING_JSON = json.dumps(
    {
        "category": "question",
        "severity": "P4",
        "assessment": "User is asking how to reset their password.",
        "routing": "self",
    }
)


def _make_issue_event(issue_number: int = 42, title: str = "Login broken") -> TriggerEvent:
    return TriggerEvent(
        kind="issue.opened",
        repo="owner/repo",
        pr_number=issue_number,
        head_sha="0" * 40,
        detected_at=datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
        payload={
            "issue_number": issue_number,
            "title": title,
            "body": "Steps to reproduce ...",
            "labels": ["bug"],
            "author": "alice",
        },
    )


class _FakeDelegationClient:
    def __init__(self, output: str) -> None:
        self._output = output
        self.prompts: list[str] = []

    async def __aenter__(self) -> "_FakeDelegationClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def delegate(
        self, prompt: str, *, cwd: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        self.prompts.append(prompt)
        yield {"event": "task.state", "data": {"state": "submitted"}}
        yield {"event": "task.artifact", "data": {"artifact": {"content": self._output}}}
        yield {"event": "task.state", "data": {"state": "completed"}}


class _FailingDelegationClient:
    async def __aenter__(self) -> "_FailingDelegationClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def delegate(self, prompt: str, *, cwd: str | None = None) -> AsyncIterator[dict]:
        yield {"event": "task.state", "data": {"state": "failed", "reason": "timeout"}}


def _make_agent(
    tmp_path: Path,
    output: str = "",
    *,
    fail: bool = False,
    notifier: Any = None,
) -> tuple[IssueTiageAgent, Path]:
    db = tmp_path / "events.db"
    eventlog.bootstrap(db)
    conn = eventlog.connect(db)
    client = _FailingDelegationClient() if fail else _FakeDelegationClient(output)
    agent = IssueTiageAgent(
        delegation_client=client,
        eventlog_conn=conn,
        notifier=notifier,
    )
    return agent, db


# ---------------------------------------------------------------------------
# Core triage parsing (T008)
# ---------------------------------------------------------------------------


class TestCoreTriage:
    def test_valid_json_block_emits_triage_decision(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"Analysis:\n```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        kinds = [e.kind for e in events]
        assert "triage.decision" in kinds

    def test_triage_decision_payload_contains_fields(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        decision_ev = next(e for e in events if e.kind == "triage.decision")
        payload = json.loads(decision_ev.payload_json)
        assert payload["category"] == "bug"
        assert payload["severity"] == "P2"
        assert payload["routing"] == "@frontend-architect"

    def test_routing_non_self_emits_triage_routed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "triage.routed" for e in events)

    def test_routing_self_does_not_emit_triage_routed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"```json\n{_SELF_ROUTING_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert not any(e.kind == "triage.routed" for e in events)

    def test_valid_run_emits_run_completed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.completed" for e in events)

    def test_invalid_json_block_emits_run_failed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output="```json\n{broken json\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.failed" for e in events)
        assert not any(e.kind == "run.completed" for e in events)

    def test_missing_required_key_emits_run_failed(self, tmp_path: Path) -> None:
        incomplete = json.dumps({"category": "bug", "severity": "P2"})
        agent, db = _make_agent(tmp_path, output=f"```json\n{incomplete}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.failed" for e in events)

    def test_no_json_block_at_all_emits_run_failed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output="Just some plain text, no JSON.")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.failed" for e in events)

    def test_delegate_failed_state_emits_run_failed(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, fail=True)
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.failed" for e in events)

    def test_issue_cursor_marked_after_success(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event(issue_number=42)))
        conn = eventlog.connect(db)
        assert eventlog.issue_cursor_is_triaged(conn, 42, "owner/repo")

    def test_issue_cursor_not_marked_on_failure(self, tmp_path: Path) -> None:
        agent, db = _make_agent(tmp_path, output="no json block here")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event(issue_number=42)))
        conn = eventlog.connect(db)
        assert not eventlog.issue_cursor_is_triaged(conn, 42, "owner/repo")


# ---------------------------------------------------------------------------
# Comment posting (T012)
# ---------------------------------------------------------------------------


class TestCommentPosting:
    def test_successful_comment_emits_gh_comment_posted(
        self, tmp_path: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(["issue", "comment"], returncode=0)
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "gh.comment.posted" for e in events)

    def test_failed_comment_emits_gh_comment_failed_but_run_completes(
        self, tmp_path: Path, fake_gh: Any
    ) -> None:
        fake_gh.queue(["issue", "comment"], returncode=1, stderr="not found")
        agent, db = _make_agent(tmp_path, output=f"```json\n{_VALID_TRIAGE_JSON}\n```")
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        kinds = [e.kind for e in events]
        assert "gh.comment.failed" in kinds
        assert "run.completed" in kinds


# ---------------------------------------------------------------------------
# Phone notifications (T014)
# ---------------------------------------------------------------------------


class _RecordingNotifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(
        self,
        *,
        level: str,
        title: str,
        body: str,
        click_url: str | None = None,
    ) -> None:
        self.calls.append({"level": level, "title": title, "body": body})

    async def aclose(self) -> None:
        pass


class TestNotifications:
    def test_run_start_sends_info_notification(self, tmp_path: Path) -> None:
        notifier = _RecordingNotifier()
        agent, _ = _make_agent(
            tmp_path,
            output=f"```json\n{_VALID_TRIAGE_JSON}\n```",
            notifier=notifier,
        )
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        assert any(c["level"] == "info" and "42" in c["title"] for c in notifier.calls)

    def test_triage_complete_sends_info_notification(self, tmp_path: Path) -> None:
        notifier = _RecordingNotifier()
        agent, _ = _make_agent(
            tmp_path,
            output=f"```json\n{_VALID_TRIAGE_JSON}\n```",
            notifier=notifier,
        )
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        completion_notifs = [c for c in notifier.calls if "bug" in c.get("body", "") or "bug" in c.get("title", "")]
        assert len(completion_notifs) >= 1

    def test_failed_triage_sends_error_notification(self, tmp_path: Path) -> None:
        notifier = _RecordingNotifier()
        agent, _ = _make_agent(tmp_path, fail=True, notifier=notifier)
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        assert any(c["level"] == "error" for c in notifier.calls)

    def test_notifier_exception_does_not_abort_run(self, tmp_path: Path) -> None:
        class _CrashingNotifier:
            async def send(self, **_: object) -> None:
                raise RuntimeError("notifier down")
            async def aclose(self) -> None:
                pass

        agent, db = _make_agent(
            tmp_path,
            output=f"```json\n{_VALID_TRIAGE_JSON}\n```",
            notifier=_CrashingNotifier(),
        )
        asyncio.get_event_loop().run_until_complete(agent.run(_make_issue_event()))
        conn = eventlog.connect(db)
        events = eventlog.tail_since(conn, 0)
        assert any(e.kind == "run.completed" for e in events)
