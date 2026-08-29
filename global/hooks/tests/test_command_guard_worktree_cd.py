#!/usr/bin/env python3
"""Tests for command_guard.py's working-directory drift check.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_command_guard_worktree_cd.py

The Bash tool persists the working directory between calls, so a single `cd`
into a git worktree silently relocates every later command in the session.
That is not hypothetical: it produced a file listing that reported an existing
file as missing, and a pytest run that used the worktree's own conftest and
sources while appearing to describe the main checkout.

A subshell -- `(cd "$wt" && pytest ...)` -- gets the same rootdir with no
drift, and git never needs a `cd` at all because `git -C <path>` exists. So the
guard blocks only the persistent form and leaves both escape hatches open.
"""

import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import command_guard  # noqa: E402


class WorktreeCdDetection(unittest.TestCase):
    def assert_flagged(self, command: str) -> None:
        self.assertIsNotNone(
            command_guard._unparenthesised_worktree_cd(command),
            f"expected drift to be flagged: {command!r}",
        )

    def assert_clean(self, command: str) -> None:
        self.assertIsNone(
            command_guard._unparenthesised_worktree_cd(command),
            f"expected no drift: {command!r}",
        )

    def test_bare_cd_with_a_literal_worktree_path_is_flagged(self):
        self.assert_flagged("cd C:/p/.claude/worktrees/agent-x && pytest -q")

    def test_cd_through_a_variable_is_flagged(self):
        """The shape this actually takes in practice; matching only literal
        arguments would miss every real occurrence."""
        self.assert_flagged('wt=/p/.claude/worktrees/a; cd $wt && pnpm test')
        self.assert_flagged('wt="/p/.claude/worktrees/a"; cd "$wt/apps" && pnpm lint')

    def test_a_subshell_is_the_supported_escape_hatch(self):
        self.assert_clean("(cd C:/p/.claude/worktrees/agent-x && pytest -q)")
        self.assert_clean('wt=/p/.claude/worktrees/a; (cd $wt && pytest)')

    def test_git_dash_c_never_trips_the_guard(self):
        """git needs no cd at all, so the guard must not push anyone away from it."""
        self.assert_clean("git -C C:/p/.claude/worktrees/agent-x status")
        self.assert_clean('wt=/p/.claude/worktrees/a; git -C $wt log --oneline -3')

    def test_cd_inside_the_main_checkout_is_untouched(self):
        self.assert_clean("cd C:/projects/prompt-lib && pytest -q")


class ScanIntegration(unittest.TestCase):
    def test_scan_reports_the_drift_and_names_the_remedy(self):
        issues = command_guard.scan("cd /p/.claude/worktrees/a && pytest", tool_name="Bash")
        drift = [i for i in issues if i.startswith("Working-directory drift")]
        self.assertEqual(len(drift), 1, issues)
        self.assertIn("subshell", drift[0])
        self.assertIn("git -C", drift[0])

    def test_scan_stays_quiet_for_a_subshell(self):
        issues = command_guard.scan("(cd /p/.claude/worktrees/a && pytest)", tool_name="Bash")
        self.assertEqual([i for i in issues if i.startswith("Working-directory drift")], [])

    def test_powershell_is_not_subject_to_this_check(self):
        """Only the Bash tool persists cwd between calls in the way this guards against."""
        issues = command_guard.scan(
            "cd /p/.claude/worktrees/a && pytest", tool_name="PowerShell"
        )
        self.assertEqual([i for i in issues if i.startswith("Working-directory drift")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
