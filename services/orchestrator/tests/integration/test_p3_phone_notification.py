"""Integration test — Phase 5 / US3 phone-notification acceptance scenarios (T030).

Self-contained — uses ``pytest-httpx``'s ``httpx_mock`` to capture ntfy POSTs
in-process, ``FakeDelegationClient`` (from conftest) for the agent stream,
and ``fake_gh`` (from conftest) to stand in for ``gh pr diff`` / ``gh pr
review``. No real A2A bridge subprocess, no real ntfy server, no real ``gh``,
no real network.

Design deviation
----------------

The original brief in ``tasks.md`` allowed gating this test on ``INTEGRATION=1``.
We ship without the gate because the in-process realization covers the same
acceptance scenarios at lower cost and faster signal: each test is a sub-second
end-to-end through the agent's notify hooks, the eventlog, the notifier, and
the (mocked) HTTP transport. The phone-handset side of the loop (real ntfy
server, real subscriber) is exercised manually per ``quickstart.md``.

Acceptance scenarios mapped to test methods (see ``spec.md`` US3):

* Scenario 1 → ``test_run_started_PushesInfoLevelStartNotification`` and
  ``test_run_started_NotificationBodyContainsHeadShaPrefix``.
* Scenario 2 → ``test_run_completed_PushesInfoLevelCompleteNotification`` and
  ``test_run_completed_NotificationClickHeaderIsArtifactUrl``.
* Scenario 3 → ``test_run_failed_PushesErrorLevelFailNotification`` and
  ``test_run_failed_DoesNotPostReviewComment``.
* Scenario 4 → ``test_ntfyUnreachable_RunStillCompletes`` and
  ``test_ntfyUnreachable_RecordsPushFailedEvent``.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from orchestrator import eventlog
from orchestrator.agents.pr_review import PrReviewAgent
from orchestrator.notifier import Notifier
from orchestrator.triggers.base import TriggerEvent

TOPIC = "orchestrator-test-topic"
NTFY_BASE = "https://ntfy.sh"
NTFY_URL = f"{NTFY_BASE}/{TOPIC}"

REPO = "octo/widgets"
PR_NUMBER = 42
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
PR_URL = f"https://github.com/{REPO}/pull/{PR_NUMBER}"
REVIEW_URL = f"{PR_URL}#pullrequestreview-7"
DIFF_TEXT = "diff --git a/file.py b/file.py\n+added line\n"


def _trigger_event() -> TriggerEvent:
    return TriggerEvent(
        kind="pr.opened",
        repo=REPO,
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        detected_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
        payload={
            "title": "Add the thing",
            "url": PR_URL,
            "headRefName": "feature/the-thing",
            "baseRefName": "main",
            "author_login": "octocat",
        },
    )


def _bootstrap(db_path: Path) -> sqlite3.Connection:
    eventlog.bootstrap(db_path)
    return eventlog.connect(db_path)


def _events(db_path: Path) -> list[dict[str, Any]]:
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


def _kinds(db_path: Path) -> list[str]:
    return [e["kind"] for e in _events(db_path)]


def _prime_diff(fake_gh: Any) -> None:
    fake_gh.queue(["pr", "diff"], stdout=DIFF_TEXT)


def _prime_review_post(fake_gh: Any, *, url: str = REVIEW_URL) -> None:
    fake_gh.queue(["pr", "review"], stdout=url + "\n")


def _count_argv_in_remaining(fake_gh: Any, argv_prefix: list[str]) -> int:
    data = json.loads(fake_gh.behavior_file.read_text(encoding="utf-8"))
    return sum(
        1
        for rule in data.get("rules", [])
        if rule.get("argv_match", [])[: len(argv_prefix)] == argv_prefix
    )


def _success_event_stream() -> list[dict[str, Any]]:
    return [
        {"event": "state", "data": {"state": "submitted"}},
        {"event": "message", "data": {"text": "Looks good. Ship it.", "partial": False}},
        {"event": "state", "data": {"state": "completed"}},
    ]


def _failed_event_stream(reason: str = "peer crashed mid-stream") -> list[dict[str, Any]]:
    return [
        {"event": "state", "data": {"state": "submitted"}},
        {"event": "state", "data": {"state": "failed", "reason": reason}},
    ]


def _posts_to_ntfy(httpx_mock: Any) -> list[httpx.Request]:
    return [r for r in httpx_mock.get_requests() if str(r.url) == NTFY_URL]


# ---------------------------------------------------------------------------
# Scenario 1 — run start → info-level push notification
# ---------------------------------------------------------------------------


class TestScenario1RunStartNotification:
    async def test_run_started_PushesInfoLevelStartNotification(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        start_pushes = [
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].startswith(f"Reviewing PR #{PR_NUMBER}")
        ]

        assert len(start_pushes) == 1
        assert start_pushes[0].headers["Priority"] == "3"

    async def test_run_started_NotificationBodyContainsHeadShaPrefix(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        start_push = next(
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].startswith(f"Reviewing PR #{PR_NUMBER}")
        )

        assert HEAD_SHA[:7] in start_push.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Scenario 2 — run complete → info-level push with click URL
# ---------------------------------------------------------------------------


class TestScenario2RunCompleteNotification:
    async def test_run_completed_PushesInfoLevelCompleteNotification(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        complete_pushes = [
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].startswith(f"Review posted on PR #{PR_NUMBER}")
        ]

        assert len(complete_pushes) == 1
        assert complete_pushes[0].headers["Priority"] == "3"

    async def test_run_completed_NotificationClickHeaderIsArtifactUrl(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        posted = [e for e in _events(tmp_db) if e["kind"] == "gh.review.posted"]
        assert len(posted) == 1
        artifact_url = posted[0]["payload"]["artifact_url"]

        complete_push = next(
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].startswith(f"Review posted on PR #{PR_NUMBER}")
        )

        assert complete_push.headers["Click"] == artifact_url


# ---------------------------------------------------------------------------
# Scenario 3 — run fail → error-level push, no PR comment
# ---------------------------------------------------------------------------


class TestScenario3RunFailureNotification:
    async def test_run_failed_PushesErrorLevelFailNotification(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        client = fake_delegation_client(_failed_event_stream("peer crashed"))

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        fail_pushes = [
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].startswith(f"PR #{PR_NUMBER}")
            and r.headers["Title"].endswith("review FAILED")
        ]

        assert len(fail_pushes) == 1
        assert fail_pushes[0].headers["Priority"] == "5"

    async def test_run_failed_NotificationBodyTruncatedToNotifLimit(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        long_reason = "x" * 500
        client = fake_delegation_client(_failed_event_stream(long_reason))

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        fail_push = next(
            r
            for r in _posts_to_ntfy(httpx_mock)
            if r.headers["Title"].endswith("review FAILED")
        )

        assert len(fail_push.content.decode("utf-8")) <= 120

    async def test_run_failed_DoesNotPostReviewComment(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_response(status_code=200, is_reusable=True)
        _prime_diff(fake_gh)
        client = fake_delegation_client(_failed_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        assert "gh.review.posted" not in _kinds(tmp_db)
        assert _count_argv_in_remaining(fake_gh, ["pr", "review"]) == 0


# ---------------------------------------------------------------------------
# Scenario 4 — ntfy unreachable → run still completes, push.failed recorded
# ---------------------------------------------------------------------------


class TestScenario4NtfyUnreachable:
    async def test_ntfyUnreachable_RunStillCompletes(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("ntfy down"), is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        kinds = _kinds(tmp_db)

        assert "run.completed" in kinds
        assert "gh.review.posted" in kinds
        assert _count_argv_in_remaining(fake_gh, ["pr", "review"]) == 0

    async def test_ntfyUnreachable_RecordsPushFailedEvent(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
        httpx_mock: Any,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("ntfy down"), is_reusable=True)
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)
        client = fake_delegation_client(_success_event_stream())

        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=NTFY_BASE, eventlog_conn=conn)
            agent = PrReviewAgent(
                delegation_client=client,
                eventlog_conn=conn,
                notifier=notifier,
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        push_failed = [e for e in _events(tmp_db) if e["kind"] == "push.failed"]

        assert len(push_failed) >= 1
