"""Unit coverage for local TCP listener discovery and process shutdown."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import psutil

from cabal.webapi import running_apps_service


class _FakeProcess:
    terminated = False

    def __init__(self, pid: int, location: str) -> None:
        self.pid = pid
        self._location = location

    def oneshot(self):
        return nullcontext()

    def name(self) -> str:
        return "node.exe"

    def create_time(self) -> float:
        return 1_725_000_000.25

    def cwd(self) -> str:
        return self._location

    def exe(self) -> str:
        return f"{self._location}/node.exe"

    def terminate(self) -> None:
        type(self).terminated = True

    def wait(self, timeout: float) -> int:
        del timeout
        return 0

    def kill(self) -> None:
        raise AssertionError("graceful termination should have succeeded")


def test_discovers_manifest_named_listener_and_stops_verified_process(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "package.json").write_text('{"name":"fixture-web"}', encoding="utf-8")
    connection = SimpleNamespace(
        pid=4_242,
        status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip="127.0.0.1", port=5_173),
    )
    monkeypatch.setattr(running_apps_service, "_tcp_connections", lambda: [connection])
    monkeypatch.setattr(
        running_apps_service.psutil,
        "Process",
        lambda pid: _FakeProcess(pid, str(tmp_path)),
    )

    payload = running_apps_service.running_apps_payload()

    assert payload["count"] == 1
    assert payload["apps"][0] == {
        "port": 5_173,
        "pid": 4_242,
        "app_name": "fixture-web",
        "location": str(tmp_path),
        "address": "127.0.0.1",
        "started_at": 1_725_000_000.25,
    }

    stopped = running_apps_service.stop_running_app(4_242, 5_173, 1_725_000_000.25)

    assert stopped["stopped"] is True
    assert _FakeProcess.terminated is True


def test_excludes_the_cabal_backend_listener(monkeypatch) -> None:
    connection = SimpleNamespace(
        pid=running_apps_service.os.getpid(),
        status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip="127.0.0.1", port=8_000),
    )
    monkeypatch.setattr(running_apps_service, "_tcp_connections", lambda: [connection])

    assert running_apps_service.running_apps_payload() == {"apps": [], "count": 0}
