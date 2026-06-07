"""Hook contract tests: each global/hooks/*.py honors the JSON stdin contract,
tolerates malformed input, and respects the _gate runtime kill-switch.

Self-contained: invokes each hook as a subprocess (mirroring how Claude Code
calls them), so _gate.py resolves from the hook's own directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "global" / "hooks"

ALL_HOOKS = [
    "check_claude_update",
    "command_guard",
    "file_write_guard",
    "format_on_write",
    "post_tool_use",
    "pretool_task_isolation",
    "session_end",
    "session_end_release_lock",
    "session_start",
    "stop_session",
    "write_audit",
]

# Hooks that read a tool payload from stdin and must exit 0 on garbage input.
STDIN_DRIVEN_HOOKS = [
    "command_guard",
    "file_write_guard",
    "format_on_write",
    "post_tool_use",
    "pretool_task_isolation",
    "write_audit",
]

INJECTION_TRIGGER = "i" + "gnore previous instructions"
PROTECTED_FILE = str(Path.home() / ".claude" / "hooks" / "command_guard.py")


def _invoke(hook: str, payload, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = {**os.environ, **(env or {})}
    args = [sys.executable, str(HOOKS_DIR / f"{hook}.py")]
    if isinstance(payload, (bytes, bytearray)):
        return subprocess.run(
            args, input=bytes(payload), capture_output=True, env=merged, timeout=15
        )
    return subprocess.run(
        args,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=merged,
        timeout=15,
    )


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _write(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path}}


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


class TestHappyPath:
    def test_command_guard_allows_safe_bash(self):
        result = _invoke("command_guard", _bash("echo hi"))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_file_write_guard_allows_unprotected_path(self):
        result = _invoke("file_write_guard", _write(str(Path.home() / "notes.txt")))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_write_audit_appends_one_entry(self, fake_home):
        audit = fake_home / ".claude" / "write_audit.jsonl"
        result = _invoke(
            "write_audit",
            _write("/tmp/foo.txt"),
            env={"HOME": str(fake_home), "USERPROFILE": str(fake_home)},
        )
        assert result.returncode == 0
        lines = audit.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["tool"] == "Write"


class TestBlockPath:
    def test_command_guard_blocks_injection(self):
        result = _invoke("command_guard", _bash(INJECTION_TRIGGER))
        assert result.returncode == 2
        assert json.loads(result.stdout)["decision"] == "block"

    def test_file_write_guard_blocks_protected_file(self):
        result = _invoke("file_write_guard", _write(PROTECTED_FILE))
        assert result.returncode == 2
        assert json.loads(result.stdout)["decision"] == "block"


class TestMalformedJsonTolerance:
    @pytest.mark.parametrize("hook", STDIN_DRIVEN_HOOKS)
    def test_exits_zero_on_garbage_stdin(self, hook):
        assert _invoke(hook, b"not json").returncode == 0


class TestGate:
    @pytest.mark.parametrize("hook", ALL_HOOKS)
    def test_profile_off_exits_zero(self, hook):
        assert _invoke(hook, {}, env={"PROMPTLIB_HOOK_PROFILE": "off"}).returncode == 0

    @pytest.mark.parametrize("hook", ALL_HOOKS)
    def test_disabled_hooks_exits_zero(self, hook):
        assert _invoke(hook, {}, env={"PROMPTLIB_DISABLED_HOOKS": hook}).returncode == 0

    def test_disabled_guard_does_not_block_injection(self):
        result = _invoke(
            "command_guard",
            _bash(INJECTION_TRIGGER),
            env={"PROMPTLIB_DISABLED_HOOKS": "command_guard"},
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_unrelated_disabled_name_still_blocks(self):
        result = _invoke(
            "command_guard",
            _bash(INJECTION_TRIGGER),
            env={"PROMPTLIB_DISABLED_HOOKS": "other_hook"},
        )
        assert result.returncode == 2

    def test_profile_off_suppresses_write_audit_side_effect(self, fake_home):
        audit = fake_home / ".claude" / "write_audit.jsonl"
        env = {
            "HOME": str(fake_home),
            "USERPROFILE": str(fake_home),
            "PROMPTLIB_HOOK_PROFILE": "off",
        }
        result = _invoke("write_audit", _write("/tmp/foo.txt"), env=env)
        assert result.returncode == 0
        assert not audit.exists()
