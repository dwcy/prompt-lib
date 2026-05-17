"""Integration test — Phase 7 / T019 — issue triage end-to-end.

REQUIRES ``INTEGRATION=1``. Spawns real subprocesses, creates and deletes a
real GitHub repo, exercises the full poll-trigger -> issue-agent -> eventlog
-> ``gh issue comment`` pipeline end-to-end. Mirrors the structure of
``test_p1_pr_review_end_to_end.py`` adapted for GitHub Issues.

Map of test methods to spec.md User Story acceptance scenarios:

* ``test_serve_issue_opened_PostsTriageCommentAndCompletes`` — US1 1+2, US2 1.
* ``test_serve_issue_alreadyTriaged_EmitsRunSkippedAndPostsNothing`` — US4 1.
* ``test_serve_issue_peerDown_EmitsRunFailedAndPostsNothing`` — US1 4 / peer-down.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTEGRATION") != "1",
        reason="set INTEGRATION=1 to run live-network tests",
    ),
]


_REPO_ROOT = Path(__file__).resolve().parents[4]
_BRIDGE_DIR = _REPO_ROOT / "services" / "a2a-bridge"
_ORCHESTRATOR_DIR = _REPO_ROOT / "services" / "orchestrator"

_BRIDGE_HOST = "127.0.0.1"
_BRIDGE_PORT = 8765
_BRIDGE_URL = f"http://{_BRIDGE_HOST}:{_BRIDGE_PORT}"

_BRIDGE_READY_DEADLINE = 30.0
_RUN_DEADLINE = 120.0
_FAILURE_DEADLINE = 60.0
_SKIPPED_WINDOW = 20.0

_TERMINAL_KINDS = frozenset({"run.completed", "run.failed", "run.skipped", "run.orphaned"})


def _gh_user_login() -> str:
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


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


def _wait_until(predicate, deadline_seconds: float, *, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _read_events(db_path: Path) -> list[dict[str, object]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, run_id, kind, level, payload_json FROM events ORDER BY id ASC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "kind": row["kind"],
            "level": row["level"],
            "payload": json.loads(row["payload_json"] or "{}"),
        }
        for row in rows
    ]


def _terminal_runs(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    by_run: dict[str, dict[str, object]] = {}
    for event in events:
        if event["kind"] in _TERMINAL_KINDS:
            run_id = str(event["run_id"])
            by_run.setdefault(run_id, event)
    return by_run


def _issue_comment_count(repo: str, issue_number: int) -> int:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "comments",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout or "{}")
    return len(payload.get("comments") or [])


@pytest.fixture(scope="module")
def gh_login() -> str:
    if shutil.which("gh") is None:
        pytest.skip("gh CLI not on PATH")
    auth = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, check=False
    )
    if auth.returncode != 0:
        pytest.skip(f"gh not authenticated: {auth.stderr.strip()}")
    return _gh_user_login()


@pytest.fixture(scope="module")
def bearer_token() -> str:
    return secrets.token_hex(32)


@pytest.fixture(scope="module")
def ntfy_topic() -> str:
    return uuid.uuid4().hex


@pytest.fixture(scope="module")
def test_repo(gh_login: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    """Create a private throwaway GitHub repo for the module's lifetime."""
    repo_name = f"orchestrator-triage-test-{uuid.uuid4().hex[:8]}"
    repo_slug = f"{gh_login}/{repo_name}"
    workdir = tmp_path_factory.mktemp(f"repo-{repo_name}")

    subprocess.run(["git", "init", "-q", "-b", "main", str(workdir)], check=True)
    seed = workdir / "README.md"
    seed.write_text(f"# {repo_name}\n\nThrowaway repo for orchestrator triage tests.\n")
    subprocess.run(["git", "-C", str(workdir), "add", "README.md"], check=True)
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
    )

    created = False
    try:
        subprocess.run(
            [
                "gh",
                "repo",
                "create",
                repo_slug,
                "--private",
                "--push",
                "--source",
                str(workdir),
                "--remote",
                "origin",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        created = True
        yield {"slug": repo_slug, "path": str(workdir), "name": repo_name}
    finally:
        if created:
            subprocess.run(
                ["gh", "repo", "delete", repo_slug, "--yes"],
                check=False,
                capture_output=True,
                text=True,
            )


@pytest.fixture(scope="module")
def bridge(bearer_token: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Start the a2a-bridge serving the claude adapter for the module."""
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
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        stdout_log.close()
        stderr_log.close()


def _spawn_daemon(
    *,
    repo_slug: str,
    bearer_token: str,
    ntfy_topic: str,
    db_path: Path,
    log_dir: Path,
    poll_seconds: int = 5,
) -> subprocess.Popen[bytes]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_log = (log_dir / "daemon-stdout.log").open("w", encoding="utf-8")
    stderr_log = (log_dir / "daemon-stderr.log").open("w", encoding="utf-8")

    env = os.environ.copy()
    env["ORCHESTRATOR_REPO"] = repo_slug
    env["ORCHESTRATOR_NTFY_TOPIC"] = ntfy_topic
    env["ORCHESTRATOR_POLL_SECONDS"] = str(poll_seconds)
    env["ORCHESTRATOR_DB_PATH"] = str(db_path)
    env["ORCHESTRATOR_ENABLE_ISSUE_TRIAGE"] = "true"
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


def _stop_daemon(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture
def daemon(
    test_repo: dict[str, str],
    bridge: None,
    bearer_token: str,
    ntfy_topic: str,
    tmp_path: Path,
) -> Iterator[Path]:
    """Spawn the orchestrator daemon (issue triage enabled) with a fresh DB."""
    del bridge
    db_path = tmp_path / "events.db"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    process = _spawn_daemon(
        repo_slug=test_repo["slug"],
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        log_dir=log_dir,
    )
    try:
        if not _wait_until(lambda: db_path.exists(), deadline_seconds=20.0, interval=0.5):
            raise RuntimeError("daemon did not bootstrap the eventlog within 20s")
        yield db_path
    finally:
        _stop_daemon(process)


def _open_issue(repo: dict[str, str], title: str, body: str) -> int:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo["slug"],
            "--title",
            title,
            "--body",
            body,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    last_line = (result.stdout or "").strip().splitlines()[-1]
    return int(last_line.rsplit("/", 1)[-1])


def _wait_for_terminal_run(
    db_path: Path,
    *,
    deadline_seconds: float,
    after_run_ids: set[str] | None = None,
) -> dict[str, object] | None:
    after = after_run_ids or set()
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        events = _read_events(db_path)
        terminals = _terminal_runs(events)
        new_terminals = {rid: ev for rid, ev in terminals.items() if rid not in after}
        if new_terminals:
            return next(iter(new_terminals.values()))
        time.sleep(2.0)
    return None


def _wait_for_event_kind(
    db_path: Path,
    kind: str,
    *,
    deadline_seconds: float,
    where: dict[str, object] | None = None,
) -> dict[str, object] | None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        for event in _read_events(db_path):
            if event["kind"] != kind:
                continue
            payload = event.get("payload") or {}
            if where is None or all(
                isinstance(payload, dict) and payload.get(k) == v for k, v in where.items()
            ):
                return event
        time.sleep(1.0)
    return None


def test_serve_issue_opened_PostsTriageCommentAndCompletes(
    test_repo: dict[str, str],
    daemon: Path,
) -> None:
    issue_number = _open_issue(
        test_repo,
        "scenario A — opened",
        "The README is missing a contributing section. Please add one.",
    )

    terminal = _wait_for_terminal_run(daemon, deadline_seconds=_RUN_DEADLINE)

    assert terminal is not None, "no terminal run event recorded within deadline"
    assert terminal["kind"] == "run.completed", (
        f"expected run.completed, got {terminal['kind']}: {terminal.get('payload')}"
    )

    events = _read_events(daemon)
    kinds = [e["kind"] for e in events]
    assert "run.queued" in kinds
    assert "run.started" in kinds
    assert "triage.decision" in kinds
    assert "gh.comment.posted" in kinds

    decision = next(e for e in events if e["kind"] == "triage.decision")
    payload = decision.get("payload") or {}
    assert isinstance(payload, dict)
    assert payload.get("issue_number") == issue_number
    for key in ("category", "severity", "assessment", "routing"):
        assert key in payload, f"triage.decision payload missing {key}: {payload}"

    assert _issue_comment_count(test_repo["slug"], issue_number) >= 1


def test_serve_issue_alreadyTriaged_EmitsRunSkippedAndPostsNothing(
    test_repo: dict[str, str],
    daemon: Path,
) -> None:
    issue_number = _open_issue(
        test_repo,
        "scenario B — duplicate suppression",
        "Triage me once.",
    )

    first = _wait_for_terminal_run(daemon, deadline_seconds=_RUN_DEADLINE)
    assert first is not None, "first run never reached terminal"
    assert first["kind"] == "run.completed"

    comments_after_first = _issue_comment_count(test_repo["slug"], issue_number)
    first_run_ids = {str(first["run_id"])}

    skipped = _wait_for_event_kind(
        daemon,
        "run.skipped",
        deadline_seconds=_SKIPPED_WINDOW,
        where={"issue_number": issue_number, "reason": "already_triaged"},
    )

    assert skipped is not None, (
        "expected a run.skipped event for the already-triaged issue within "
        f"{_SKIPPED_WINDOW}s after first completion"
    )

    events = _read_events(daemon)
    new_terminals = {
        rid: ev
        for rid, ev in _terminal_runs(events).items()
        if rid not in first_run_ids and ev["kind"] in {"run.completed", "run.failed"}
    }
    assert new_terminals == {}, (
        f"no second run.completed/run.failed should exist for issue #{issue_number}; "
        f"saw: {new_terminals}"
    )

    assert _issue_comment_count(test_repo["slug"], issue_number) == comments_after_first


def test_serve_issue_peerDown_EmitsRunFailedAndPostsNothing(
    test_repo: dict[str, str],
    bridge: None,
    bearer_token: str,
    ntfy_topic: str,
    tmp_path: Path,
) -> None:
    """Peer-down — daemon is started after the bridge has been killed.

    We do not reuse the ``daemon`` fixture because it depends on the live
    module bridge, and we need the bridge unreachable for the entire run.
    """
    del bridge

    issue_number = _open_issue(
        test_repo,
        "scenario C — peer down",
        "Triage with the bridge offline.",
    )
    initial_comments = _issue_comment_count(test_repo["slug"], issue_number)

    bridge_killed = False
    if _port_listening(_BRIDGE_HOST, _BRIDGE_PORT):
        if sys.platform == "win32":
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-NetTCPConnection -LocalPort {_BRIDGE_PORT} -State Listen | "
                    "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }",
                ],
                check=False,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["pkill", "-f", "a2a-bridge serve claude"], check=False, capture_output=True
            )
        bridge_killed = _wait_until(
            lambda: not _port_listening(_BRIDGE_HOST, _BRIDGE_PORT),
            deadline_seconds=10.0,
            interval=0.5,
        )

    if not bridge_killed and _port_listening(_BRIDGE_HOST, _BRIDGE_PORT):
        pytest.skip("could not stop module-scoped bridge to simulate peer-down")

    db_path = tmp_path / "events.db"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    process = _spawn_daemon(
        repo_slug=test_repo["slug"],
        bearer_token=bearer_token,
        ntfy_topic=ntfy_topic,
        db_path=db_path,
        log_dir=log_dir,
    )
    try:
        assert _wait_until(lambda: db_path.exists(), deadline_seconds=20.0, interval=0.5), (
            "daemon never bootstrapped the eventlog"
        )
        terminal = _wait_for_terminal_run(db_path, deadline_seconds=_FAILURE_DEADLINE)
    finally:
        _stop_daemon(process)

    assert terminal is not None, "expected a run.failed terminal event within deadline"
    assert terminal["kind"] == "run.failed", (
        f"expected run.failed, got {terminal['kind']}: {terminal.get('payload')}"
    )
    payload = terminal.get("payload") or {}
    assert isinstance(payload, dict)
    assert payload.get("stage") == "delegate", (
        f"run.failed should record stage=delegate; got payload={payload}"
    )

    events = _read_events(db_path)
    posted = [e for e in events if e["kind"] == "gh.comment.posted"]
    assert posted == [], "no gh.comment.posted events should be recorded when peer is down"

    assert _issue_comment_count(test_repo["slug"], issue_number) == initial_comments
