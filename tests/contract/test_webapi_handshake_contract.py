"""Contract tests for specs/015-web-ui-overhaul/contracts/desktop-shell.contract.md.

Backend-side handshake assertions only (per the contract, shell-side adoption/orphan
behavior is covered by Playwright/`tauri dev` smoke, not this pytest suite).
"""

from __future__ import annotations

import json
import os
import subprocess
import time

import httpx
import pytest

from .webapi_fixtures import (
    auth_headers,
    import_or_fail,
    spawn_backend,
    terminate_backend,
    wait_for_handshake,
)

HANDSHAKE_SCHEMA = "cabal-handshake.v1"


def test_write_handshake_atomic_leaves_no_partial_state(tmp_path) -> None:
    security = import_or_fail("cabal.webapi.security")
    path = tmp_path / "webapi-handshake.json"

    security.write_handshake_atomic(
        path,
        port=54321,
        token="tok-abc",
        pid=os.getpid(),
        started_at="2026-01-01T00:00:00Z",
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "schema": HANDSHAKE_SCHEMA,
        "port": 54321,
        "token": "tok-abc",
        "pid": os.getpid(),
        "started_at": "2026-01-01T00:00:00Z",
    }
    leftovers = [p for p in tmp_path.iterdir() if p != path]
    assert leftovers == []


def test_backend_writes_handshake_before_serving_and_port_matches_bound_socket(tmp_path) -> None:
    storage_path = tmp_path / "cabal.sqlite3"
    handshake_path = tmp_path / "webapi-handshake.json"
    proc = spawn_backend(storage_path=storage_path, handshake_path=handshake_path)

    try:
        data = wait_for_handshake(handshake_path, proc)
        assert data["schema"] == HANDSHAKE_SCHEMA
        assert isinstance(data["port"], int) and data["port"] > 0
        assert data["pid"] == proc.pid
        assert isinstance(data["started_at"], str) and data["started_at"]

        response = httpx.get(
            f"http://127.0.0.1:{data['port']}/api/health",
            headers=auth_headers(data["token"]),
            timeout=5.0,
        )
        assert response.status_code == 200
    finally:
        terminate_backend(proc)


def test_handshake_file_is_owner_restricted(tmp_path) -> None:
    security = import_or_fail("cabal.webapi.security")
    storage_path = tmp_path / "cabal.sqlite3"
    handshake_path = tmp_path / "webapi-handshake.json"
    proc = spawn_backend(storage_path=storage_path, handshake_path=handshake_path)

    try:
        wait_for_handshake(handshake_path, proc)
        assert security.handshake_is_owner_restricted(handshake_path) is True
    finally:
        terminate_backend(proc)


def test_wrong_token_rejected_and_correct_token_accepted(tmp_path) -> None:
    storage_path = tmp_path / "cabal.sqlite3"
    handshake_path = tmp_path / "webapi-handshake.json"
    proc = spawn_backend(storage_path=storage_path, handshake_path=handshake_path)

    try:
        data = wait_for_handshake(handshake_path, proc)
        base_url = f"http://127.0.0.1:{data['port']}"

        wrong = httpx.get(f"{base_url}/api/health", headers=auth_headers("not-the-token"), timeout=5.0)
        assert wrong.status_code == 401

        right = httpx.get(f"{base_url}/api/health", headers=auth_headers(data["token"]), timeout=5.0)
        assert right.status_code == 200
    finally:
        terminate_backend(proc)


def test_stale_handshake_with_dead_pid_is_replaced_on_next_start(tmp_path) -> None:
    security = import_or_fail("cabal.webapi.security")
    storage_path = tmp_path / "cabal.sqlite3"
    handshake_path = tmp_path / "webapi-handshake.json"

    first = spawn_backend(storage_path=storage_path, handshake_path=handshake_path)
    stale = wait_for_handshake(handshake_path, first)
    terminate_backend(first)

    deadline = time.monotonic() + 5.0
    while security.is_pid_alive(stale["pid"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert security.is_pid_alive(stale["pid"]) is False

    second_storage = tmp_path / "cabal-2.sqlite3"
    second = spawn_backend(storage_path=second_storage, handshake_path=handshake_path)
    try:
        fresh = wait_for_handshake(handshake_path, second)
        assert fresh["pid"] == second.pid
        assert fresh["pid"] != stale["pid"]
        assert fresh["token"] != stale["token"]
    finally:
        terminate_backend(second)


def test_shutdown_removes_handshake_file_and_exits_within_grace_window(tmp_path) -> None:
    storage_path = tmp_path / "cabal.sqlite3"
    handshake_path = tmp_path / "webapi-handshake.json"
    proc = spawn_backend(storage_path=storage_path, handshake_path=handshake_path)

    try:
        data = wait_for_handshake(handshake_path, proc)
        response = httpx.post(
            f"http://127.0.0.1:{data['port']}/api/system/shutdown",
            headers=auth_headers(data["token"]),
            timeout=5.0,
        )
        assert response.status_code == 200

        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pytest.fail("backend did not exit within the shutdown grace window")

        assert not handshake_path.exists()
    finally:
        terminate_backend(proc)
