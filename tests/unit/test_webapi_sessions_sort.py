"""Regression test: one timestamp-less session must not break the sessions sort."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from cabal.webapi.sessions_service import _sort_key


def _row(session_id: str, start_time: datetime | None) -> tuple:
    session = SimpleNamespace(session_id=session_id)
    summary = SimpleNamespace(
        start_time=start_time,
        estimated_cost_usd=0.0,
        total_input_tokens=0,
        total_output_tokens=0,
        duration_seconds=0.0,
    )
    return (session, summary)


def test_sessions_with_and_without_start_time_sort_together_without_error() -> None:
    rows = [
        _row("with-timestamp", datetime(2026, 8, 27, tzinfo=timezone.utc)),
        _row("no-timestamp", None),
    ]

    ordered = sorted(rows, key=lambda row: _sort_key(row, "started_desc"))

    assert [session.session_id for session, _summary in ordered] == [
        "no-timestamp",
        "with-timestamp",
    ]
