#!/usr/bin/env python3
"""Tests for command_guard.py's find-delete carve-out.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_command_guard_find_delete.py

A `find ... -delete` / `-exec rm` is only waved through when every file it
would touch is already tracked and identical to the last commit — genuinely
recoverable via git, not just "lives in a repo somewhere".
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
GUARD = HOOKS_DIR / "command_guard.py"


def run_hook(command: str, cwd: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")


class FindDeleteCarveOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_findguard_")).resolve()
        self.repo = self.parent / "repo"
        _init_repo(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def _commit_file(self, name: str, content: str = "hello\n") -> Path:
        target = self.repo / name
        target.write_text(content, encoding="utf-8")
        _git(self.repo, "add", name)
        _git(self.repo, "commit", "-q", "-m", "add " + name)
        return target

    def test_find_delete_on_tracked_clean_file_is_allowed(self):
        self._commit_file("keep.tmp")
        result = run_hook("find . -name '*.tmp' -delete", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_find_exec_rm_on_tracked_clean_file_is_allowed(self):
        self._commit_file("keep.tmp")
        result = run_hook(r"find . -name '*.tmp' -exec rm {} \;", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_find_delete_on_untracked_file_is_blocked(self):
        (self.repo / "scratch.tmp").write_text("new\n", encoding="utf-8")
        result = run_hook("find . -name '*.tmp' -delete", cwd=str(self.repo))
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        body = json.loads(result.stdout)
        self.assertIn("find", body["reason"].lower())

    def test_find_delete_on_modified_tracked_file_is_blocked(self):
        target = self._commit_file("keep.tmp")
        target.write_text("edited, not committed\n", encoding="utf-8")
        result = run_hook("find . -name '*.tmp' -delete", cwd=str(self.repo))
        self.assertEqual(result.returncode, 2, msg=result.stdout)

    def test_find_delete_outside_git_repo_is_blocked(self):
        loose = self.parent / "loose"
        loose.mkdir()
        (loose / "scratch.tmp").write_text("new\n", encoding="utf-8")
        result = run_hook("find . -name '*.tmp' -delete", cwd=str(loose))
        self.assertEqual(result.returncode, 2, msg=result.stdout)

    def test_find_delete_chained_with_other_command_is_blocked(self):
        self._commit_file("keep.tmp")
        result = run_hook("find . -name '*.tmp' -delete && echo done", cwd=str(self.repo))
        self.assertEqual(result.returncode, 2, msg=result.stdout)

    def test_find_delete_matching_nothing_is_allowed(self):
        result = run_hook("find . -name '*.doesnotexist' -delete", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_unrelated_command_is_unaffected(self):
        result = run_hook("git status --short", cwd=str(self.repo))
        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_commit_message_mentioning_find_delete_is_not_flagged(self):
        # A commit message describing this very feature must not itself trip
        # the detector — "find" only counts when it's an invoked command.
        result = run_hook(
            'git commit -m "feat: allow find-delete only when targets are clean"',
            cwd=str(self.repo),
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
