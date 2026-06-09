#!/usr/bin/env python3
"""Tests for pretool_branch_guard.py — block Write/Edit on a refused branch.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_branch_guard.py

Mirrors the "branch before starting work" rule enforced at PreToolUse time.
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
GUARD = HOOKS_DIR / "pretool_branch_guard.py"


def run_hook(
    stdin: str, env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _init_repo(repo: Path, branch: str) -> None:
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-B", branch], check=True)


def _payload(file_path: str, tool: str = "Write") -> str:
    return json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path}})


class BranchGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_branchguard_")).resolve()
        self.repo = self.parent / "repo"
        self.repo.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def test_write_on_main_is_blocked(self):
        _init_repo(self.repo, "main")
        result = run_hook(_payload(str(self.repo / "file.py")))
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        body = json.loads(result.stdout)
        self.assertEqual(body["decision"], "block")
        self.assertIn("main", body["reason"])

    def test_edit_on_master_is_blocked(self):
        _init_repo(self.repo, "master")
        result = run_hook(_payload(str(self.repo / "file.py"), tool="Edit"))
        self.assertEqual(result.returncode, 2)

    def test_new_nested_file_on_main_is_blocked(self):
        _init_repo(self.repo, "main")
        result = run_hook(_payload(str(self.repo / "a" / "b" / "new.py")))
        self.assertEqual(result.returncode, 2)

    def test_write_on_feature_branch_is_allowed(self):
        _init_repo(self.repo, "feat/thing")
        result = run_hook(_payload(str(self.repo / "file.py")))
        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_path_outside_any_repo_is_allowed(self):
        result = run_hook(_payload(str(self.parent / "loose.txt")))
        self.assertEqual(result.returncode, 0)

    def test_non_write_tool_passes_through(self):
        _init_repo(self.repo, "main")
        result = run_hook(_payload(str(self.repo / "file.py"), tool="Bash"))
        self.assertEqual(result.returncode, 0)

    def test_missing_file_path_passes_through(self):
        result = run_hook(json.dumps({"tool_name": "Write", "tool_input": {}}))
        self.assertEqual(result.returncode, 0)

    def test_malformed_input_fails_open(self):
        result = run_hook("not json")
        self.assertEqual(result.returncode, 0)

    def test_should_skip_env_bypasses_block_on_main(self):
        _init_repo(self.repo, "main")
        result = run_hook(
            _payload(str(self.repo / "file.py")),
            env_overrides={"PROMPTLIB_DISABLED_HOOKS": "pretool_branch_guard"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
