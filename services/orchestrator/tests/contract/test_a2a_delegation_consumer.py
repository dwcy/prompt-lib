"""Contract test for the A2A delegation consumer (T015).

Pins the consumer-side event-stream handling documented in
``specs/002-agent-orchestrator/contracts/a2a-delegation.contract.md``: success
sequence, partial-message concatenation, terminal-state semantics, unknown-kind
forwarding, exception → ``run.failed`` mapping with payload truncation, and
the ``NO_REVIEW:`` sentinel → ``run.skipped`` short-circuit.

Implementation guidance for T019
--------------------------------

These tests assume a single consumer class::

    from orchestrator.agents.pr_review import PrReviewAgent

with the constructor signature::

    PrReviewAgent(
        delegation_client,    # async-context-managed; .delegate(prompt) yields events
        eventlog_conn,        # bootstrapped sqlite3.Connection
    )

and the entry point::

    async def run(self, trigger_event: TriggerEvent) -> None: ...

Per the contract, ``run`` performs roughly:

1. Run ``gh pr diff <pr_number> --repo <repo>`` to capture the diff.
2. Build the prompt described in the contract document and call
   ``delegation_client.delegate(prompt)``.
3. Consume the SSE event stream:

   * ``state`` events → ``agent.state`` events in the log.
   * ``message`` events → append ``text`` to a running buffer; emit
     ``agent.message`` events.
   * Any other event kind → ``agent.<kind>`` event with the raw payload.

4. On terminal ``state="completed"``:
   * If the buffer starts with ``NO_REVIEW:`` (single-line response), emit
     ``run.skipped`` with ``reason="agent_declined"`` and SKIP the post.
   * Otherwise, post the buffer via ``gh pr review <n> --repo <repo>
     --comment -F -`` (stdin), capture the resulting URL into a
     ``gh.review.posted`` event, and emit ``run.completed``.
5. On terminal ``state="failed"``: emit ``run.failed`` with
   ``stage="delegate"`` and the payload's reason; SKIP the post.
6. On terminal ``state="cancelled"``: emit ``run.failed`` with
   ``error="cancelled by peer"``; SKIP the post.
7. If ``delegate()`` raises: emit ``run.failed`` with ``stage="delegate"``
   and the exception message truncated to 200 chars.

Test conventions
----------------

Every test that exercises a successful delegation path MUST queue a
``gh pr diff`` rule on ``fake_gh`` BEFORE the agent runs — the agent calls
``gh pr diff <n>`` to capture the diff input for the prompt. We also queue a
``gh pr review`` rule for the post-back step in tests that exercise it.

All tests construct a ``TriggerEvent`` via ``orchestrator.triggers.base`` so
the wiring matches what the trigger-side test exercises.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orchestrator import eventlog
from orchestrator.agents.pr_review import PrReviewAgent
from orchestrator.triggers.base import TriggerEvent

REPO = "owner/repo"
PR_NUMBER = 42
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
DIFF_TEXT = "diff --git a/file.py b/file.py\n+added line\n"
REVIEW_URL = "https://github.com/owner/repo/pull/42#pullrequestreview-1"


def _trigger_event() -> TriggerEvent:
    return TriggerEvent(
        kind="pr.opened",
        repo=REPO,
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        detected_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC),
        payload={
            "title": "Add the thing",
            "url": "https://github.com/owner/repo/pull/42",
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


def _prime_review_post(fake_gh: Any) -> None:
    fake_gh.queue(["pr", "review"], stdout=REVIEW_URL + "\n")


def _count_argv_in_remaining(fake_gh: Any, argv_prefix: list[str]) -> int:
    """How many queued rules remain whose argv_match starts with ``argv_prefix``?"""
    data = json.loads(fake_gh.behavior_file.read_text(encoding="utf-8"))
    return sum(
        1
        for rule in data.get("rules", [])
        if rule.get("argv_match", [])[: len(argv_prefix)] == argv_prefix
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSuccessfulDelegation:
    async def test_consumer_handles_minimal_success_sequence(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "message", "data": {"text": "Looks good. Ship it.", "partial": False}},
                {"event": "state", "data": {"state": "completed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        kinds = _kinds(tmp_db)
        assert "run.started" in kinds
        # Order: run.started precedes the first agent.state.
        assert kinds.index("run.started") < kinds.index("agent.state")
        # agent.message recorded.
        assert "agent.message" in kinds
        # gh.review.posted recorded after agent activity, before run.completed.
        assert kinds.index("gh.review.posted") < kinds.index("run.completed")

    async def test_consumer_handles_real_bridge_sse_event_names(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)

        client = fake_delegation_client(
            [
                {
                    "event": "task.state",
                    "data": {"task_id": "t1", "state": "submitted", "ts": "t"},
                },
                {
                    "event": "task.artifact",
                    "data": {
                        "task_id": "t1",
                        "artifact": {
                            "id": "a1",
                            "kind": "text",
                            "mime_type": "text/plain",
                            "content": "Real bridge review.",
                        },
                    },
                },
                {
                    "event": "task.state",
                    "data": {"task_id": "t1", "state": "completed", "ts": "t"},
                },
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        kinds = _kinds(tmp_db)
        assert "agent.message" in kinds
        assert "gh.review.posted" in kinds
        assert "run.completed" in kinds

    async def test_consumer_concatenates_partial_message_chunks(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "message", "data": {"text": "Part one. ", "partial": True}},
                {"event": "message", "data": {"text": "Part two. ", "partial": True}},
                {"event": "message", "data": {"text": "Part three.", "partial": False}},
                {"event": "state", "data": {"state": "completed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        # The posted review text is the concatenated buffer.
        posted = [e for e in _events(tmp_db) if e["kind"] == "gh.review.posted"]
        assert len(posted) == 1
        comment_length = posted[0]["payload"].get("comment_length")
        assert comment_length == len("Part one. Part two. Part three.")

    async def test_consumer_emits_agent_state_for_each_state_event(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "state", "data": {"state": "working"}},
                {"event": "state", "data": {"state": "working"}},
                {"event": "message", "data": {"text": "ok", "partial": False}},
                {"event": "state", "data": {"state": "completed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        states = [
            e["payload"].get("state")
            for e in _events(tmp_db)
            if e["kind"] == "agent.state"
        ]
        # The terminal "completed" is consumed as the run-complete signal and
        # may or may not also be re-emitted as agent.state — at minimum the
        # three pre-terminal states must be present.
        assert states[:3] == ["submitted", "working", "working"]


# ---------------------------------------------------------------------------
# Terminal failure / cancellation
# ---------------------------------------------------------------------------


class TestTerminalFailureStates:
    async def test_consumer_treats_failed_state_as_terminal(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "state", "data": {"state": "failed", "reason": "peer crashed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        run_failed = [e for e in _events(tmp_db) if e["kind"] == "run.failed"]
        assert len(run_failed) == 1
        assert run_failed[0]["payload"].get("stage") == "delegate"

        # No gh pr review invocation ever happened.
        assert _count_argv_in_remaining(fake_gh, ["pr", "review"]) == 0

    async def test_consumer_treats_cancelled_state_as_terminal(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "state", "data": {"state": "cancelled"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        run_failed = [e for e in _events(tmp_db) if e["kind"] == "run.failed"]
        assert len(run_failed) == 1
        assert "cancelled by peer" in (run_failed[0]["payload"].get("error") or "")

    async def test_consumer_does_not_post_when_terminal_state_is_failed(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        # No review post primed — and we'll assert nothing tried to post.

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "state", "data": {"state": "failed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        assert "gh.review.posted" not in _kinds(tmp_db)

    async def test_consumer_does_not_post_when_terminal_state_is_cancelled(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "state", "data": {"state": "cancelled"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        assert "gh.review.posted" not in _kinds(tmp_db)


# ---------------------------------------------------------------------------
# Unknown kinds + delegate exceptions
# ---------------------------------------------------------------------------


class TestExtensibilityAndExceptions:
    async def test_consumer_propagates_unknown_event_kinds_with_agent_prefix(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        _prime_review_post(fake_gh)

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "tool_use", "data": {"name": "grep", "input": {"pattern": "TODO"}}},
                {"event": "message", "data": {"text": "review", "partial": False}},
                {"event": "state", "data": {"state": "completed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        tool_uses = [e for e in _events(tmp_db) if e["kind"] == "agent.tool_use"]
        assert len(tool_uses) == 1
        assert tool_uses[0]["payload"].get("name") == "grep"

    async def test_consumer_emits_run_failed_when_delegate_raises(
        self,
        tmp_db: Path,
        fake_gh: Any,
    ) -> None:
        _prime_diff(fake_gh)

        class RaisingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def delegate(self, prompt: str, *, cwd: str | None = None):
                raise ConnectionError("peer down")
                yield  # pragma: no cover — make this an async generator

        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=RaisingClient(), eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        run_failed = [e for e in _events(tmp_db) if e["kind"] == "run.failed"]
        assert len(run_failed) == 1
        payload = run_failed[0]["payload"]
        assert payload.get("stage") == "delegate"
        assert "peer down" in (payload.get("error") or "")

    async def test_consumer_truncates_exception_message_in_failure_payload(
        self,
        tmp_db: Path,
        fake_gh: Any,
    ) -> None:
        _prime_diff(fake_gh)
        long_message = "x" * 500

        class LongRaisingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def delegate(self, prompt: str, *, cwd: str | None = None):
                raise RuntimeError(long_message)
                yield  # pragma: no cover

        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(
                delegation_client=LongRaisingClient(), eventlog_conn=conn
            )
            await agent.run(_trigger_event())
        finally:
            conn.close()

        run_failed = [e for e in _events(tmp_db) if e["kind"] == "run.failed"]
        assert len(run_failed) == 1
        error_text = run_failed[0]["payload"].get("error") or ""
        assert len(error_text) == 200


# ---------------------------------------------------------------------------
# NO_REVIEW sentinel
# ---------------------------------------------------------------------------


class TestNoReviewSentinel:
    async def test_consumer_handles_no_review_sentinel_as_skipped(
        self,
        tmp_db: Path,
        fake_gh: Any,
        fake_delegation_client: Any,
    ) -> None:
        _prime_diff(fake_gh)
        # Do NOT prime a review post — the agent must not invoke it.

        client = fake_delegation_client(
            [
                {"event": "state", "data": {"state": "submitted"}},
                {"event": "message", "data": {"text": "NO_REVIEW: binary diff", "partial": False}},
                {"event": "state", "data": {"state": "completed"}},
            ]
        )
        conn = _bootstrap(tmp_db)
        try:
            agent = PrReviewAgent(delegation_client=client, eventlog_conn=conn)
            await agent.run(_trigger_event())
        finally:
            conn.close()

        skipped = [e for e in _events(tmp_db) if e["kind"] == "run.skipped"]
        assert len(skipped) == 1
        assert skipped[0]["payload"].get("reason") == "agent_declined"

        assert "gh.review.posted" not in _kinds(tmp_db)
        assert _count_argv_in_remaining(fake_gh, ["pr", "review"]) == 0
