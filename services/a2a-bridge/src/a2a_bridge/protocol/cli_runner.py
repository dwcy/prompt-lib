"""CLI-agnostic NDJSON subprocess runner (T025).

Spawns an arbitrary CLI via ``asyncio.create_subprocess_exec``, parses its
stdout line-by-line as NDJSON, translates each event into an :class:`Artifact`
through a caller-supplied parser, and yields A2A ``task.state`` /
``task.artifact`` events that drive the lifecycle in
``contracts/sse-events.md``.

The runner is intentionally CLI-agnostic so the Phase 4 Claude adapter can reuse
it unchanged; the only Gemini-specific bits live in
``a2a_bridge.adapters.gemini.runner``.

Failure modes (driven by the contract tests in
``tests/contract/test_jsonrpc_methods_send_subscribe.py``):

* exit != 0 → ``failed`` with ``reason="cli_nonzero_exit"``,
  ``exit_code``, and the last 1024 bytes of stderr in ``stderr_tail``.
* malformed stdout line → ``failed`` with ``reason="cli_malformed_output"``.
* per-task timeout elapsed → ``cancelled`` with ``reason="timeout"``.
* external transition to ``cancelled`` (e.g. from ``tasks/cancel``) →
  ``cancelled`` with ``reason="client_cancelled"``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from a2a_bridge.protocol.logging import log_cli_exit
from a2a_bridge.protocol.sse import TaskArtifactEvent, TaskStateEvent
from a2a_bridge.protocol.tasks import Artifact, Task, TaskState

_STDERR_TAIL_BYTES = 1024
_TERMINATE_GRACE_SECONDS = 2.0
_TERMINAL_TASK_STATES = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _state_event(task: Task, **fields: object) -> TaskStateEvent:
    return TaskStateEvent(
        task_id=str(task.id),
        state=task.state.value,
        ts=_now_iso(),
        **fields,
    )


def _artifact_event(task: Task, artifact: Artifact) -> TaskArtifactEvent:
    return TaskArtifactEvent(
        task_id=str(task.id),
        artifact=artifact.model_dump(mode="json"),
    )


class CliRunner:
    def __init__(
        self,
        *,
        cli_command_factory: Callable[[str], list[str]],
        parse_event: Callable[[dict], Artifact | None],
        task_timeout_seconds: float,
    ) -> None:
        self._cli_command_factory = cli_command_factory
        self._parse_event = parse_event
        self._task_timeout_seconds = task_timeout_seconds

    async def run(
        self, prompt: str, task: Task
    ) -> AsyncIterator[TaskStateEvent | TaskArtifactEvent]:
        yield _state_event(task)

        argv = self._cli_command_factory(prompt)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            task.transition(TaskState.WORKING)
            yield _state_event(task)
            task.process = None
            task.transition(TaskState.FAILED)
            log_cli_exit(str(task.id), outcome="failure", exit_code=None)
            yield _state_event(
                task, reason="cli_spawn_failed", stderr_tail=str(exc)[-_STDERR_TAIL_BYTES:]
            )
            return

        task.process = process
        task.transition(TaskState.WORKING)
        yield _state_event(task)

        stderr_buffer = bytearray()
        stderr_task = asyncio.create_task(_drain_stderr(process, stderr_buffer))

        outcome: str | None = None
        try:
            async for event_or_outcome in self._consume_stdout(process, task):
                if isinstance(event_or_outcome, TaskArtifactEvent):
                    yield event_or_outcome
                else:
                    outcome = event_or_outcome
        except asyncio.CancelledError:
            await _kill_process(process)
            raise
        finally:
            await _await_stderr(stderr_task)

        if outcome is None:
            outcome = await self._await_exit(process)

        if task.state in _TERMINAL_TASK_STATES:
            log_cli_exit(
                str(task.id),
                outcome=_log_outcome(task.state),
                exit_code=process.returncode,
            )
            yield _state_event(task, reason="client_cancelled")
            return

        async for event in self._finalise(task, process, outcome, stderr_buffer):
            yield event

    async def _consume_stdout(
        self, process: asyncio.subprocess.Process, task: Task
    ) -> AsyncIterator[TaskArtifactEvent | str]:
        deadline = asyncio.get_running_loop().time() + self._task_timeout_seconds
        assert process.stdout is not None
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await _kill_process(process)
                yield "cancelled:timeout"
                return
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
            except TimeoutError:
                await _kill_process(process)
                yield "cancelled:timeout"
                return

            if not line:
                return

            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                await _kill_process(process)
                yield "failed:cli_malformed_output"
                return

            artifact = self._parse_event(payload)
            if artifact is None:
                continue

            try:
                task.add_artifact(artifact)
            except Exception:
                continue
            yield _artifact_event(task, artifact)

    async def _await_exit(self, process: asyncio.subprocess.Process) -> str:
        try:
            await asyncio.wait_for(process.wait(), timeout=_TERMINATE_GRACE_SECONDS)
        except TimeoutError:
            await _kill_process(process)
        if process.returncode == 0:
            return "completed"
        return "failed:cli_nonzero_exit"

    async def _finalise(
        self,
        task: Task,
        process: asyncio.subprocess.Process,
        outcome: str,
        stderr_buffer: bytearray,
    ) -> AsyncIterator[TaskStateEvent | TaskArtifactEvent]:
        kind, _, reason = outcome.partition(":")
        # The runner has already reaped the subprocess (or seen it exit). Clear
        # the Task's process reference so its terminal-transition reaper does
        # not try to terminate an already-dead handle (ProcessLookupError on
        # Windows, where the transport closes synchronously on exit).
        task.process = None

        if kind == "completed":
            task.transition(TaskState.COMPLETED)
            log_cli_exit(str(task.id), outcome="success", exit_code=process.returncode)
            yield _state_event(task)
            return

        if kind == "failed":
            task.transition(TaskState.FAILED)
            stderr_tail = _format_stderr_tail(stderr_buffer)
            log_cli_exit(
                str(task.id),
                outcome="failure",
                exit_code=process.returncode,
            )
            yield _state_event(
                task,
                reason=reason or "cli_nonzero_exit",
                exit_code=process.returncode,
                stderr_tail=stderr_tail,
            )
            return

        if kind == "cancelled":
            task.transition(TaskState.CANCELLED)
            log_cli_exit(
                str(task.id),
                outcome="timeout" if reason == "timeout" else "failure",
                exit_code=process.returncode,
            )
            yield _state_event(task, reason=reason or "client_cancelled")
            return

        task.transition(TaskState.FAILED)
        log_cli_exit(str(task.id), outcome="failure", exit_code=process.returncode)
        yield _state_event(task, reason="unknown_outcome")


def _format_stderr_tail(buffer: bytearray) -> str | None:
    if not buffer:
        return None
    tail_bytes = bytes(buffer[-_STDERR_TAIL_BYTES:])
    return tail_bytes.decode("utf-8", errors="replace").strip() or None


def _log_outcome(state: TaskState) -> str:
    if state is TaskState.COMPLETED:
        return "success"
    return "failure"


async def _drain_stderr(
    process: asyncio.subprocess.Process, buffer: bytearray
) -> None:
    if process.stderr is None:
        return
    try:
        while True:
            chunk = await process.stderr.read(1024)
            if not chunk:
                return
            buffer.extend(chunk)
            if len(buffer) > _STDERR_TAIL_BYTES * 4:
                del buffer[: len(buffer) - _STDERR_TAIL_BYTES * 2]
    except asyncio.CancelledError:
        return


async def _await_stderr(stderr_task: asyncio.Task[None]) -> None:
    try:
        await asyncio.wait_for(stderr_task, timeout=_TERMINATE_GRACE_SECONDS)
    except (TimeoutError, asyncio.CancelledError):
        stderr_task.cancel()
        try:
            await stderr_task
        except (asyncio.CancelledError, Exception):
            pass


async def _kill_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=_TERMINATE_GRACE_SECONDS)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            return
        try:
            await process.wait()
        except Exception:
            pass
