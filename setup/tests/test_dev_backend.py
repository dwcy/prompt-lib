# -*- coding: utf-8 -*-
"""Change detection for the dev backend supervisor (setup/tools/dev_backend.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import psutil
import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
SUPERVISOR_PATH = TOOLS_DIR / "dev_backend.py"

# dev_backend imports its sibling dev_watch the way the script does — by directory, which is
# sys.path[0] under `python setup/tools/dev_backend.py` but not when loaded from a spec here.
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

spec = importlib.util.spec_from_file_location("dev_backend", SUPERVISOR_PATH)
dev_backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev_backend)

import dev_backend_procs  # noqa: E402  (needs TOOLS_DIR on sys.path, inserted above)


def _unused_pid() -> int:
    """A pid that is not in use, so clear_stale_handshake sees a dead owner."""
    for candidate in range(60000, 65000):
        if not psutil.pid_exists(candidate):
            return candidate
    raise AssertionError("no free pid found")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "service.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "pkg" / "__pycache__").mkdir()
    (tmp_path / "pkg" / "__pycache__" / "service.cpython-314.pyc").write_bytes(b"\x00")
    (tmp_path / "pkg" / "notes.md").write_text("not watched", encoding="utf-8")
    return tmp_path


def test_watching_ignores_generated_and_non_python_files(tree: Path) -> None:
    watched = {path.name for path in dev_backend.iter_watched_files([tree])}

    assert watched == {"service.py"}


def test_editing_a_source_file_is_reported_as_a_change(tree: Path) -> None:
    before = dev_backend.snapshot([tree])
    source = tree / "pkg" / "service.py"
    source.write_text("x = 2", encoding="utf-8")
    # Coarse filesystem timestamps can collide within one test run.
    os.utime(source, (0, before[source] + 10))

    assert dev_backend.changed_paths(before, dev_backend.snapshot([tree])) == [source]


def test_deleting_a_source_file_is_reported_as_a_change(tree: Path) -> None:
    before = dev_backend.snapshot([tree])
    source = tree / "pkg" / "service.py"
    source.unlink()

    assert dev_backend.changed_paths(before, dev_backend.snapshot([tree])) == [source]


def test_an_untouched_tree_reports_no_changes(tree: Path) -> None:
    before = dev_backend.snapshot([tree])

    assert dev_backend.changed_paths(before, dev_backend.snapshot([tree])) == []


def test_change_summary_stays_short_for_a_large_burst(tree: Path) -> None:
    paths = [tree / "pkg" / f"module_{index}.py" for index in range(6)]

    summary = dev_backend.describe(paths, tree)

    assert summary == "pkg/module_0.py, pkg/module_1.py, pkg/module_2.py, (+3 more)"


def _handshake(path: Path, pid: int) -> None:
    path.write_text(
        json.dumps({"schema": "cabal-handshake.v1", "port": 51000, "token": "t", "pid": pid}),
        encoding="utf-8",
    )


def test_a_live_backends_handshake_is_left_alone(tmp_path: Path) -> None:
    # Deleting it would disarm cabal-backend's single-instance guard and let a second
    # backend start behind a running app's back.
    path = tmp_path / "handshake.json"
    _handshake(path, os.getpid())

    dev_backend_procs.clear_stale_handshake(path)

    assert path.exists()


def test_a_dead_backends_handshake_is_removed(tmp_path: Path) -> None:
    path = tmp_path / "handshake.json"
    _handshake(path, _unused_pid())

    dev_backend_procs.clear_stale_handshake(path)

    assert not path.exists()


def test_an_unreadable_handshake_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "handshake.json"
    path.write_text("{ not json", encoding="utf-8")

    dev_backend_procs.clear_stale_handshake(path)

    assert path.exists()


def test_a_missing_handshake_is_not_an_error(tmp_path: Path) -> None:
    dev_backend_procs.clear_stale_handshake(tmp_path / "absent.json")


def test_a_recycled_pid_pointing_at_an_unrelated_process_is_never_killed(tmp_path: Path) -> None:
    # The handshake records a pid, and pids get recycled. This test's own process occupies the
    # recorded pid but is plainly not a backend, so takeover must decline.
    path = tmp_path / "handshake.json"
    _handshake(path, os.getpid())

    stopped, message = dev_backend_procs.takeover(path)

    assert stopped is False
    assert "not a cabal backend" in message
    assert path.exists()


def test_takeover_does_nothing_when_no_backend_is_recorded(tmp_path: Path) -> None:
    assert dev_backend_procs.takeover(tmp_path / "absent.json") == (False, None)


def test_takeover_ignores_a_handshake_whose_process_is_gone(tmp_path: Path) -> None:
    path = tmp_path / "handshake.json"
    _handshake(path, _unused_pid())

    assert dev_backend_procs.takeover(path) == (False, None)


@pytest.mark.parametrize(
    "cmdline",
    [
        ["python.exe", "-m", "cabal.webapi", "--project", "C:/repo"],
        ["cabal-backend.exe", "--project", "C:/repo"],
        ["uv", "run", "cabal-backend"],
    ],
)
def test_every_way_the_backend_is_launched_is_recognised(cmdline: list[str]) -> None:
    class Fake:
        def cmdline(self) -> list[str]:
            return cmdline

    assert dev_backend_procs.looks_like_backend(Fake()) is True


@pytest.mark.parametrize("cmdline", [["python.exe", "-m", "pytest"], ["code.exe"], []])
def test_unrelated_processes_are_not_recognised(cmdline: list[str]) -> None:
    class Fake:
        def cmdline(self) -> list[str]:
            return cmdline

    assert dev_backend_procs.looks_like_backend(Fake()) is False
