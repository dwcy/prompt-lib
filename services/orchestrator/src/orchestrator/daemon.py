"""Daemon entry point (T020).

Wires the trigger, agent, and delegation client together. Bounded concurrency
caps in-flight runs at 3. Signal handling drains in-flight tasks for up to 5
seconds before cancelling and shutting down.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sqlite3
import sys
from typing import TYPE_CHECKING

from a2a_bridge.client.delegation import DelegationClient

from orchestrator import eventlog
from orchestrator.agents.pr_review import PrReviewAgent
from orchestrator.config import Config
from orchestrator.notifier import Notifier
from orchestrator.triggers.github_poll import GithubPollTrigger
from orchestrator.worktree import WorktreeManager

if TYPE_CHECKING:
    from collections.abc import Iterable

_logger = logging.getLogger(__name__)

_MAX_CONCURRENT_RUNS = 3
_SHUTDOWN_GRACE_SECONDS = 5.0
_PRUNE_INTERVAL_SECONDS = 3600.0


async def serve(config: Config) -> None:
    """Run the orchestrator daemon until a shutdown signal is received."""
    eventlog.bootstrap(config.orchestrator_db_path)
    conn = eventlog.connect(config.orchestrator_db_path)

    marker_path = config.orchestrator_db_path.parent / "shutdown.marker"
    marker_ts = eventlog.read_shutdown_marker(marker_path)
    last_id_before_recovery = _max_event_id(conn)
    recovered = 0
    if marker_ts is not None:
        recovered = eventlog.recover_orphans(conn, marker_ts)
        if recovered > 0:
            print(
                f"[orchestrator] recovered {recovered} orphaned run(s) "
                "from previous shutdown",
                flush=True,
            )

    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    in_flight: set[asyncio.Task[None]] = set()
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RUNS)

    client = DelegationClient(
        peer_url=config.a2a_peer_url,
        peer_bearer_token=config.a2a_bearer_token,
    )

    notifier = Notifier(
        topic=config.orchestrator_ntfy_topic,
        base_url=config.orchestrator_ntfy_base,
        eventlog_conn=conn,
    )
    if recovered > 0:
        await _notify_orphans(conn, last_id_before_recovery, notifier)
    trigger = GithubPollTrigger(
        repo=config.orchestrator_repo,
        poll_seconds=float(config.orchestrator_poll_seconds),
        eventlog_conn=conn,
        notifier=notifier,
    )
    worktree_manager: WorktreeManager | None = None
    if config.orchestrator_worktree_enabled:
        repo_slug = config.orchestrator_repo.replace("/", "-")
        worktree_manager = WorktreeManager(
            repo_path=config.orchestrator_repo_path,
            root=config.orchestrator_worktree_root / repo_slug,
            conn=conn,
        )
        await worktree_manager.reconcile()
        await worktree_manager.prune(
            max_count=config.orchestrator_worktree_max_count,
            max_age_days=config.orchestrator_worktree_max_age_days,
        )
    agent = PrReviewAgent(
        delegation_client=client,
        eventlog_conn=conn,
        notifier=notifier,
        worktree_manager=worktree_manager,
    )

    try:
        events_iter = trigger.events()
        consume_task = asyncio.create_task(
            _consume(events_iter, agent, semaphore, in_flight, stop_event)
        )
        prune_task: asyncio.Task[None] | None = None
        if worktree_manager is not None:
            prune_task = asyncio.create_task(
                _prune_loop(worktree_manager, config, stop_event)
            )

        await stop_event.wait()
        consume_task.cancel()
        if prune_task is not None:
            prune_task.cancel()
        background_tasks: tuple[asyncio.Task[None], ...] = (
            (consume_task, prune_task) if prune_task is not None else (consume_task,)
        )
        for pending_task in background_tasks:
            try:
                await pending_task
            except (asyncio.CancelledError, Exception):
                pass

        await trigger.aclose()

        if in_flight:
            done, pending = await asyncio.wait(
                in_flight, timeout=_SHUTDOWN_GRACE_SECONDS
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            del done
    finally:
        await notifier.aclose()
        eventlog.write_shutdown_marker(marker_path)
        conn.close()


def _max_event_id(conn: sqlite3.Connection) -> int:
    """Return the maximum ``id`` currently in the events table (0 if empty)."""
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()
    return int(row[0])


async def _notify_orphans(
    conn: sqlite3.Connection,
    last_id_before: int,
    notifier: Notifier,
) -> None:
    """Push one ``warn`` notification per ``run.orphaned`` event written after
    ``last_id_before`` (data-model.md notification matrix).

    Each ``notifier.send`` call is wrapped in try/except so a notifier bug
    cannot abort daemon startup (FR-009 push-must-not-abort policy).
    """
    new_events = eventlog.tail_since(conn, last_id=last_id_before)
    runs = {r.run_id: r for r in eventlog.runs_summary(conn)}
    for ev in new_events:
        if ev.kind != "run.orphaned":
            continue
        run = runs.get(ev.run_id)
        if run is None or run.pr_number is None:
            continue
        try:
            await notifier.send(
                level="warn",
                title=f"Orphaned run for PR #{run.pr_number}",
                body="Daemon restart left a run mid-flight",
            )
        except Exception:
            _logger.exception("orphan-notify failed for run %s", ev.run_id)


async def _prune_loop(
    manager: WorktreeManager,
    config: Config,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_PRUNE_INTERVAL_SECONDS)
        except TimeoutError:
            try:
                await manager.prune(
                    max_count=config.orchestrator_worktree_max_count,
                    max_age_days=config.orchestrator_worktree_max_age_days,
                )
            except Exception:
                continue


async def _consume(
    events: object,
    agent: PrReviewAgent,
    semaphore: asyncio.Semaphore,
    in_flight: set[asyncio.Task[None]],
    stop_event: asyncio.Event,
) -> None:
    async for trigger_event in events:  # type: ignore[attr-defined]
        if stop_event.is_set():
            break
        task = asyncio.create_task(_run_one(agent, trigger_event, semaphore))
        in_flight.add(task)
        task.add_done_callback(in_flight.discard)


async def _run_one(
    agent: PrReviewAgent,
    trigger_event: object,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        await agent.run(trigger_event)  # type: ignore[arg-type]


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_event_loop()
    handled: Iterable[int] = (signal.SIGINT, signal.SIGTERM)

    if sys.platform == "win32":
        for sig in handled:
            try:
                signal.signal(sig, lambda *_: stop_event.set())
            except (OSError, ValueError):
                pass
        return

    for sig in handled:
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(sig, lambda *_: stop_event.set())
            except (OSError, ValueError):
                pass
