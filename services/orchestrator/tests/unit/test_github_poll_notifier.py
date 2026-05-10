"""Unit test for ``GithubPollTrigger`` ``auth.failed`` notification wiring.

Pins the ``data-model.md`` notification matrix entry for ``auth.failed``:
``error`` level, title ``Auth failed: gh``, body ``<detail[:160]>``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from orchestrator import eventlog
from orchestrator.triggers.github_poll import GithubPollTrigger


async def test_GithubPollTrigger_AuthFailedStderr_PushesErrorNotification(
    tmp_db: Path, fake_gh: Any
) -> None:
    fake_gh.queue(
        ["pr", "list"],
        stderr="error: not authenticated. Run gh auth login.",
        returncode=1,
    )
    eventlog.bootstrap(tmp_db)
    conn = eventlog.connect(tmp_db)
    notifier = AsyncMock()

    try:
        trigger = GithubPollTrigger(
            repo="owner/repo",
            poll_seconds=0.01,
            eventlog_conn=conn,
            notifier=notifier,
        )

        async def _run() -> None:
            async for _ in trigger.events():
                pass

        task = asyncio.create_task(_run())
        try:
            await asyncio.sleep(0.15)
        finally:
            await trigger.aclose()
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
    finally:
        conn.close()

    notifier.send.assert_called_once_with(
        level="error",
        title="Auth failed: gh",
        body="error: not authenticated. Run gh auth login.",
    )
