"""Contract test for ntfy.sh publish (T026).

Pins the outbound POST shape documented in
``specs/002-agent-orchestrator/contracts/ntfy-publish.contract.md``: configured
base + topic in the URL, locked level → priority/tags mapping, header surface,
UTF-8 plain-text body with 1024-char truncation marker, and the non-fatal
response-handling policy that maps 4xx / 5xx / network errors to a single
``push.failed`` event in the SQLite event log.

Implementation guidance for T028
--------------------------------

These tests assume a single class::

    from orchestrator.notifier import Notifier

with the constructor signature::

    Notifier(
        *,
        topic: str,
        base_url: str = "https://ntfy.sh",
        eventlog_conn: sqlite3.Connection,   # bootstrapped events.db connection
        http_client: httpx.AsyncClient | None = None,  # tests inject a mocked one
    )

and the single entry point::

    async def send(
        self,
        level: Literal["info", "warn", "error", "needs_input"],
        title: str,
        body: str,
        *,
        click_url: str | None = None,
    ) -> None: ...

The notifier MUST NOT raise on a non-2xx response or on a network error — it
MUST swallow the failure, append exactly one ``push.failed`` event to the log,
and return. ``push.failed`` is itself never re-pushed (FR-009).

Tests rely on ``pytest-httpx``'s ``httpx_mock`` fixture (auto-discovered from
the installed plugin) to intercept POSTs in-process — no real network calls.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import httpx

from orchestrator import eventlog
from orchestrator.notifier import Notifier

TOPIC = "orchestrator-test-topic"
DEFAULT_BASE = "https://ntfy.sh"
CUSTOM_BASE = "https://ntfy.example.com"


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


def _push_failed_events(db_path: Path) -> list[dict[str, Any]]:
    return [e for e in _events(db_path) if e["kind"] == "push.failed"]


# ---------------------------------------------------------------------------
# URL composition
# ---------------------------------------------------------------------------


class TestPostUrl:
    async def test_post_url_uses_configured_base(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=CUSTOM_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert str(request.url) == f"{CUSTOM_BASE}/{TOPIC}"

    async def test_post_url_uses_configured_topic(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.url.path == f"/{TOPIC}"


# ---------------------------------------------------------------------------
# Level → Priority + Tags (locked mapping)
# ---------------------------------------------------------------------------


class TestLevelMapping:
    async def test_info_level_sets_priority_3_and_blue_tag(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "3"
        assert request.headers["Tags"] == "🔵"

    async def test_warn_level_sets_priority_4_and_warning_tag(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="warn", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "4"
        assert request.headers["Tags"] == "⚠️"

    async def test_error_level_sets_priority_5_and_stop_tag(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="error", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "5"
        assert request.headers["Tags"] == "🛑"

    async def test_needs_input_level_sets_priority_5_and_question_tag(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="needs_input", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Priority"] == "5"
        assert request.headers["Tags"] == "❓"


# ---------------------------------------------------------------------------
# Title / Click / body / User-Agent / Content-Type
# ---------------------------------------------------------------------------


class TestHeaders:
    async def test_title_header_set_from_notification_title(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        title = "Reviewing PR #42"
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title=title, body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Title"] == title

    async def test_click_header_set_when_url_present(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        click_url = "https://github.com/foo/bar/pull/42"
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b", click_url=click_url)
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Click"] == click_url

    async def test_click_header_omitted_when_url_none(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert "Click" not in request.headers

    async def test_body_is_utf8_plain_text(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        body = "hello — world"
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body=body)
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert request.headers["Content-Type"] == "text/plain; charset=utf-8"
        assert request.content == body.encode("utf-8")

    async def test_body_truncated_at_1024_chars_with_ellipsis(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        body = "a" * 2000
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body=body)
        finally:
            conn.close()

        request = httpx_mock.get_request()
        sent = request.content.decode("utf-8")

        assert len(sent) == 1024
        assert sent.endswith("…")

    async def test_user_agent_includes_orchestrator_and_version(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=200)
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        request = httpx_mock.get_request()
        assert re.match(r"^orchestrator/\S+", request.headers["User-Agent"])


# ---------------------------------------------------------------------------
# Failure handling — non-fatal, single push.failed event
# ---------------------------------------------------------------------------


class TestFailureHandling:
    async def test_4xx_response_emits_push_failed_event_and_does_not_raise(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=403, text="forbidden")
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        failed = _push_failed_events(tmp_db)
        assert len(failed) == 1
        assert failed[0]["payload"].get("status_code") == 403

    async def test_5xx_response_emits_push_failed_event_and_does_not_raise(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_response(status_code=503, text="service unavailable")
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        failed = _push_failed_events(tmp_db)
        assert len(failed) == 1
        assert failed[0]["payload"].get("status_code") == 503

    async def test_network_timeout_emits_push_failed_event_and_does_not_raise(
        self, tmp_db: Path, httpx_mock: Any
    ) -> None:
        httpx_mock.add_exception(httpx.TimeoutException("boom"))
        conn = _bootstrap(tmp_db)
        try:
            notifier = Notifier(topic=TOPIC, base_url=DEFAULT_BASE, eventlog_conn=conn)
            await notifier.send(level="info", title="t", body="b")
        finally:
            conn.close()

        failed = _push_failed_events(tmp_db)
        assert len(failed) == 1
        assert failed[0]["payload"].get("error")
