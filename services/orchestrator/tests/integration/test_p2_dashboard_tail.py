"""Integration test — Phase 4 / US2 dashboard acceptance scenarios (T025).

Self-contained — uses Textual's ``App.run_test()`` headless mode and writes
events directly into a fixture SQLite file owned by ``tmp_path``. There is no
``INTEGRATION=1`` gate; this runs as part of the default ``uv run pytest``
suite.

Map of test methods to spec.md User Story 2 acceptance scenarios:

* ``test_run_test_HistoricalRunsPrePopulated_RendersInRunsTable`` — Scenario 1.
* ``test_run_test_NewEventWrittenWhileRunning_AppearsWithinOneSecond`` — Scenario 2.
* ``test_run_test_NoNewWritesForSeveralTicks_DashboardKeepsRefreshing`` — Scenario 3a.
* ``test_run_test_DatabaseDeletedMidRun_StatusFooterShowsErrorThenRecovers`` — Scenario 3b.
* ``test_run_test_RelaunchedAgainstSameDb_ShowsSamePrePopulatedRuns`` — Scenario 4.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from textual.widgets import DataTable, Static

from orchestrator import eventlog
from orchestrator.config import Config
from orchestrator.dashboard import OrchestratorDash

_REPO = "test-owner/test-repo"
_REFRESH_TICK = 0.7


def _make_config(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> Config:
    """Build a real Config exercising the production env-var validators."""
    monkeypatch.setenv("ORCHESTRATOR_REPO", _REPO)
    monkeypatch.setenv("ORCHESTRATOR_NTFY_TOPIC", "test-topic-" + uuid.uuid4().hex[:8])
    monkeypatch.setenv("A2A_BEARER_TOKEN", "test-bearer-" + uuid.uuid4().hex[:8])
    monkeypatch.setenv("ORCHESTRATOR_DB_PATH", str(db_path))
    return Config()


def _seed_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    pr_number: int,
    head_sha: str,
    terminal: str | None,
    artifact_url: str | None = None,
    repo: str = _REPO,
) -> None:
    """Append a queued + started + (optional terminal) sequence for one run."""
    eventlog.append_event(
        conn,
        run_id=run_id,
        kind="run.queued",
        level="info",
        payload={
            "kind": "pr.review",
            "repo": repo,
            "pr_number": pr_number,
            "head_sha": head_sha,
        },
    )
    eventlog.append_event(
        conn,
        run_id=run_id,
        kind="run.started",
        level="info",
        payload={"pr_number": pr_number},
    )
    if terminal == "completed":
        eventlog.append_event(
            conn,
            run_id=run_id,
            kind="run.completed",
            level="info",
            payload={"artifact_url": artifact_url} if artifact_url else {},
        )
    elif terminal == "failed":
        eventlog.append_event(
            conn,
            run_id=run_id,
            kind="run.failed",
            level="error",
            payload={"stage": "delegate", "error": "peer unreachable"},
        )
    elif terminal == "skipped":
        eventlog.append_event(
            conn,
            run_id=run_id,
            kind="run.skipped",
            level="warn",
            payload={"reason": "agent_declined"},
        )
    conn.commit()


def _seed_three_completed_runs(db_path: Path) -> list[str]:
    eventlog.bootstrap(db_path)
    conn = eventlog.connect(db_path)
    try:
        run_ids = [str(uuid.uuid4()) for _ in range(3)]
        _seed_run(
            conn,
            run_id=run_ids[0],
            pr_number=101,
            head_sha="a" * 40,
            terminal="completed",
            artifact_url="https://github.com/test-owner/test-repo/pull/101#issuecomment-1",
        )
        _seed_run(
            conn,
            run_id=run_ids[1],
            pr_number=102,
            head_sha="b" * 40,
            terminal="failed",
        )
        _seed_run(
            conn,
            run_id=run_ids[2],
            pr_number=103,
            head_sha="c" * 40,
            terminal="completed",
            artifact_url="https://github.com/test-owner/test-repo/pull/103#issuecomment-2",
        )
    finally:
        conn.close()
    return run_ids


def _row_glyphs(table: DataTable) -> list[str]:
    """Collect the rendered text of column 0 (status glyph) for every row."""
    glyphs: list[str] = []
    for row_index in range(table.row_count):
        row = table.get_row_at(row_index)
        cell = row[0]
        glyphs.append(str(cell))
    return glyphs


def _row_pr_numbers(table: DataTable) -> list[str]:
    pr_cells: list[str] = []
    for row_index in range(table.row_count):
        row = table.get_row_at(row_index)
        pr_cells.append(str(row[1]))
    return pr_cells


# ---------------------------------------------------------------------------
# Scenario 1 — historical runs visible on launch
# ---------------------------------------------------------------------------


async def test_run_test_HistoricalRunsPrePopulated_RendersInRunsTable(
    tmp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_three_completed_runs(tmp_db)
    config = _make_config(monkeypatch, tmp_db)

    app = OrchestratorDash(config)
    async with app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        table = app.query_one("#runs-table", DataTable)

        assert table.row_count == 3
        glyphs = _row_glyphs(table)
        prs = _row_pr_numbers(table)

        assert prs == ["#103", "#102", "#101"]
        assert "✓" in glyphs[0]
        assert "✗" in glyphs[1]
        assert "✓" in glyphs[2]


# ---------------------------------------------------------------------------
# Scenario 2 — new event written by a background task is visible within 1 s
# ---------------------------------------------------------------------------


async def test_run_test_NewEventWrittenWhileRunning_AppearsWithinOneSecond(
    tmp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eventlog.bootstrap(tmp_db)
    config = _make_config(monkeypatch, tmp_db)

    run_id = str(uuid.uuid4())

    async def _writer() -> None:
        await asyncio.sleep(0.1)
        conn = eventlog.connect(tmp_db)
        try:
            eventlog.append_event(
                conn,
                run_id=run_id,
                kind="run.queued",
                level="info",
                payload={
                    "kind": "pr.review",
                    "repo": _REPO,
                    "pr_number": 42,
                    "head_sha": "d" * 40,
                },
            )
            eventlog.append_event(
                conn,
                run_id=run_id,
                kind="run.started",
                level="info",
                payload={"pr_number": 42},
            )
            conn.commit()
        finally:
            conn.close()

    app = OrchestratorDash(config)
    async with app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        table = app.query_one("#runs-table", DataTable)
        assert table.row_count == 0

        writer_task = asyncio.create_task(_writer())
        try:
            await pilot.pause(1.0)
        finally:
            await writer_task

        assert table.row_count == 1
        glyphs = _row_glyphs(table)
        prs = _row_pr_numbers(table)

        assert prs == ["#42"]
        assert "⟳" in glyphs[0]


# ---------------------------------------------------------------------------
# Scenario 3a — dashboard keeps refreshing when no new events arrive
# ---------------------------------------------------------------------------


async def test_run_test_NoNewWritesForSeveralTicks_DashboardKeepsRefreshing(
    tmp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_three_completed_runs(tmp_db)
    config = _make_config(monkeypatch, tmp_db)

    app = OrchestratorDash(config)
    async with app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        table = app.query_one("#runs-table", DataTable)
        initial_row_count = table.row_count
        initial_poll_count = app._poll_count

        for _ in range(4):
            await pilot.pause(_REFRESH_TICK)

        assert table.row_count == initial_row_count
        assert app._poll_count > initial_poll_count
        footer = app.query_one("#status-footer", Static)
        assert "connected" in str(footer.render())


# ---------------------------------------------------------------------------
# Scenario 3b — DB file disappearing mid-run is reported, not crashed
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows holds an exclusive lock on the open SQLite file; deletion "
    "while the dashboard's read connection is open returns PermissionError "
    "rather than the in-place sqlite3.OperationalError we want to assert.",
)
async def test_run_test_DatabaseDeletedMidRun_StatusFooterShowsErrorThenRecovers(
    tmp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_three_completed_runs(tmp_db)
    config = _make_config(monkeypatch, tmp_db)

    app = OrchestratorDash(config)
    async with app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        table = app.query_one("#runs-table", DataTable)
        assert table.row_count == 3

        tmp_db.unlink()
        for _ in range(3):
            await pilot.pause(_REFRESH_TICK)

        footer = app.query_one("#status-footer", Static)
        footer_text = str(footer.render())
        assert "waiting for daemon" in footer_text or "error:" in footer_text


# ---------------------------------------------------------------------------
# Scenario 4 — close-and-reopen preserves the historical record
# ---------------------------------------------------------------------------


async def test_run_test_RelaunchedAgainstSameDb_ShowsSamePrePopulatedRuns(
    tmp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_three_completed_runs(tmp_db)
    config = _make_config(monkeypatch, tmp_db)

    first_app = OrchestratorDash(config)
    async with first_app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        first_table = first_app.query_one("#runs-table", DataTable)
        first_pr_numbers = _row_pr_numbers(first_table)
        first_glyphs = _row_glyphs(first_table)

    second_app = OrchestratorDash(config)
    async with second_app.run_test() as pilot:
        await pilot.pause(_REFRESH_TICK)
        second_table = second_app.query_one("#runs-table", DataTable)
        second_pr_numbers = _row_pr_numbers(second_table)
        second_glyphs = _row_glyphs(second_table)

    assert second_pr_numbers == first_pr_numbers
    assert second_glyphs == first_glyphs
    assert second_pr_numbers == ["#103", "#102", "#101"]
