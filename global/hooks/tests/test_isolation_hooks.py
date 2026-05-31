#!/usr/bin/env python3
"""Tests for the parallel-isolation hook trio.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_isolation_hooks.py

Each test method is named after the rule it verifies, mirroring the labels
in docs/parallel-isolation.md "Runtime enforcement" and docs/hooks.md.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
PRETOOL = HOOKS_DIR / "pretool_task_isolation.py"
SESSION_START = HOOKS_DIR / "session_start.py"
SESSION_END_RELEASE = HOOKS_DIR / "session_end_release_lock.py"


def run_hook(
    script: Path,
    stdin: str = "",
    cwd: Path | None = None,
    env_overrides: dict | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
        timeout=60,
    )


def _init_repo(repo: Path, branch: str) -> None:
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", branch], check=True)


def _write_lock(repo: Path, branch: str, cwd_value: str, pid: int) -> Path:
    lock_dir = repo / ".git" / "claude-session-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{branch}.json"
    lock_path.write_text(
        json.dumps({
            "pid": pid,
            "started_at": "2026-01-01T00:00:00+00:00",
            "cwd": cwd_value,
        }),
        encoding="utf-8",
    )
    return lock_path


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


class PreToolUseTaskGuardrailTests(unittest.TestCase):
    def _payload(self, **tool_input) -> str:
        return json.dumps({"tool_name": "Task", "tool_input": tool_input})

    def test_read_only_subagent_is_exempt(self):
        for agent in [
            "Explore", "Plan", "claude-code-guide", "statusline-setup",
            "code-plan-verifier", "gitignore-auditor", "github-config-manager",
            "load-project", "secret-auditor",
        ]:
            with self.subTest(agent=agent):
                result = run_hook(
                    PRETOOL,
                    self._payload(subagent_type=agent, run_in_background=True),
                )
                self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_foreground_dispatch_is_exempt_v1_gap(self):
        result = run_hook(
            PRETOOL,
            self._payload(subagent_type="python-architect", run_in_background=False),
        )
        self.assertEqual(result.returncode, 0)

    def test_background_writer_with_worktree_isolation_is_allowed(self):
        result = run_hook(
            PRETOOL,
            self._payload(
                subagent_type="python-architect",
                run_in_background=True,
                isolation="worktree",
            ),
        )
        self.assertEqual(result.returncode, 0)

    def test_background_writer_without_isolation_is_blocked(self):
        result = run_hook(
            PRETOOL,
            self._payload(subagent_type="python-architect", run_in_background=True),
        )
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["decision"], "block")
        self.assertIn("isolation", body["reason"])
        self.assertIn("python-architect", body["reason"])

    def test_non_task_tool_passes_through(self):
        result = run_hook(PRETOOL, json.dumps({"tool_name": "Write", "tool_input": {}}))
        self.assertEqual(result.returncode, 0)

    def test_malformed_input_fails_open(self):
        result = run_hook(PRETOOL, "not json")
        self.assertEqual(result.returncode, 0)


class SessionStartLockLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_iso_")).resolve()
        self.repo = self.parent / "myrepo"
        self.repo.mkdir()
        _init_repo(self.repo, "feat-test")
        self.repo = self.repo.resolve()

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def _lock_path(self, branch: str = "feat-test") -> Path:
        return self.repo / ".git" / "claude-session-locks" / f"{branch}.json"

    def _branches(self) -> list[str]:
        out = subprocess.run(
            ["git", "-C", str(self.repo), "branch", "--list", "--format=%(refname:short)"],
            capture_output=True, text=True, check=True,
        ).stdout
        return [b.strip() for b in out.splitlines() if b.strip()]

    def test_first_feature_branch_session_claims_lock(self):
        result = run_hook(SESSION_START, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self._lock_path().exists())
        data = json.loads(self._lock_path().read_text(encoding="utf-8"))
        self.assertEqual(Path(data["cwd"]).resolve(), self.repo)
        self.assertIsInstance(data["pid"], int)

    def test_main_branch_session_skips_lock(self):
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "-q", "-b", "main"], check=True
        )
        result = run_hook(SESSION_START, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.repo / ".git" / "claude-session-locks" / "main.json").exists())

    def test_colliding_session_creates_sibling_worktree(self):
        _write_lock(self.repo, "feat-test", "/some/other/cwd", pid=os.getpid())
        result = run_hook(SESSION_START, cwd=self.repo)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        emitted = json.loads(result.stdout)
        self.assertIn("additionalContext", emitted)
        self.assertIn("Stop", emitted["additionalContext"])
        self.assertIn("feat-test-s2", emitted["additionalContext"])

        self.assertIn("feat-test-s2", self._branches())
        sibling = self.parent / "myrepo-feat-test-s2"
        self.assertTrue(sibling.exists(), msg=f"expected sibling worktree at {sibling}")

    def test_colliding_session_does_not_overwrite_holder_lock(self):
        _write_lock(self.repo, "feat-test", "/some/other/cwd", pid=os.getpid())
        run_hook(SESSION_START, cwd=self.repo)
        data = json.loads(self._lock_path().read_text(encoding="utf-8"))
        self.assertEqual(data["cwd"], "/some/other/cwd")

    def test_claude_worktree_auto_zero_emits_warning_only(self):
        _write_lock(self.repo, "feat-test", "/some/other/cwd", pid=os.getpid())
        result = run_hook(
            SESSION_START, cwd=self.repo, env_overrides={"CLAUDE_WORKTREE_AUTO": "0"}
        )
        self.assertEqual(result.returncode, 0)
        emitted = json.loads(result.stdout)
        self.assertIn("CLAUDE_WORKTREE_AUTO=0", emitted["additionalContext"])
        self.assertNotIn("feat-test-s2", self._branches())

    def test_stale_lock_is_reclaimed(self):
        _write_lock(self.repo, "feat-test", "/some/other/cwd", pid=_dead_pid())
        result = run_hook(SESSION_START, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        data = json.loads(self._lock_path().read_text(encoding="utf-8"))
        self.assertEqual(Path(data["cwd"]).resolve(), self.repo)
        self.assertNotIn("feat-test-s2", self._branches())


class SessionEndLockReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_iso_")).resolve()
        self.repo = self.parent / "myrepo"
        self.repo.mkdir()
        _init_repo(self.repo, "feat-test")
        self.repo = self.repo.resolve()

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def _lock_path(self) -> Path:
        return self.repo / ".git" / "claude-session-locks" / "feat-test.json"

    def test_session_end_release_lock_deletes_own_lock(self):
        _write_lock(self.repo, "feat-test", str(self.repo), pid=os.getpid())
        result = run_hook(SESSION_END_RELEASE, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self._lock_path().exists())

    def test_session_end_release_lock_leaves_foreign_lock_alone(self):
        _write_lock(self.repo, "feat-test", "/not/our/cwd", pid=os.getpid())
        result = run_hook(SESSION_END_RELEASE, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self._lock_path().exists())

    def test_session_end_release_lock_noop_when_no_lock_exists(self):
        result = run_hook(SESSION_END_RELEASE, cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self._lock_path().exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
