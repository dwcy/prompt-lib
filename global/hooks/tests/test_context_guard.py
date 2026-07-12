#!/usr/bin/env python3
"""Tests for context_guard.py — the opt-in UserPromptSubmit context-usage nudge.

Stdlib only (no pytest). Run from anywhere:

    python global/hooks/tests/test_context_guard.py

Spins up a fake ~/.claude (via HOME/USERPROFILE override) and a fake transcript JSONL,
then invokes the hook as a subprocess with a JSON stdin payload, asserting on stdout.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
HOOK = HOOKS_DIR / "context_guard.py"


def _assistant_line(input_tokens=2, cache_creation=100, cache_read=1000, output=50) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": cache_creation,
                    "cache_read_input_tokens": cache_read,
                    "output_tokens": output,
                }
            },
        }
    )


class ContextGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="claude_ctxguard_")).resolve()
        self.home = self.tmp / "home"
        self.claude_dir = self.home / ".claude"
        self.claude_dir.mkdir(parents=True)
        self.transcript = self.tmp / "transcript.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_policy(self, **overrides) -> None:
        policy = {
            "enabled": True,
            "threshold_percent": 80,
            "max_context_tokens": 2000,
        }
        policy.update(overrides)
        (self.claude_dir / "context-guard-policy.json").write_text(
            json.dumps(policy), encoding="utf-8"
        )

    def _write_transcript(self, lines: list[str]) -> None:
        self.transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_hook(self, extra_env: dict | None = None) -> subprocess.CompletedProcess:
        import os

        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        if extra_env:
            env.update(extra_env)
        payload = json.dumps(
            {
                "session_id": "s1",
                "transcript_path": str(self.transcript),
                "prompt": "hello",
            }
        )
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def test_disabled_by_default_produces_no_output(self):
        # No policy file at all == disabled (matches the shipped default).
        self._write_transcript([_assistant_line(cache_read=1900)])

        result = self.run_hook()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_enabled_but_explicitly_disabled_produces_no_output(self):
        self._write_policy(enabled=False)
        self._write_transcript([_assistant_line(cache_read=1900)])

        result = self.run_hook()

        self.assertEqual(result.stdout.strip(), "")

    def test_below_threshold_produces_no_output(self):
        self._write_policy()
        # ~52/2000 = 2.6% — nowhere near the 80% threshold.
        self._write_transcript([_assistant_line(input_tokens=2, cache_creation=0, cache_read=0, output=50)])

        result = self.run_hook()

        self.assertEqual(result.stdout.strip(), "")

    def test_at_or_above_threshold_emits_additional_context_nudge(self):
        self._write_policy()
        # 2 + 0 + 1650 + 50 = 1702 / 2000 = 85.1% >= 80%.
        self._write_transcript(
            [_assistant_line(input_tokens=2, cache_creation=0, cache_read=1650, output=50)]
        )

        result = self.run_hook()

        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        message = body["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(body["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("/compact", message)
        self.assertIn("advisory", message.lower())

    def test_uses_the_most_recent_assistant_usage_entry(self):
        self._write_policy()
        self._write_transcript(
            [
                _assistant_line(input_tokens=2, cache_creation=0, cache_read=1900, output=50),
                json.dumps({"type": "user", "message": {"content": "ok"}}),
                _assistant_line(input_tokens=2, cache_creation=0, cache_read=0, output=10),
            ]
        )

        result = self.run_hook()

        # The last assistant usage (12 tokens) is well below threshold even though an
        # earlier entry alone would have crossed it.
        self.assertEqual(result.stdout.strip(), "")

    def test_missing_transcript_file_fails_open(self):
        self._write_policy()
        self.transcript.unlink(missing_ok=True)

        result = self.run_hook()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_json_lines_are_skipped_not_fatal(self):
        self._write_policy()
        self._write_transcript(
            [
                "{not json",
                _assistant_line(input_tokens=2, cache_creation=0, cache_read=1650, output=50),
            ]
        )

        result = self.run_hook()

        body = json.loads(result.stdout)
        self.assertIn("/compact", body["hookSpecificOutput"]["additionalContext"])

    def test_malformed_stdin_fails_open(self):
        self._write_policy()
        self._write_transcript([_assistant_line(cache_read=1900)])
        import os

        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input="not json",
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_disabled_hooks_env_var_suppresses_nudge(self):
        self._write_policy()
        self._write_transcript(
            [_assistant_line(input_tokens=2, cache_creation=0, cache_read=1650, output=50)]
        )

        result = self.run_hook(extra_env={"PROMPTLIB_DISABLED_HOOKS": "context_guard"})

        self.assertEqual(result.stdout.strip(), "")

    def test_hook_profile_off_suppresses_nudge(self):
        self._write_policy()
        self._write_transcript(
            [_assistant_line(input_tokens=2, cache_creation=0, cache_read=1650, output=50)]
        )

        result = self.run_hook(extra_env={"PROMPTLIB_HOOK_PROFILE": "off"})

        self.assertEqual(result.stdout.strip(), "")

    def test_missing_max_context_tokens_fails_open(self):
        self._write_policy(max_context_tokens=0)
        self._write_transcript([_assistant_line(cache_read=1900)])

        result = self.run_hook()

        self.assertEqual(result.stdout.strip(), "")

    def test_missing_transcript_path_in_payload_fails_open(self):
        self._write_policy()
        import os

        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"session_id": "s1"}),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
