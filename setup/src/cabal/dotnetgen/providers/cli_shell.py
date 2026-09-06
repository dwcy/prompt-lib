# -*- coding: utf-8 -*-
"""Subscription-auth adapter: drive the `claude` / `codex` CLIs instead of an API key.

Follows the `/cli-llm-app` skill's findings. Two shapes, because the tools differ:

* **claude** keeps a *persistent* stream-json session over stdin/stdout. Spawning a process per
  turn pays cold start every time; holding one open is roughly an order of magnitude faster.
* **codex** has only one-shot `exec` — there is no equivalent to `--input-format stream-json`
  that keeps a session alive, so each call is its own process.

Known limitation, recorded rather than hidden: the CLI takes a single prompt string, so the
banded messages are flattened and this path cannot place its own cache checkpoints. Cache
accounting on this provider is whatever the CLI reports (T014), not something we control.

**Every subprocess pipe pins `encoding="utf-8", errors="replace"`.** Without it Python decodes
with the platform default, which on Windows is cp1252 - and the first curly quote or em dash the
model emits kills the reader thread with a `UnicodeDecodeError`. The failure is especially nasty
because the exception surfaces on a background thread while the main thread waits on a queue that
will now never fill, so the symptom is a hang until the turn timeout rather than an error.
"""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Final

from cabal.dotnetgen.providers.base import (
    CompletionRequest,
    CompletionResult,
    Message,
    ProviderError,
    ProviderStatus,
    ProviderUnavailableError,
    Usage,
)
from cabal.dotnetgen.providers.config import StageBinding
from cabal.dotnetgen.providers.usage import parse_usage

PROVIDER_NAME: Final[str] = "cli_shell"
TURN_TIMEOUT_SECONDS: Final[int] = 600
CHECK_TIMEOUT_SECONDS: Final[int] = 30
_READ_POLL_SECONDS: Final[float] = 0.1
# Windows caps a command line at ~32767 chars; the prompt is one argv element,
# so an oversized architect prompt fails at spawn rather than reaching the model.
_MAX_CODEX_PROMPT_CHARS: Final[int] = 30_000

CLAUDE_FLAGS: Final[tuple[str, ...]] = (
    "--print",
    "--verbose",
    "--input-format",
    "stream-json",
    "--output-format",
    "stream-json",
    "--permission-mode",
    "plan",
    "--no-session-persistence",
)
CODEX_FLAGS: Final[tuple[str, ...]] = ("exec", "--sandbox", "read-only")


class CliShellError(ProviderError):
    """A CLI invocation failed."""


def resolve_cli(model: str) -> str:
    """Infer which CLI serves a model id. Aliases are unreliable, so ids must be explicit."""
    if model.startswith("claude"):
        return "claude"
    if model.startswith(("gpt", "o1", "o3", "o4")):
        return "codex"
    raise CliShellError(
        f"cannot infer a CLI for model {model!r}; use a full id such as "
        "'claude-opus-5' or 'gpt-5'"
    )


def flatten(messages: tuple[Message, ...]) -> str:
    """Collapse banded messages into the single prompt string the CLIs accept."""
    parts: list[str] = []
    for message in messages:
        if message.role == "user":
            parts.append(message.content)
        else:
            parts.append(f"[{message.role}]\n{message.content}")
    return "\n\n".join(parts)


def extract_result(event: dict) -> tuple[str, Usage, float | None]:
    """Pull text, usage and cost from a stream-json `result` event (T014).

    `result.result` is the assembled reply and `is_error` is the canonical failure flag, per the
    documented schema. Usage field names vary, so normalisation is delegated to `parse_usage`,
    which reports absence rather than substituting a zero.

    Cost is None when the event carries none. Returning 0.0 there and letting the caller coerce
    it back with `cost if cost else None` loses the distinction twice over: an unreported cost
    becomes a measured zero, and a genuine measured zero -- what a locally hosted model actually
    costs -- becomes "unknown". SC-010 reconciles against this figure, and a fabricated zero is
    not a report.
    """
    if event.get("is_error") or event.get("subtype") not in (None, "success"):
        detail = event.get("result") or event.get("subtype") or "unknown error"
        raise CliShellError(f"CLI reported an error: {detail}")

    text = event.get("result")
    if not isinstance(text, str):
        raise CliShellError("result event carried no text")

    usage = parse_usage(event.get("usage"))
    cost = event.get("total_cost_usd")
    return text, usage, float(cost) if isinstance(cost, (int, float)) else None


@dataclass
class ClaudeSession:
    """One long-lived `claude` process. Reused across turns; the caller owns its lifetime."""

    model: str
    executable: str
    _process: subprocess.Popen[str] | None = field(default=None, repr=False)
    _lines: "queue.Queue[str | None]" = field(default_factory=queue.Queue, repr=False)
    _reader: threading.Thread | None = field(default=None, repr=False)

    def start(self) -> None:
        if self._process is not None:
            return
        command = [self.executable, *CLAUDE_FLAGS, "--model", self.model]
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise ProviderUnavailableError(f"cannot start `{self.executable}`: {exc}") from exc

        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        # Bind both locally. `_discard_pending` swaps in a fresh queue after a timed-out turn,
        # and a reader still draining the old process would otherwise start writing into that
        # new queue -- leaking the dead turn's events into the next prompt's answer. Holding a
        # reference to its own queue means an orphaned reader can only talk to itself.
        stdout, lines = self._process.stdout, self._lines
        for line in stdout:
            lines.put(line)
        lines.put(None)

    def send(self, prompt: str, timeout: int = TURN_TIMEOUT_SECONDS) -> dict:
        """Write one user event and read events until the turn's `result` arrives."""
        self.start()
        assert self._process is not None and self._process.stdin is not None

        event = {"type": "user", "message": {"role": "user", "content": prompt}}
        try:
            self._process.stdin.write(json.dumps(event) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise ProviderUnavailableError(f"`{self.executable}` session closed: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._lines.get(timeout=_READ_POLL_SECONDS)
            except queue.Empty:
                continue
            if line is None:
                raise ProviderUnavailableError(f"`{self.executable}` exited mid-turn")
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if parsed.get("type") == "result":
                return parsed

        # The process is still working on this turn and will queue its `result`
        # later; a reused session would hand that stale event to the next prompt.
        self.close()
        self._discard_pending()
        raise CliShellError(f"`{self.executable}` did not complete a turn in {timeout}s")

    def _discard_pending(self) -> None:
        """Drop anything the reader queued for a turn nobody is waiting on any more."""
        self._lines = queue.Queue()

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
            self._process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
        finally:
            self._process = None


@dataclass
class CliShellProvider:
    """Stage-bindable adapter over the `claude` / `codex` CLIs. Needs no API key."""

    binding: StageBinding
    name: str = PROVIDER_NAME
    _session: ClaudeSession | None = field(default=None, repr=False)

    @property
    def cli(self) -> str:
        return resolve_cli(self.binding.model)

    def _executable(self) -> str:
        exe = shutil.which(self.cli)
        if exe is None:
            raise ProviderUnavailableError(f"`{self.cli}` not found on PATH")
        return exe

    def complete(self, request: CompletionRequest) -> CompletionResult:
        prompt = flatten(request.messages)
        started = time.monotonic()

        if self.cli == "claude":
            text, usage, cost = extract_result(self._claude_turn(prompt))
            # Passed through as-is: `cost if cost else None` would report a genuine measured
            # zero as unknown, which is the conflation the ledger exists to prevent.
            reported = cost
        else:
            text, usage, _cost = self._codex_turn(prompt)
            # codex exec reports no usage or cost, so there is nothing to reconcile against.
            reported = None

        return CompletionResult(
            text=text,
            usage=usage,
            model=request.model,
            provider=self.name,
            wall_clock_seconds=time.monotonic() - started,
            reported_cost_usd=reported,
        )

    def _claude_turn(self, prompt: str) -> dict:
        if self._session is None:
            self._session = ClaudeSession(model=self.binding.model, executable=self._executable())
        return self._session.send(prompt)

    def _codex_turn(self, prompt: str) -> tuple[str, Usage, float]:
        """One-shot: codex `exec` has no persistent-session mode."""
        if len(prompt) > _MAX_CODEX_PROMPT_CHARS:
            raise CliShellError(
                f"prompt of {len(prompt)} chars exceeds the {_MAX_CODEX_PROMPT_CHARS}-char "
                "codex command-line budget; reduce the context sent to this stage"
            )
        command = [self._executable(), *CODEX_FLAGS, "-m", self.binding.model, prompt]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TURN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliShellError(f"`codex` timed out after {TURN_TIMEOUT_SECONDS}s") from exc
        except OSError as exc:
            raise ProviderUnavailableError(f"cannot run `codex`: {exc}") from exc

        if proc.returncode != 0:
            raise CliShellError(f"`codex` exited {proc.returncode}: {proc.stderr[:400]}")
        # codex exec emits plain text and reports no token usage, so caching is unmeasurable here.
        return proc.stdout.strip(), Usage(cache_reported=False), 0.0

    def check(self) -> ProviderStatus:
        """Confirm the CLI exists and runs. Never raises."""
        try:
            exe = self._executable()
        except ProviderUnavailableError as exc:
            return ProviderStatus(self.name, self.binding.model, reachable=False, detail=str(exc))

        try:
            proc = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CHECK_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return ProviderStatus(self.name, self.binding.model, reachable=False, detail=str(exc))

        if proc.returncode != 0:
            return ProviderStatus(
                self.name, self.binding.model, reachable=False, detail=proc.stderr.strip()[:200]
            )
        return ProviderStatus(
            self.name, self.binding.model, reachable=True, detail=proc.stdout.strip()[:80]
        )

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
