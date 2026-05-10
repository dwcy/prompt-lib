"""ntfy.sh push notifier (T028).

Implements the outbound POST contract documented in
``specs/002-agent-orchestrator/contracts/ntfy-publish.contract.md``:

* ``POST <base_url>/<topic>`` with UTF-8 plain-text body, locked
  ``Priority`` / ``Tags`` mapping per notification level, optional ``Click``
  header, capped 200-char ``Title`` and 1024-char body (truncated with a
  trailing single-character Unicode ellipsis ``…``).
* All HTTP errors and network exceptions are non-fatal — the notifier
  swallows them, appends a single ``push.failed`` event to the SQLite event
  log via :func:`orchestrator.eventlog.append_event`, and returns. Per
  FR-009 push-notification failures MUST NOT abort the underlying run.
* The Notifier reads ``topic`` and ``base_url`` from its constructor only —
  config is the env-reading layer (``orchestrator.config.Config``).
"""

from __future__ import annotations

import sqlite3
from importlib import metadata
from typing import Literal

import httpx

from orchestrator import eventlog

NotificationLevel = Literal["info", "warn", "error", "needs_input"]

_TITLE_MAX = 200
_BODY_MAX = 1024
_ELLIPSIS = "…"
_HTTP_TIMEOUT_SECONDS = 5.0
_FALLBACK_VERSION = "0.1.0"

_PRIORITY_BY_LEVEL: dict[NotificationLevel, str] = {
    "info": "3",
    "warn": "4",
    "error": "5",
    "needs_input": "5",
}

_TAG_BY_LEVEL: dict[NotificationLevel, str] = {
    "info": "\U0001f535",
    "warn": "⚠️",
    "error": "\U0001f6d1",
    "needs_input": "❓",
}


def _level_to_priority(level: NotificationLevel) -> str:
    """Map a notification level to its locked ntfy ``Priority`` header value."""
    return _PRIORITY_BY_LEVEL[level]


def _level_to_tag(level: NotificationLevel) -> str:
    """Map a notification level to its locked ntfy ``Tags`` header value."""
    return _TAG_BY_LEVEL[level]


def _truncate_title(title: str) -> str:
    """Cap title at 200 chars; do not raise on overflow (graceful degradation)."""
    if len(title) <= _TITLE_MAX:
        return title
    return title[:_TITLE_MAX]


def _truncate_body(body: str) -> str:
    """Cap body at 1024 chars total; replace the last char with ``…`` on overflow."""
    if len(body) <= _BODY_MAX:
        return body
    return body[: _BODY_MAX - 1] + _ELLIPSIS


def _resolve_version() -> str:
    try:
        return metadata.version("orchestrator")
    except metadata.PackageNotFoundError:
        return _FALLBACK_VERSION


_USER_AGENT = f"orchestrator/{_resolve_version()}"


class Notifier:
    """Async ntfy.sh publisher.

    The notifier owns its ``httpx.AsyncClient`` unless one is injected (for
    tests). Call :meth:`aclose` to clean up the owned client; injected
    clients are left alone.
    """

    def __init__(
        self,
        *,
        topic: str,
        base_url: str = "https://ntfy.sh",
        eventlog_conn: sqlite3.Connection,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._topic = topic
        self._base_url = base_url.rstrip("/")
        self._conn = eventlog_conn

        if http_client is None:
            self._http = httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS)
            self._owns_http = True
        else:
            self._http = http_client
            self._owns_http = False

    async def send(
        self,
        level: NotificationLevel,
        title: str,
        body: str,
        *,
        click_url: str | None = None,
    ) -> None:
        """POST one notification to ntfy. Never raises on transport errors."""
        url = f"{self._base_url}/{self._topic}"
        raw_headers: list[tuple[bytes, bytes]] = [
            (b"Content-Type", b"text/plain; charset=utf-8"),
            (b"Title", _truncate_title(title).encode("utf-8")),
            (b"Priority", _level_to_priority(level).encode("utf-8")),
            (b"Tags", _level_to_tag(level).encode("utf-8")),
            (b"User-Agent", _USER_AGENT.encode("utf-8")),
        ]
        if click_url is not None:
            raw_headers.append((b"Click", click_url.encode("utf-8")))

        payload = _truncate_body(body).encode("utf-8")

        try:
            response = await self._http.post(url, content=payload, headers=raw_headers)
        except httpx.HTTPError as exc:
            self._record_network_failure(exc)
            return

        if response.status_code >= 400:
            self._record_http_failure(response)

    async def aclose(self) -> None:
        """Close the owned ``httpx.AsyncClient``; no-op if a client was injected."""
        if self._owns_http:
            await self._http.aclose()

    def _record_http_failure(self, response: httpx.Response) -> None:
        try:
            detail_text = response.text
        except Exception:
            detail_text = ""
        eventlog.append_event(
            self._conn,
            run_id="",
            kind="push.failed",
            level="warn",
            payload={
                "topic": self._topic,
                "status_code": response.status_code,
                "detail": detail_text[:200],
            },
        )
        self._conn.commit()

    def _record_network_failure(self, exc: httpx.HTTPError) -> None:
        eventlog.append_event(
            self._conn,
            run_id="",
            kind="push.failed",
            level="warn",
            payload={
                "topic": self._topic,
                "error": type(exc).__name__,
            },
        )
        self._conn.commit()
