#!/usr/bin/env python3
"""Tests for pretool_inflight_guard.py — warn once before editing someone else's dirty file.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_inflight_guard.py

The behaviour under test is the one the per-branch session lock cannot provide: uncommitted
work left behind by a session that already exited has no live lock holder, so the only signal
is that the file was already dirty when this session started.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
GUARD = HOOKS_DIR / "pretool_inflight_guard.py"
STATE_DIR = "claude-inflight"


def run_hook(stdin: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
    (repo / "other.txt").write_text("committed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "checkout", "-q", "-B", "feat/thing")


def _payload(file_path: str, session: str = "s1", tool: str = "Write") -> str:
    return json.dumps(
        {"tool_name": tool, "session_id": session, "tool_input": {"file_path": file_path}}
    )


class InflightGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_inflight_")).resolve()
        self.repo = self.parent / "repo"
        self.repo.mkdir()
        _init_repo(self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def _dirty(self, name: str = "tracked.txt") -> Path:
        path = self.repo / name
        path.write_text("someone else's uncommitted work\n", encoding="utf-8")
        return path

    def test_editing_a_file_dirty_before_the_session_is_blocked_once(self):
        target = self._dirty()

        first = run_hook(_payload(str(target)))
        self.assertEqual(first.returncode, 2, msg=first.stdout)
        body = json.loads(first.stdout)
        self.assertEqual(body["decision"], "block")
        self.assertIn("tracked.txt", body["reason"])

    def test_the_second_attempt_on_the_same_file_proceeds(self):
        target = self._dirty()

        self.assertEqual(run_hook(_payload(str(target))).returncode, 2)
        second = run_hook(_payload(str(target)))

        self.assertEqual(second.returncode, 0, msg=second.stdout)

    def test_the_warning_names_the_irreversible_risk(self):
        target = self._dirty()

        body = json.loads(run_hook(_payload(str(target))).stdout)

        self.assertIn("checkout", body["reason"])
        self.assertIn("destroys it permanently", body["reason"])

    def test_a_clean_tracked_file_is_never_blocked(self):
        self._dirty("tracked.txt")

        result = run_hook(_payload(str(self.repo / "other.txt")))

        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_a_file_this_session_dirties_after_the_snapshot_is_not_blocked(self):
        self._dirty("tracked.txt")
        # Snapshot is taken on this first call, while other.txt is still clean.
        run_hook(_payload(str(self.repo / "tracked.txt")))

        self._dirty("other.txt")
        result = run_hook(_payload(str(self.repo / "other.txt")))

        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_an_untracked_file_from_another_session_is_blocked(self):
        stray = self.repo / "left_behind.py"
        stray.write_text("work from an exited session\n", encoding="utf-8")

        result = run_hook(_payload(str(stray)))

        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertIn("left_behind.py", json.loads(result.stdout)["reason"])

    def test_an_untracked_file_inside_a_new_directory_is_matched(self):
        nested = self.repo / "brand_new" / "deep" / "file.py"
        nested.parent.mkdir(parents=True)
        nested.write_text("work from an exited session\n", encoding="utf-8")

        result = run_hook(_payload(str(nested)))

        self.assertEqual(result.returncode, 2, msg=result.stdout)

    def test_a_gitignored_file_is_not_treated_as_someone_elses_work(self):
        (self.repo / ".gitignore").write_text("build/\n", encoding="utf-8")
        _git(self.repo, "add", ".gitignore")
        _git(self.repo, "commit", "-q", "-m", "ignore build")
        artifact = self.repo / "build" / "out.js"
        artifact.parent.mkdir()
        artifact.write_text("generated\n", encoding="utf-8")

        result = run_hook(_payload(str(artifact)))

        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_a_staged_change_still_counts_as_unrecoverable_work(self):
        target = self._dirty()
        _git(self.repo, "add", "tracked.txt")

        result = run_hook(_payload(str(target)))

        self.assertEqual(result.returncode, 2, msg=result.stdout)

    def test_each_session_gets_its_own_snapshot_and_its_own_warning(self):
        target = self._dirty()
        self.assertEqual(run_hook(_payload(str(target), session="s1")).returncode, 2)
        self.assertEqual(run_hook(_payload(str(target), session="s1")).returncode, 0)

        other_session = run_hook(_payload(str(target), session="s2"))

        self.assertEqual(other_session.returncode, 2, msg=other_session.stdout)

    def test_the_snapshot_is_written_under_the_git_common_dir(self):
        run_hook(_payload(str(self._dirty())))

        snapshots = list((self.repo / ".git" / STATE_DIR).glob("*.json"))

        self.assertEqual(len(snapshots), 1)
        state = json.loads(snapshots[0].read_text(encoding="utf-8"))
        self.assertIn("tracked.txt", state["baseline"])
        self.assertIn("tracked.txt", state["acknowledged"])

    def test_edit_and_notebookedit_are_guarded_too(self):
        target = self._dirty()

        edit = run_hook(_payload(str(target), session="e1", tool="Edit"))
        notebook = run_hook(_payload(str(target), session="n1", tool="NotebookEdit"))

        self.assertEqual(edit.returncode, 2, msg=edit.stdout)
        self.assertEqual(notebook.returncode, 2, msg=notebook.stdout)

    def test_a_non_write_tool_passes_through(self):
        target = self._dirty()

        result = run_hook(_payload(str(target), tool="Bash"))

        self.assertEqual(result.returncode, 0)

    def test_a_path_outside_any_repo_is_allowed(self):
        loose = self.parent / "loose.txt"
        loose.write_text("x", encoding="utf-8")

        result = run_hook(_payload(str(loose)))

        self.assertEqual(result.returncode, 0)

    def test_a_clean_repo_never_blocks_anything(self):
        result = run_hook(_payload(str(self.repo / "tracked.txt")))

        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_missing_file_path_passes_through(self):
        result = run_hook(json.dumps({"tool_name": "Write", "tool_input": {}}))

        self.assertEqual(result.returncode, 0)

    def test_malformed_input_fails_open(self):
        result = run_hook("not json")

        self.assertEqual(result.returncode, 0)

    def test_should_skip_env_bypasses_the_block(self):
        target = self._dirty()

        result = run_hook(
            _payload(str(target)),
            env_overrides={"PROMPTLIB_DISABLED_HOOKS": "pretool_inflight_guard"},
        )

        self.assertEqual(result.returncode, 0, msg=result.stdout)

    def test_hook_profile_off_bypasses_the_block(self):
        target = self._dirty()

        result = run_hook(
            _payload(str(target)), env_overrides={"PROMPTLIB_HOOK_PROFILE": "off"}
        )

        self.assertEqual(result.returncode, 0, msg=result.stdout)


class SnapshotPruningTests(unittest.TestCase):
    """The SessionEnd hook prunes aged-out snapshots so .git/ does not accumulate them."""

    def setUp(self) -> None:
        self.parent = Path(tempfile.mkdtemp(prefix="claude_inflight_prune_")).resolve()
        self.common = self.parent / ".git"
        (self.common / STATE_DIR).mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.parent, ignore_errors=True)

    def _load_pruner(self):
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import importlib

            module = importlib.import_module("session_end_release_lock")
            return importlib.reload(module)
        finally:
            sys.path.pop(0)

    def test_an_aged_snapshot_is_removed_and_a_fresh_one_kept(self):
        module = self._load_pruner()
        directory = self.common / STATE_DIR
        old, new = directory / "old.json", directory / "new.json"
        old.write_text("{}", encoding="utf-8")
        new.write_text("{}", encoding="utf-8")
        aged = time.time() - (module._INFLIGHT_MAX_AGE_S + 60)
        os.utime(old, (aged, aged))

        module._prune_inflight_snapshots(self.common)

        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_pruning_a_missing_directory_is_not_an_error(self):
        module = self._load_pruner()

        module._prune_inflight_snapshots(self.parent / "nope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
