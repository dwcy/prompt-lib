"""Unit tests for ``orchestrator.notifier`` (T027).

Covers the pure level → priority + tags mapping, the 200-char title cap, and
the 1024-char body truncation marker. No real HTTP — every test injects an
``httpx.AsyncClient`` backed by ``httpx.MockTransport`` so request shaping is
observed directly without a network round-trip.

Implementation guidance for T028
--------------------------------

Same constructor as the contract test::

    Notifier(
        *,
        topic: str,
        base_url: str = "https://ntfy.sh",
        eventlog_conn: sqlite3.Connection,
        http_client: httpx.AsyncClient | None = None,
    )

Title-cap behaviour: when the caller passes a title longer than 200 chars,
the notifier MUST truncate to 200 (graceful degradation) — NOT raise. The
truncated value is what ends up in the ``Title`` header.

Body-truncation behaviour: bodies longer than 1024 chars are truncated to
exactly 1024 chars and the last char is the single Unicode ellipsis ``…``.
Bodies at or below 1024 chars pass through unchanged.

If the architect exposes pure helpers ``_level_to_priority(level) -> str``
and ``_level_to_tag(level) -> str`` they can be re-pointed here later; for
now we exercise the public surface to remain resilient to internal
factoring.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx

from orchestrator import eventlog
from orchestrator.notifier import Notifier

TOPIC = "orchestrator-test-topic"
BASE = "https://ntfy.sh"


def _bootstrap(db_path: Path) -> sqlite3.Connection:
    eventlog.bootstrap(db_path)
    return eventlog.connect(db_path)


def _capture_client(captured: list[httpx.Request]) -> httpx.AsyncClient:
    """Return an AsyncClient that records every outgoing request and replies 200."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _send(
    db_path: Path,
    *,
    level: str,
    title: str = "t",
    body: str = "b",
    click_url: str | None = None,
) -> httpx.Request:
    captured: list[httpx.Request] = []
    client = _capture_client(captured)
    conn = _bootstrap(db_path)
    try:
        notifier = Notifier(
            topic=TOPIC,
            base_url=BASE,
            eventlog_conn=conn,
            http_client=client,
        )
        await notifier.send(level=level, title=title, body=body, click_url=click_url)  # type: ignore[arg-type]
    finally:
        conn.close()
        await client.aclose()

    assert len(captured) == 1
    return captured[0]


# ---------------------------------------------------------------------------
# Level → Priority
# ---------------------------------------------------------------------------


class TestLevelToPriority:
    async def test_level_to_priority_info_is_3(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="info")

        assert request.headers["Priority"] == "3"

    async def test_level_to_priority_warn_is_4(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="warn")

        assert request.headers["Priority"] == "4"

    async def test_level_to_priority_error_is_5(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="error")

        assert request.headers["Priority"] == "5"

    async def test_level_to_priority_needs_input_is_5(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="needs_input")

        assert request.headers["Priority"] == "5"


# ---------------------------------------------------------------------------
# Level → Tag
# ---------------------------------------------------------------------------


class TestLevelToTag:
    async def test_level_to_tag_info_is_blue(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="info")

        assert request.headers["Tags"] == "🔵"

    async def test_level_to_tag_warn_is_warning(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="warn")

        assert request.headers["Tags"] == "⚠️"

    async def test_level_to_tag_error_is_stop(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="error")

        assert request.headers["Tags"] == "🛑"

    async def test_level_to_tag_needs_input_is_question(self, tmp_db: Path) -> None:
        request = await _send(tmp_db, level="needs_input")

        assert request.headers["Tags"] == "❓"


# ---------------------------------------------------------------------------
# Title / body length handling
# ---------------------------------------------------------------------------


class TestLengthCaps:
    async def test_title_capped_at_200_chars(self, tmp_db: Path) -> None:
        long_title = "x" * 300

        request = await _send(tmp_db, level="info", title=long_title)

        assert len(request.headers["Title"]) == 200

    async def test_body_truncated_at_1024_chars_with_ellipsis_marker(
        self, tmp_db: Path
    ) -> None:
        long_body = "a" * 2000

        request = await _send(tmp_db, level="info", body=long_body)

        sent = request.content.decode("utf-8")
        assert len(sent) == 1024
        assert sent[-1] == "…"

    async def test_body_below_1024_chars_passed_unchanged(self, tmp_db: Path) -> None:
        body = "a" * 500

        request = await _send(tmp_db, level="info", body=body)

        assert request.content.decode("utf-8") == body
