#!/usr/bin/env python3
"""Tests for the session_start.py auto session title (hookSpecificOutput.sessionTitle).

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_session_title.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
SESSION_START = HOOKS_DIR / "session_start.py"


def run_hook(cwd: Path) -> dict:
    env = os.environ.copy()
    env.pop("PROMPTLIB_DISABLED_HOOKS", None)
    out = subprocess.run(
        [sys.executable, str(SESSION_START)],
        input="{}",
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
        timeout=30,
    ).stdout
    return json.loads(out)


class SessionTitleTest(unittest.TestCase):
    def test_plain_dir_titles_with_dir_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp) / "my-project"
            cwd.mkdir()
            data = run_hook(cwd)
            self.assertEqual(data["hookSpecificOutput"]["sessionTitle"], "my-project")
            self.assertEqual(
                data["hookSpecificOutput"]["hookEventName"], "SessionStart"
            )

    def test_git_repo_titles_with_dir_and_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp) / "my-repo"
            cwd.mkdir()
            subprocess.run(
                ["git", "init", "-b", "feat/thing"],
                cwd=cwd,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.email=t@t",
                    "-c",
                    "user.name=t",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "init",
                ],
                cwd=cwd,
                capture_output=True,
                check=True,
            )
            data = run_hook(cwd)
            self.assertEqual(
                data["hookSpecificOutput"]["sessionTitle"],
                "my-repo · feat/thing",
            )


if __name__ == "__main__":
    unittest.main()
