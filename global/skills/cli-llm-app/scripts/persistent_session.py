"""Persistent Claude Code CLI session — reference implementation.

Drop-in module for any Python app that wants to talk to the local `claude`
CLI as a long-lived chat backend (subscription-auth, no API key needed).
Cold start (~5–15s on Windows) is paid once at construction; subsequent
turns are pure inference (~1–2s).

Usage:
    from persistent_session import ClaudeSession, SessionError

    session = ClaudeSession(
        system_prompt="You are a helpful assistant. Reply concisely.",
        model="claude-haiku-4-5",
    )
    try:
        reply = session.ask("Hi!")
        reply2 = session.ask("What did I just say?")  # history is preserved
    finally:
        session.close()

Adapt freely — `SYSTEM_PROMPT` and the model are the main knobs. For
structured output, embed your JSON schema rules in `system_prompt` and
validate `reply` with pydantic / dataclasses / your validator of choice.
"""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading


class SessionError(RuntimeError):
    """Raised when the persistent claude session can't fulfil a request."""


DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_TIMEOUT_S = 120.0


class ClaudeSession:
    """A long-lived `claude` CLI subprocess driven via stream-json NDJSON.

    Threading model: one background reader thread consumes stdout events
    and pushes `result` events into a queue. `ask()` writes a `user` event
    to stdin (under a lock) then blocks on the queue for the matching
    result. One `ask()` may be in flight at a time.
    """

    def __init__(
        self,
        system_prompt: str,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        # Windows: npm-installed CLIs are .cmd shims; subprocess won't find
        # them without an explicit absolute path.
        exe = shutil.which("claude")
        if exe is None:
            raise SessionError("claude CLI not found on PATH")

        self._timeout_s = timeout_s
        argv = [
            exe,
            "--print",
            # --verbose is mandatory when output-format=stream-json with --print.
            "--verbose",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--model", model,
            "--permission-mode", "plan",
            "--no-session-persistence",
            # Strip startup overhead that doesn't apply to an app backend.
            # These keep OAuth/keychain auth working (unlike --bare).
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--tools", "",
            "--system-prompt", system_prompt,
        ]
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._send_lock = threading.Lock()
        self._results: queue.Queue = queue.Queue()
        self._dead = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        try:
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "result":
                    self._results.put(ev)
        finally:
            self._dead.set()
            self._results.put(None)  # unblock any waiting ask()

    def ask(self, user_message: str, timeout: float | None = None) -> str:
        """Send one user message and return the assistant reply text.

        Raises SessionError if the session is dead or returns a non-success
        result. The caller is responsible for any further parsing (e.g.
        extracting structured JSON from the reply).
        """
        if self._dead.is_set():
            raise SessionError("session is dead")
        event = {
            "type": "user",
            "message": {"role": "user", "content": user_message},
        }
        wait_for = timeout if timeout is not None else self._timeout_s
        with self._send_lock:
            try:
                assert self._proc.stdin is not None
                self._proc.stdin.write(json.dumps(event) + "\n")
                self._proc.stdin.flush()
            except (OSError, ValueError) as error:
                self._dead.set()
                raise SessionError(f"write to claude failed: {error}") from error
            try:
                result_ev = self._results.get(timeout=wait_for)
            except queue.Empty as error:
                raise SessionError("claude timed out waiting for result") from error
        if result_ev is None:
            raise SessionError("claude session died before producing a result")
        if result_ev.get("subtype") != "success" or result_ev.get("is_error"):
            detail = (
                result_ev.get("result")
                or result_ev.get("subtype")
                or "unknown error"
            )
            raise SessionError(f"claude returned error: {detail}")
        text = result_ev.get("result")
        if not isinstance(text, str) or not text.strip():
            raise SessionError("claude returned empty result")
        return text

    def is_alive(self) -> bool:
        return not self._dead.is_set() and self._proc.poll() is None

    def close(self) -> None:
        try:
            if self._proc.stdin is not None and not self._proc.stdin.closed:
                self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self._proc.kill()
            except OSError:
                pass


def _smoke_test() -> None:
    """Quick sanity check: prove cold-start-once and history-preserved."""
    import time

    s = ClaudeSession(
        system_prompt="You are a terse assistant. Reply in <=10 words.",
    )
    try:
        t0 = time.perf_counter()
        r1 = s.ask("Say the word ALPHA.")
        t1 = time.perf_counter()
        r2 = s.ask("Now say BETA.")
        t2 = time.perf_counter()
        r3 = s.ask("What was the first word I asked you to say?")
        t3 = time.perf_counter()
        print(f"turn 1 (cold start): {t1 - t0:5.2f}s  -> {r1!r}")
        print(f"turn 2 (warm)      : {t2 - t1:5.2f}s  -> {r2!r}")
        print(f"turn 3 (history)   : {t3 - t2:5.2f}s  -> {r3!r}")
        assert "ALPHA" in r3.upper(), "history was not preserved across turns"
        print("OK — persistent session works and remembers turn 1.")
    finally:
        s.close()


if __name__ == "__main__":
    _smoke_test()
