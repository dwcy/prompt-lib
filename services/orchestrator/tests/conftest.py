"""Shared pytest fixtures for the orchestrator test suite (T007).

Fixtures provided:

* ``tmp_db`` — returns a fresh ``Path`` to a SQLite file under pytest's
  ``tmp_path``. The file does NOT exist yet; bootstrapping the schema is the
  ``orchestrator.eventlog`` module's responsibility (see T013). Each test gets
  its own database — there is no shared state between tests.

* ``fake_gh`` — installs a cross-platform ``gh`` shim onto the test's PATH
  whose behaviour is configured per-test via the returned :class:`FakeGh`
  helper. The shim is a tiny Python script invoked through a ``.cmd`` wrapper
  on Windows and via a ``#!`` shebang on POSIX. The wrapper reads
  ``behavior.json`` from the same directory and matches the invocation argv
  against queued rules; first match wins. Unmatched argv produces a default
  empty-success response.

  Why this shape and not ``monkeypatch`` over ``subprocess.run`` directly?
  The orchestrator uses ``asyncio.create_subprocess_exec`` (R3) which goes
  through the OS, not Python's ``subprocess`` module. Mocking ``subprocess``
  would not intercept it. A real PATH-resolved shim is the only correct
  test stand-in for that production code path.

* ``fake_delegation_client`` — yields a factory ``make(events)`` returning a
  drop-in fake of ``a2a_bridge.client.delegation.DelegationClient``. The fake
  exposes an ``async def delegate(prompt) -> AsyncIterator[dict]`` that yields
  the canned events one-by-one so consumer logic can be tested without
  spinning up the real bridge.

``pytest-httpx``'s ``httpx_mock`` fixture is auto-discovered from the
installed plugin; no re-export is needed here.

The ``fake_gh`` fixture supports ANY ``gh`` subcommand via behavior.json rule
matching.  For issue-triage tests, queue rules like::

    fake_gh.queue(["issue", "list", "--json"], stdout=json.dumps([...]))
    fake_gh.queue(["issue", "comment"], returncode=0)
"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# tmp_db
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a non-existent SQLite file under ``tmp_path``.

    The eventlog module is responsible for creating the file and bootstrapping
    its schema when it opens it.
    """
    return tmp_path / "events.db"


# ---------------------------------------------------------------------------
# fake_gh
# ---------------------------------------------------------------------------


@dataclass
class _FakeGhRule:
    argv_match: list[str]
    stdout: str
    stderr: str
    returncode: int


@dataclass
class FakeGh:
    """Per-test handle to configure the ``gh`` shim's behaviour.

    Each call to :meth:`queue` adds a rule. When the shim is invoked, the
    first rule whose ``argv_match`` is a contiguous subsequence of the
    invocation argv (after the program name) is consumed and its stdout /
    stderr / returncode is used. Unmatched invocations exit ``0`` with no
    output.

    Rules are consumed in FIFO order and removed after the first match — call
    :meth:`queue` once per expected invocation.
    """

    bin_dir: Path
    behavior_file: Path
    rules: list[_FakeGhRule] = field(default_factory=list)

    def queue(
        self,
        argv_match: list[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.rules.append(
            _FakeGhRule(
                argv_match=list(argv_match),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )
        )
        self._flush()

    def reset(self) -> None:
        self.rules.clear()
        self._flush()

    def _flush(self) -> None:
        payload = {
            "rules": [
                {
                    "argv_match": rule.argv_match,
                    "stdout": rule.stdout,
                    "stderr": rule.stderr,
                    "returncode": rule.returncode,
                }
                for rule in self.rules
            ]
        }
        self.behavior_file.write_text(json.dumps(payload), encoding="utf-8")


_SHIM_PY_SOURCE = '''\
"""Test shim for `gh` — driven by behavior.json next to this file."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _argv_matches(rule_argv: list[str], invocation_argv: list[str]) -> bool:
    if not rule_argv:
        return True
    n = len(rule_argv)
    for start in range(0, len(invocation_argv) - n + 1):
        if invocation_argv[start : start + n] == rule_argv:
            return True
    return False


def main() -> int:
    here = Path(__file__).resolve().parent
    behavior_path = here / "behavior.json"
    if not behavior_path.exists():
        return 0
    data = json.loads(behavior_path.read_text(encoding="utf-8"))
    rules = data.get("rules", [])
    invocation_argv = sys.argv[1:]
    for index, rule in enumerate(rules):
        if _argv_matches(rule.get("argv_match", []), invocation_argv):
            stdout = rule.get("stdout", "")
            stderr = rule.get("stderr", "")
            returncode = int(rule.get("returncode", 0))
            if stdout:
                sys.stdout.write(stdout)
                sys.stdout.flush()
            if stderr:
                sys.stderr.write(stderr)
                sys.stderr.flush()
            remaining = rules[:index] + rules[index + 1 :]
            data["rules"] = remaining
            behavior_path.write_text(json.dumps(data), encoding="utf-8")
            return returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _write_fake_gh_shim(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim_py = bin_dir / "_gh_shim.py"
    shim_py.write_text(_SHIM_PY_SOURCE, encoding="utf-8")

    if sys.platform == "win32":
        cmd_path = bin_dir / "gh.cmd"
        cmd_path.write_text(
            f'@echo off\r\n"{sys.executable}" "{shim_py}" %*\r\n',
            encoding="utf-8",
        )
    else:
        gh_path = bin_dir / "gh"
        gh_path.write_text(
            f"#!/bin/sh\nexec {sys.executable!s} {shim_py!s} \"$@\"\n",
            encoding="utf-8",
        )
        gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeGh:
    bin_dir = tmp_path / "fake-gh"
    behavior_file = bin_dir / "behavior.json"
    _write_fake_gh_shim(bin_dir)

    handle = FakeGh(bin_dir=bin_dir, behavior_file=behavior_file)
    handle._flush()

    existing_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{existing_path}")
    return handle


# ---------------------------------------------------------------------------
# fake_delegation_client
# ---------------------------------------------------------------------------


class FakeDelegationClient:
    """Drop-in stand-in for ``a2a_bridge.client.delegation.DelegationClient``.

    Yields the events passed at construction in order. Supports use as an
    async context manager so tests can mirror production's ``async with``.
    """

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = list(events)
        self.delegate_calls: list[str] = []
        self.delegate_cwds: list[str | None] = []

    async def __aenter__(self) -> FakeDelegationClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def delegate(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.delegate_calls.append(prompt)
        self.delegate_cwds.append(cwd)
        for event in self._events:
            yield event


@pytest.fixture
def fake_delegation_client() -> Iterator[Callable[[list[dict[str, Any]]], FakeDelegationClient]]:
    def make(events: list[dict[str, Any]]) -> FakeDelegationClient:
        return FakeDelegationClient(events)

    yield make
