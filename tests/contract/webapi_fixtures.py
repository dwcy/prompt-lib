"""Shared fixtures/seams for the cabal.webapi contract-test suites (015-web-ui-overhaul).

This module is the authoritative seam spec T012-T019 must implement to satisfy
tests/contract/test_webapi_{envelope,handshake,action_safety,jobs_sse}_contract.py.
Import cabal.webapi.* only inside fixtures/helpers (never at module import time) so a
not-yet-implemented backend fails tests as ordinary FAILUREs, never collection errors.

Expected seams
--------------
``cabal.webapi.app``
    ``create_app(project: Path | None = None, *, storage_path: Path | None = None,
    handshake_path: Path | None = None, token: str | None = None) -> fastapi.FastAPI``
    Builds the app in-process without binding a socket (tests drive it via TestClient).
    State attached to the returned app:
      - ``app.state.token`` -- effective bearer token (generated if not passed).
      - ``app.state.storage`` -- the storage handle opened at ``storage_path``.
      - ``app.state.diagnostics`` -- ``DiagnosticsRecorder`` with
        ``.record(*, severity: str, module: str, message: str) -> dict`` (redacts on write)
        and ``.list(limit=None, severity=None) -> list[dict]``.
      - ``app.state.jobs`` -- a ``cabal.webapi.jobs.JobManager`` instance.
      - ``app.state.actions`` -- a ``cabal.webapi.actions.ActionRegistry`` instance; tests
        register fixture-only descriptors on it via ``.register(descriptor)``.
      - ``app.state.write_guard`` -- ``WriteGuard`` counter (``.count``, ``.reset()``)
        incremented by storage/jobs/actions on every persisted write; backs the
        action-safety zero-write GET-sweep assertion.

``cabal.webapi.security``
    - ``generate_token() -> str``
    - ``write_handshake_atomic(path, *, port, token, pid, started_at) -> None`` -- writes
      ``{"schema": "cabal-handshake.v1", "port", "token", "pid", "started_at"}`` atomically
      (temp file + rename in the same directory, no partial reads possible).
    - ``read_handshake(path) -> dict | None`` (None when absent/corrupt).
    - ``remove_handshake(path) -> None`` (no-op if absent).
    - ``restrict_to_owner(path) -> None`` -- applies the platform owner-only ACL/mode.
    - ``handshake_is_owner_restricted(path) -> bool`` -- truth source tests assert against;
      the implementation owns the POSIX-mode-vs-Windows-ACL branching.
    - ``is_pid_alive(pid: int) -> bool``

``cabal.webapi.__main__``
    ``main(argv=None) -> int``. CLI flags: ``--project``, ``--storage-path``,
    ``--handshake-path``, ``--token``, ``--host`` (default ``127.0.0.1``), ``--port``
    (default ``0`` = OS-assigned). Binds the socket, writes the handshake atomically
    once bound and BEFORE serving the first request, detects+replaces a stale handshake
    (dead pid) at that same path, then serves until ``POST /api/system/shutdown`` (or
    SIGTERM), removing the handshake file before exit.

``cabal.webapi.actions``
    - ``ActionDescriptor`` dataclass: ``action_id, module, destructive, backup_policy,
      params_schema, prepare, execute, compute_digest``.
      ``prepare(params: dict, state) -> dict`` returns an ``EffectPreview`` dict
      (``summary, commands, files_changed, scopes, backup, removals``).
      ``execute(params: dict, state) -> ActionOutcome``.
      ``compute_digest(params: dict, state) -> str | None`` -- omit/None for a static digest.
    - ``ActionOutcome`` dataclass: ``job_id: str | None = None, data: dict | None = None``
      (exactly one populated -- job_id => 202, data => 200).
    - ``ActionRegistry.register(descriptor) / .get(action_id) / .ids() -> list[str]``.
    - ``ActionRegistry.force_expire_ticket_for_test(ticket_id: str) -> None`` -- test-only hook
      that flips a pending ticket straight to the ``expired`` state so the 410 path is
      reachable without a real TTL sleep.
    - HTTP surface: ``POST /api/actions/{action_id}/prepare`` and
      ``POST /api/actions/{action_id}/execute`` per contracts/action-safety.contract.md.
      Prepare responses envelope a ``ConfirmationTicket`` in ``data``; execute responses
      envelope either ``{"job_id": ...}`` (202) or the outcome ``data`` (200). Also mounts
      ``GET /api/audit`` -> envelope ``data.entries: AuditEntry[]`` (written on execute).
      Non-2xx action-safety envelopes populate ``error.code`` with one of the specific
      machine-readable reasons the contract names: ``state_changed``, ``ticket_consumed``,
      ``ticket_expired``, ``ticket_not_found``, ``params_invalid``, ``job_conflict``.
      ``job_conflict`` additionally sets ``error.blocking_job_id`` to the job already
      holding the exclusive resource.

``cabal.webapi.jobs``
    - ``JobManager.create(kind, *, runner, ticket_id=None, exclusive_resource=None,
      ring_buffer_size=200) -> Job`` -- ``runner(handle)`` is invoked off-thread; ``handle``
      exposes ``.emit_line(text: str) -> None``, ``.is_cancelled() -> bool``,
      ``.finish(state: Literal["succeeded","failed"], exit_detail=None) -> None``.
    - ``JobManager.get(job_id) -> Job | None``, ``.list() -> list[Job]``,
      ``.cancel(job_id) -> bool``.
    - ``JobConflict`` exception with ``.blocking_job_id`` raised by ``.create`` when
      ``exclusive_resource`` is already held by a non-terminal job; the actions execute
      route translates this to ``409 job_conflict``.
    - SSE surface: ``GET /api/jobs/{id}/stream`` (grammar: ``event: output|state|heartbeat|gap``
      per contracts/jobs-and-streams.contract.md), reconnect via ``Last-Event-ID`` header.

Jobs are created ONLY through an executed action (never called directly by tests), matching
production. Fixture actions registered by ``register_fixture_actions`` below are the test-only
entry point that exercises ``app.state.jobs`` the same way a real descriptor would.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
CABAL_SRC = REPO_ROOT / "setup" / "src"

TEST_TOKEN = "cabal-test-token-0123456789abcdef"
FAKE_SECRET = "ghp_" + "x1Y2z3A4b5C6d7E8f9G0h1I2j3K4l5M6"


def import_or_fail(module_path: str) -> ModuleType:
    """Import a cabal.webapi.* module, turning ImportError into a readable FAILED test."""
    try:
        return importlib.import_module(module_path)
    except ImportError as exc:  # pragma: no cover - exercised until T012-T019 land
        pytest.fail(f"cabal.webapi not implemented yet: {exc}")


def auth_headers(token: str = TEST_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app_factory(tmp_path: Path) -> Callable[..., object]:
    """Return a lazy app builder. Deliberately does no import at fixture-setup time --
    the ImportError (and its pytest.fail) must surface inside the test's call phase so
    a not-yet-implemented backend reports as FAILED, never a fixture-setup ERROR.
    """

    def _factory(**overrides: object):
        app_module = import_or_fail("cabal.webapi.app")
        storage_path = overrides.pop("storage_path", tmp_path / "cabal-webapi.sqlite3")
        handshake_path = overrides.pop("handshake_path", tmp_path / "webapi-handshake.json")
        token = overrides.pop("token", TEST_TOKEN)
        project = overrides.pop("project", None)
        return app_module.create_app(
            project,
            storage_path=storage_path,
            handshake_path=handshake_path,
            token=token,
            **overrides,
        )

    return _factory


def build_client(app_factory: Callable[..., object], **overrides: object) -> tuple[object, TestClient]:
    """Build an app + TestClient pair from inside a test body (call phase, not setup)."""
    app = app_factory(**overrides)
    return app, TestClient(app)


def register_fixture_actions(app, *, secret: str = FAKE_SECRET) -> None:
    """Register the test-only ActionDescriptors used across the contract suites.

    - ``test.echo``: non-destructive, instant (200) result; digest driven by
      ``app.state.test_source_value`` so tests can force a 409 state_changed drift.
    - ``test.destructive``: destructive=True with non-empty removals/backup, for the
      registry self-check assertion.
    - ``test.job_emitter``: creates a job via ``app.state.jobs`` that emits N lines
      (optionally one containing FAKE_SECRET), honoring ``exclusive_resource`` and
      ``ring_buffer_size`` params -- the cheap job-kind seam for jobs/SSE tests.
    """
    actions_module = import_or_fail("cabal.webapi.actions")
    ActionDescriptor = actions_module.ActionDescriptor
    ActionOutcome = actions_module.ActionOutcome

    app.state.test_source_value = "initial"

    def echo_digest(_params: dict, state) -> str:
        return f"sha256:{state.test_source_value}"

    def echo_prepare(params: dict, _state) -> dict:
        note = params.get("note", "")
        return {
            "summary": f"Echo test note ({note!r})" if note else "Echo test note",
            "commands": [],
            "files_changed": [],
            "scopes": ["test"],
            "backup": None,
            "removals": [],
        }

    def echo_execute(params: dict, _state) -> "ActionOutcome":
        return ActionOutcome(data={"echoed": params.get("note", "")})

    def destructive_prepare(_params: dict, _state) -> dict:
        return {
            "summary": "Remove 2 fixture files",
            "commands": ["rm fixture-a.txt", "rm fixture-b.txt"],
            "files_changed": ["fixture-a.txt", "fixture-b.txt"],
            "scopes": ["test"],
            "backup": "test-backup",
            "removals": ["fixture-a.txt", "fixture-b.txt"],
        }

    def destructive_execute(_params: dict, _state) -> "ActionOutcome":
        return ActionOutcome(data={"removed": 2})

    def job_emitter_prepare(params: dict, _state) -> dict:
        return {
            "summary": f"Emit {params.get('lines', 1)} test job lines",
            "commands": [],
            "files_changed": [],
            "scopes": ["test"],
            "backup": None,
            "removals": [],
        }

    def job_emitter_execute(params: dict, state) -> "ActionOutcome":
        lines = int(params.get("lines", 1))
        secret_line = bool(params.get("secret", False))
        delay_ms = float(params.get("delay_ms", 10))
        exclusive_resource = params.get("exclusive_resource")
        ring_buffer_size = int(params.get("ring_buffer_size", 200))

        def runner(handle) -> None:
            for index in range(lines):
                if handle.is_cancelled():
                    handle.finish("cancelled")
                    return
                text = f"line {index}"
                if secret_line and index == 0:
                    text = f"line {index} token={secret}"
                handle.emit_line(text)
                time.sleep(delay_ms / 1000)
            handle.finish("succeeded")

        job = state.jobs.create(
            "test.echo_lines",
            runner=runner,
            exclusive_resource=exclusive_resource,
            ring_buffer_size=ring_buffer_size,
        )
        return ActionOutcome(job_id=job.job_id)

    app.state.actions.register(
        ActionDescriptor(
            action_id="test.echo",
            module="test",
            destructive=False,
            backup_policy=None,
            params_schema={
                "type": "object",
                "properties": {"note": {"type": "string"}},
                "additionalProperties": False,
            },
            prepare=echo_prepare,
            execute=echo_execute,
            compute_digest=echo_digest,
        )
    )
    app.state.actions.register(
        ActionDescriptor(
            action_id="test.destructive",
            module="test",
            destructive=True,
            backup_policy="test-backup",
            params_schema={"type": "object", "additionalProperties": False},
            prepare=destructive_prepare,
            execute=destructive_execute,
        )
    )
    app.state.actions.register(
        ActionDescriptor(
            action_id="test.job_emitter",
            module="test",
            destructive=False,
            backup_policy=None,
            params_schema={
                "type": "object",
                "properties": {
                    "lines": {"type": "integer"},
                    "secret": {"type": "boolean"},
                    "delay_ms": {"type": "number"},
                    "exclusive_resource": {"type": ["string", "null"]},
                    "ring_buffer_size": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            prepare=job_emitter_prepare,
            execute=job_emitter_execute,
        )
    )


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in (str(CABAL_SRC), existing) if p]
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def spawn_backend(
    *,
    storage_path: Path,
    handshake_path: Path,
    token: str | None = None,
    project: Path | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    """Spawn a real `python -m cabal.webapi` subprocess bound to an OS-assigned port."""
    import_or_fail("cabal.webapi.security")
    import_or_fail("cabal.webapi.app")

    cmd = [
        sys.executable,
        "-m",
        "cabal.webapi",
        "--storage-path",
        str(storage_path),
        "--handshake-path",
        str(handshake_path),
        "--host",
        "127.0.0.1",
        "--port",
        "0",
    ]
    if project is not None:
        cmd += ["--project", str(project)]
    if token is not None:
        cmd += ["--token", token]
    if extra_args:
        cmd += extra_args
    return subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=_child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def wait_for_handshake(path: Path, proc: subprocess.Popen, timeout: float = 10.0) -> dict:
    """Poll for the handshake file, failing fast (with captured output) on early exit."""
    security = import_or_fail("cabal.webapi.security")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"cabal-backend exited early (code={proc.returncode}): {output}")
        data = security.read_handshake(path)
        if data is not None:
            return data
        time.sleep(0.05)
    pytest.fail(f"cabal-backend did not write a handshake file within {timeout}s")


def terminate_backend(proc: subprocess.Popen, timeout: float = 5.0) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
