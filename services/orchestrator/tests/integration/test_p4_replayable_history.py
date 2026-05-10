"""Integration test — Phase 6 / US4 replayable-history acceptance scenarios (T033).

REQUIRES ``INTEGRATION=1``. Spawns real subprocesses (``a2a-bridge``, the
orchestrator daemon, the dashboard CLI) and uses ungraceful kills (POSIX
``SIGKILL`` / Windows ``taskkill /F /T``) to simulate process death without
the daemon's graceful-shutdown handler refreshing ``shutdown.marker``. Verifies
the orphan-recovery routine runs on the next start and writes the expected
``run.orphaned`` event for the in-flight run.

Map of test methods to spec.md User Story 4 acceptance scenarios:

* ``test_dashboardRelaunch_PreservesHistoricalEventRecord`` — Scenario 1
  (SC-008 — every event written before any restart is still readable after).
* ``test_daemonSigkilledMidRun_NextStartMarksRunAsOrphaned`` — Scenario 2
  (SC-007 / FR-013 — a run with ``run.started`` but no terminal event whose
  ``started_at`` predates the prior shutdown marker becomes ``run.orphaned``
  on next daemon boot).

Cross-platform notes
--------------------

* POSIX uses ``os.kill(pid, signal.SIGKILL)`` to force-terminate the daemon
  without giving its signal handlers a chance to write a fresh
  ``shutdown.marker``.
* Windows has no real ``SIGKILL``; the equivalent is
  ``taskkill /F /T /PID <pid>`` which terminates the whole process tree
  without giving the child a chance to clean up. ``Popen.kill()`` on Windows
  resolves to ``TerminateProcess`` (also non-graceful) but is per-PID, so the
  ``taskkill`` form is preferred when the spawned ``uv run …`` wrapper has
  already forked the actual daemon process.
* ``ORCHESTRATOR_REPO`` is set to a never-existed slug (``throwaway/throwaway``)
  on purpose — the polling trigger's ``gh pr list`` will surface a ``not
  found`` failure and pause the loop, but the orphan-recovery code path runs
  BEFORE the polling loop starts, so the test still observes what we care
  about.
* ``ORCHESTRATOR_REPO_PATH`` and ``ORCHESTRATOR_WORKTREE_ROOT`` are pointed at
  a throwaway ``git init`` repo so the parallel ``WorktreeManager`` reconcile
  step has a benign target.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from orchestrator import eventlog

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTEGRATION") != "1",
        reason="set INTEGRATION=1 to run live-process tests",
    ),
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]
_BRIDGE_DIR = _REPO_ROOT / "services" / "a2a-bridge"
_ORCHESTRATOR_DIR = _REPO_ROOT / "services" / "orchestrator"

_BRIDGE_HOST = "127.0.0.1"
_BRIDGE_PORT = 8765
_BRIDGE_URL = f"http://{_BRIDGE_HOST}:{_BRIDGE_PORT}"

_BRIDGE_READY_DEADLINE = 30.0
_DAEMON_BOOTSTRAP_DEADLINE = 20.0
_ORPHAN_RECOVERY_DEADLINE = 30.0

_THROWAWAY_REPO_SLUG = "throwaway/throwaway"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_bridge_ready(deadline_seconds: float = _BRIDGE_READY_DEADLINE) -> None:
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{_BRIDGE_URL}/.well-known/agent-card.json", timeout=0.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(
        f"a2a-bridge on {_BRIDGE_URL} did not become ready within {deadline_seconds}s: "
        f"{last_error!r}"
    )


def _port_listening(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        try:
            sock.connect((host, port))
        except OSError:
            return False
        return True


def _wait_until(predicate, deadline_seconds: float, *, interval: float = 0.5) -> bool:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _read_events_readonly(db_path: Path) -> list[dict[str, object]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, run_id, kind, level, ts, payload_json "
            "FROM events ORDER BY id ASC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "kind": row["kind"],
            "level": row["level"],
            "ts": row["ts"],
            "payload": json.loads(row["payload_json"] or "{}"),
        }
        for row in rows
    ]


def _ungraceful_kill(process: subprocess.Popen[bytes]) -> None:
    """SIGKILL on POSIX, ``taskkill /F /T`` on Windows.

    Critically, this MUST NOT give the process a chance to run its
    SIGINT/SIGTERM handler — otherwise it would write a fresh
    ``shutdown.marker`` and the orphan-recovery rule would skip the in-flight
    run on next start.
    """
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            check=False,
            capture_output=True,
        )
    else:
        try:
            os.kill(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _stop_process_gracefully(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bearer_token() -> str:
    return secrets.token_hex(32)


@pytest.fixture(scope="module")
def ntfy_topic() -> str:
    return uuid.uuid4().hex


@pytest.fixture(scope="module")
def tmp_repo(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Create a throwaway local git repo for ``WorktreeManager`` to operate on.

    The orchestrator's ``WorktreeManager`` reconcile step calls ``git
    worktree …`` against ``ORCHESTRATOR_REPO_PATH`` on every daemon boot.
    Pointing it at a throwaway ``git init`` directory keeps that subsystem
    happy without any GitHub side effects.
    """
    if shutil.which("git") is None:
        pytest.skip("git CLI not on PATH")
    workdir = tmp_path_factory.mktemp("orchestrator-tmp-repo")
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(workdir)],
        check=True,
        capture_output=True,
    )
    seed = workdir / "README.md"
    seed.write_text("# tmp repo\n", encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "-c",
            "user.email=orchestrator-test@example.invalid",
            "-c",
            "user.name=Orchestrator Test",
            "add",
            "README.md",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(workdir),
            "-c",
            "user.email=orchestrator-test@example.invalid",
            "-c",
            "user.name=Orchestrator Test",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture(scope="module")
def bridge(
    bearer_token: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Start the a2a-bridge for the module's lifetime."""
    log_dir = tmp_path_factory.mktemp("bridge-logs")
    stdout_log = (log_dir / "bridge-stdout.log").open("w", encoding="utf-8")
    stderr_log = (log_dir / "bridge-stderr.log").open("w", encoding="utf-8")

    env = os.environ.copy()
    env["A2A_BEARER_TOKEN"] = bearer_token

    process = subprocess.Popen(
        ["uv", "run", "a2a-bridge", "serve", "claude"],
        cwd=str(_BRIDGE_DIR),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        shell=sys.platform == "win32",
    )
    try:
        _wait_for_bridge_ready()
        yield None
    finally:
        _stop_process_gracefully(process)
        stdout_log.close()
        stderr_log.close()


def _spawn_daemon(
    *,
    repo_slug: str,
    bearer_token: str,
    ntfy_topic: str,
    db_path: Path,
    repo_path: Path,
    worktree_root: Path,
    log_dir: Path,
    poll_seconds: int = 30,
) -> subprocess.Popen[bytes]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    worktree_root.mkdir(parents=True, exist_ok=True)
    stdout_log = (log_dir / "daemon-stdout.log").open("w", encoding="utf-8")
    stderr_log = (log_dir / "daemon-stderr.log").open("w", encoding="utf-8")

    env = os.environ.copy()
    env["ORCHESTRATOR_REPO"] = repo_slug
    env["ORCHESTRATOR_NTFY_TOPIC"] = ntfy_topic
    env["ORCHESTRATOR_POLL_SECONDS"] = str(poll_seconds)
    env["ORCHESTRATOR_DB_PATH"] = str(db_path)
    env["ORCHESTRATOR_REPO_PATH"] = str(repo_path)
    env["ORCHESTRATOR_WORKTREE_ROOT"] = str(worktree_root)
    env["A2A_PEER_URL"] = _BRIDGE_URL
    env["A2A_BEARER_TOKEN"] = bearer_token

    return subprocess.Popen(
        ["uv", "run", "orchestrator", "serve"],
        cwd=str(_ORCHESTRATOR_DIR),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        shell=sys.platform == "win32",
    )


def _spawn_dashboard(
    *,
    repo_slug: str,
    bearer_token: str,
    ntfy_topic: str,
    db_path: Path,
    repo_path: Path,
    worktree_root: Path,
    log_dir: Path,
) -> subprocess.Popen[bytes]:
    stdout_log = (log_dir / "dash-stdout.log").open("w", encoding="utf-8")
    stderr_log = (log_dir / "dash-stderr.log").open("w", encoding="utf-8")

    env = os.environ.copy()
    env["ORCHESTRATOR_REPO"] = repo_slug
    env["ORCHESTRATOR_NTFY_TOPIC"] = ntfy_topic
    env["ORCHESTRATOR_DB_PATH"] = str(db_path)
    env["ORCHESTRATOR_REPO_PATH"] = str(repo_path)
    env["ORCHESTRATOR_WORKTREE_ROOT"] = str(worktree_root)
    env["A2A_PEER_URL"] = _BRIDGE_URL
    env["A2A_BEARER_TOKEN"] = bearer_token

    return subprocess.Popen(
        ["uv", "run", "orchestrator", "dash"],
        cwd=str(_ORCHESTRATOR_DIR),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log,
        shell=sys.platform == "win32",
    )


# ---------------------------------------------------------------------------
# Acceptance scenario 1 — replayable history across all-component restart
# ---------------------------------------------------------------------------


def test_dashboardRelaunch_PreservesHistoricalEventRecord(
    tmp_path: Path,
    tmp_repo: Path,
    bearer_token: str,
    ntfy_topic: str,
) -> None:
    db_path = tmp_path / "events.db"
    worktree_root = tmp_path / "worktrees"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    eventlog.bootstrap(db_path)
    seeded_run_id = str(uuid.uuid4())
    conn = eventlog.connect(db_path)
    try:
        eventlog.append_event(
            conn,
            run_id=seeded_run_id,
            kind="run.queued",
            level="info",
            payload={
                "kind": "pr.review",
                "repo": _THROWAWAY_REPO_SLUG,
                "pr_number": 7,
                "head_sha": "a" * 40,
            },
        )
        eventlog.append_event(
            conn,
            run_id=seeded_run_id,
            kind="run.started",
            level="info",
            payload={"pr_number": 7},
        )
        eventlog.append_event(
            conn,
            run_id=seeded_run_id,
            kind="run.completed",
            level="info",
            payload={"artifact_url": "https://example.invalid/pull/7#issuecomment-1"},
        )
        conn.commit()
    finally:
        conn.close()

    expected_kinds = ["run.queued", "run.started", "run.completed"]
    expected_run_ids = [seeded_run_id] * 3
    expected_ids_before = [e["id"] for e in _read_events_readonly(db_path)]

    first_dash = _spawn_dashboard(
        repo_slug=_THROWAWAY_REPO_SLUG,
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        repo_path=tmp_repo,
        worktree_root=worktree_root,
        log_dir=log_dir,
    )
    try:
        time.sleep(2.0)
        assert first_dash.poll() is None, "dashboard exited unexpectedly during smoke check"
    finally:
        _ungraceful_kill(first_dash)

    second_dash = _spawn_dashboard(
        repo_slug=_THROWAWAY_REPO_SLUG,
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        repo_path=tmp_repo,
        worktree_root=worktree_root,
        log_dir=log_dir,
    )
    try:
        time.sleep(2.0)
        assert second_dash.poll() is None, "relaunched dashboard exited unexpectedly"
    finally:
        _ungraceful_kill(second_dash)

    events_after = _read_events_readonly(db_path)
    kinds_after = [e["kind"] for e in events_after]
    run_ids_after = [e["run_id"] for e in events_after]
    ids_after = [e["id"] for e in events_after]

    assert kinds_after == expected_kinds
    assert run_ids_after == expected_run_ids
    assert ids_after == expected_ids_before


# ---------------------------------------------------------------------------
# Acceptance scenario 2 — daemon SIGKILLed mid-run produces orphan on restart
# ---------------------------------------------------------------------------


def test_daemonSigkilledMidRun_NextStartMarksRunAsOrphaned(
    tmp_path: Path,
    tmp_repo: Path,
    bridge: None,
    bearer_token: str,
    ntfy_topic: str,
) -> None:
    del bridge  # ordering dependency only

    db_path = tmp_path / "events.db"
    worktree_root = tmp_path / "worktrees"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    marker_path = db_path.parent / "shutdown.marker"

    eventlog.bootstrap(db_path)

    in_flight_run_id = str(uuid.uuid4())
    backdated_started_at = datetime.now(UTC) - timedelta(seconds=5)
    conn = eventlog.connect(db_path)
    try:
        eventlog.append_event(
            conn,
            run_id=in_flight_run_id,
            kind="run.queued",
            level="info",
            payload={
                "kind": "pr.review",
                "repo": _THROWAWAY_REPO_SLUG,
                "pr_number": 13,
                "head_sha": "b" * 40,
            },
            ts=backdated_started_at - timedelta(seconds=1),
        )
        eventlog.append_event(
            conn,
            run_id=in_flight_run_id,
            kind="run.started",
            level="info",
            payload={"pr_number": 13},
            ts=backdated_started_at,
        )
        conn.commit()
    finally:
        conn.close()

    eventlog.write_shutdown_marker(marker_path)
    marker_ts_before = marker_path.read_text(encoding="utf-8")

    first_daemon = _spawn_daemon(
        repo_slug=_THROWAWAY_REPO_SLUG,
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        repo_path=tmp_repo,
        worktree_root=worktree_root,
        log_dir=log_dir,
    )
    try:
        assert _wait_until(
            lambda: db_path.exists(),
            deadline_seconds=_DAEMON_BOOTSTRAP_DEADLINE,
        ), "daemon did not bootstrap the eventlog"
        time.sleep(2.0)
    finally:
        _ungraceful_kill(first_daemon)

    marker_ts_after_kill = marker_path.read_text(encoding="utf-8")
    assert marker_ts_after_kill == marker_ts_before, (
        "shutdown.marker was refreshed despite SIGKILL — graceful handler ran "
        "and the orphan-recovery test premise is invalid"
    )

    events_after_kill = _read_events_readonly(db_path)
    orphan_kinds_after_kill = [
        e
        for e in events_after_kill
        if e["run_id"] == in_flight_run_id and e["kind"] == "run.orphaned"
    ]
    assert orphan_kinds_after_kill == [], (
        "no orphan event should be present before the second daemon start"
    )

    second_daemon = _spawn_daemon(
        repo_slug=_THROWAWAY_REPO_SLUG,
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        repo_path=tmp_repo,
        worktree_root=worktree_root,
        log_dir=log_dir,
    )
    try:
        def _orphan_recovered() -> bool:
            for event in _read_events_readonly(db_path):
                if event["run_id"] == in_flight_run_id and event["kind"] == "run.orphaned":
                    return True
            return False

        recovered = _wait_until(_orphan_recovered, deadline_seconds=_ORPHAN_RECOVERY_DEADLINE)
    finally:
        _ungraceful_kill(second_daemon)

    assert recovered, (
        "expected a run.orphaned event for the in-flight run after restart"
    )

    final_events = _read_events_readonly(db_path)
    orphan_events = [
        e
        for e in final_events
        if e["run_id"] == in_flight_run_id and e["kind"] == "run.orphaned"
    ]
    assert len(orphan_events) == 1
    assert orphan_events[0]["level"] == "warn"
    assert orphan_events[0]["payload"] == {"prior_state": "running"}
