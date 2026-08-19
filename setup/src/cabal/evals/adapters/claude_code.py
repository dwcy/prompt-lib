# -*- coding: utf-8 -*-
"""One-shot headless `claude -p` adapter: stream-json passthrough to the transcript, tree-kill timeout.

Per research.md R3 each repetition is a cold, independent trial — no persistent session — so this
adapter spawns one process per run and streams raw event lines verbatim to `spec.transcript_path`;
`metrics.py` owns all interpretation of those events.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import IO, Final

from cabal.evals.adapters import register
from cabal.evals.adapters.base import (
    FAILURE_AGENT_CRASH,
    FAILURE_AGENT_TIMEOUT,
    AdapterCapabilities,
    AdapterStatus,
    AdapterUnavailableError,
    AgentRunResult,
    AgentRunSpec,
)

ADAPTER_NAME: Final[str] = "claude-code"
EXECUTABLE: Final[str] = "claude"
CHECK_TIMEOUT_SECONDS: Final[int] = 30
EXIT_GRACE_SECONDS: Final[int] = 30
_READ_POLL_SECONDS: Final[float] = 0.1

BASE_FLAGS: Final[tuple[str, ...]] = ("--output-format", "stream-json", "--verbose")
PERMISSION_FLAGS: Final[tuple[str, ...]] = ("--permission-mode", "acceptEdits")
SKIP_PERMISSION_FLAGS: Final[tuple[str, ...]] = ("--dangerously-skip-permissions",)


def _build_command(executable: str, spec: AgentRunSpec) -> list[str]:
    command = [executable, "-p", spec.prompt, *BASE_FLAGS]
    command.extend(SKIP_PERMISSION_FLAGS if spec.skip_permissions else PERMISSION_FLAGS)
    if spec.model is not None:
        command.extend(("--model", spec.model))
    if spec.settings_file is not None:
        command.extend(("--settings", str(spec.settings_file)))
    return command


def _build_env(spec: AgentRunSpec) -> dict[str, str]:
    env = dict(os.environ)
    if spec.config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(spec.config_dir)
    env.update(spec.env)
    return env


def _kill_tree(process: subprocess.Popen[str]) -> None:
    """The `claude` shim spawns a node child that a plain kill() orphans, so kill the whole tree."""
    if process.poll() is None:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=EXIT_GRACE_SECONDS,
            )
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
    try:
        process.kill()
    except OSError:
        pass


def _pump(stream: IO[str], lines: "queue.Queue[str | None]") -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


def _parse_line(line: str) -> dict | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _classify(result_event: dict | None, exit_code: int | None, wall_seconds: float) -> AgentRunResult:
    """Per contracts/agent-adapter.md: `is_error` or exiting without a terminal result event is a crash.

    `final_text` keeps the result event's text even on error, so auth failures surface with their
    "Not logged in" message intact (research.md R2 RESOLVED note).
    """
    if result_event is None:
        return AgentRunResult(
            status="failed",
            failure_reason=FAILURE_AGENT_CRASH,
            final_text="",
            exit_code=exit_code,
            wall_seconds=wall_seconds,
        )
    raw = result_event.get("result")
    final_text = raw if isinstance(raw, str) else ""
    if result_event.get("is_error") or result_event.get("subtype") not in (None, "success"):
        return AgentRunResult(
            status="failed",
            failure_reason=FAILURE_AGENT_CRASH,
            final_text=final_text,
            exit_code=exit_code,
            wall_seconds=wall_seconds,
        )
    return AgentRunResult(
        status="completed",
        failure_reason=None,
        final_text=final_text,
        exit_code=exit_code,
        wall_seconds=wall_seconds,
    )


@dataclass(frozen=True)
class ClaudeCodeAdapter:
    """`AgentAdapter` implementation for the Claude Code CLI (registry key "claude-code")."""

    name: str = ADAPTER_NAME

    def check(self) -> AdapterStatus:
        """`--version` probe per contracts/agent-adapter.md. Never raises."""
        exe = shutil.which(EXECUTABLE)
        if exe is None:
            return AdapterStatus(
                adapter=self.name, available=False, detail=f"`{EXECUTABLE}` not found on PATH"
            )
        try:
            proc = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return AdapterStatus(adapter=self.name, available=False, detail=str(exc))
        if proc.returncode != 0:
            return AdapterStatus(
                adapter=self.name, available=False, detail=proc.stderr.strip()[:200]
            )
        return AdapterStatus(adapter=self.name, available=True, detail=proc.stdout.strip()[:80])

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(tokens=True, tool_calls=True, cost=True)

    def run(self, spec: AgentRunSpec) -> AgentRunResult:
        """One cold `claude -p` invocation; run-level failures land in the result, never raise."""
        exe = shutil.which(EXECUTABLE)
        if exe is None:
            raise AdapterUnavailableError(f"`{EXECUTABLE}` not found on PATH")
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                _build_command(exe, spec),
                cwd=spec.worktree,
                env=_build_env(spec),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=(sys.platform != "win32"),
            )
        except OSError as exc:
            raise AdapterUnavailableError(f"cannot start `{exe}`: {exc}") from exc
        return self._stream(process, spec, started)

    def _stream(
        self, process: subprocess.Popen[str], spec: AgentRunSpec, started: float
    ) -> AgentRunResult:
        assert process.stdout is not None
        lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=_pump, args=(process.stdout, lines), daemon=True).start()
        deadline = started + spec.timeout_seconds
        result_event: dict | None = None
        spec.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        with spec.transcript_path.open("a", encoding="utf-8", newline="\n") as transcript:
            while True:
                if time.monotonic() >= deadline:
                    _kill_tree(process)
                    return AgentRunResult(
                        status="failed",
                        failure_reason=FAILURE_AGENT_TIMEOUT,
                        final_text="",
                        exit_code=None,
                        wall_seconds=time.monotonic() - started,
                    )
                try:
                    line = lines.get(timeout=_READ_POLL_SECONDS)
                except queue.Empty:
                    continue
                if line is None:
                    break
                transcript.write(line if line.endswith("\n") else line + "\n")
                transcript.flush()
                event = _parse_line(line)
                if event is not None and event.get("type") == "result":
                    result_event = event
        exit_code = self._wait_exit(process)
        return _classify(result_event, exit_code, time.monotonic() - started)

    @staticmethod
    def _wait_exit(process: subprocess.Popen[str]) -> int | None:
        try:
            return process.wait(timeout=EXIT_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            return process.poll()


register(ADAPTER_NAME, ClaudeCodeAdapter)
