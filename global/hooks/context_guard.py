#!/usr/bin/env python3
"""UserPromptSubmit hook — advisory nudge when estimated context usage crosses a threshold.

Opt-in via ~/.claude/context-guard-policy.json (default `enabled: false`). When on, reads
the session transcript (`transcript_path`, JSONL) and estimates current context-window
token usage from the most recent assistant message's `usage` object (`input_tokens` +
`cache_creation_input_tokens` + `cache_read_input_tokens` + `output_tokens` — verified
empirically against real transcript files; see docs/context-guard.md). If that estimate,
divided by the configured `max_context_tokens`, is at or above `threshold_percent`, emits
`hookSpecificOutput.additionalContext` suggesting the agent proactively consider `/compact`.

This is an ADVISORY NUDGE ONLY. No Claude Code hook can trigger or force compaction —
`PreCompact` can only block a compaction Claude Code already decided to run. This hook
can only ask; the agent may act on the suggestion or ignore it.

Fails open: any error, malformed input, missing transcript, or missing/disabled policy
exits 0 with no output. Honors PROMPTLIB_DISABLED_HOOKS=context_guard and
PROMPTLIB_HOOK_PROFILE=off via _gate.should_skip.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


POLICY_PATH = Path.home() / ".claude" / "context-guard-policy.json"

# Usage fields Anthropic's API attaches to each assistant transcript entry. Summed, they
# approximate the total tokens the model saw + produced on its most recent turn — the
# closest available proxy for "tokens currently occupying the context window" without a
# hook ever receiving a real context-window/token-usage field on stdin.
_USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)

# Bound how much of a (possibly huge, append-only) transcript we scan from the tail
# before giving up, so one very long session never makes every prompt submission slow.
_MAX_TAIL_BYTES = 8 * 1024 * 1024


def _load_policy() -> dict[str, Any] | None:
    if not POLICY_PATH.exists():
        return None
    try:
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _sum_usage(usage: dict[str, Any]) -> int | None:
    total = 0
    seen = False
    for field in _USAGE_FIELDS:
        value = usage.get(field)
        if isinstance(value, (int, float)):
            total += value
            seen = True
    return int(total) if seen else None


def _last_assistant_usage_tokens(transcript_path: str) -> int | None:
    """Scan a JSONL transcript from the end for the most recent assistant `usage`."""
    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
        if size == 0:
            return None
        chunk = min(size, 524288)
        with path.open("rb") as fh:
            while True:
                fh.seek(-chunk, 2)
                raw = fh.read()
                text = raw.decode("utf-8", errors="replace")
                lines = text.splitlines()
                # The first line may be a partial line when we didn't start at byte 0.
                usable = lines[1:] if chunk < size else lines
                for line in reversed(usable):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    usage = (entry.get("message") or {}).get("usage")
                    if isinstance(usage, dict):
                        return _sum_usage(usage)
                if chunk >= size or chunk >= _MAX_TAIL_BYTES:
                    return None
                chunk = min(chunk * 4, size, _MAX_TAIL_BYTES)
    except (OSError, ValueError):
        return None


def _emit_nudge(used_tokens: int, max_tokens: float, threshold: float, pct: float) -> None:
    message = (
        f"Context guard: estimated ~{used_tokens:,} tokens in context "
        f"(~{pct:.0f}% of the configured {int(max_tokens):,}-token budget), at or above "
        f"the configured {threshold:.0f}% threshold. This is an advisory nudge only — "
        "no hook can force or trigger compaction. Consider proactively running /compact "
        "soon if it fits the current task, but use your own judgement about timing."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": message,
                }
            }
        )
    )


def main() -> None:
    if should_skip("context_guard"):
        return
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    policy = _load_policy()
    if not policy or not policy.get("enabled"):
        return

    max_tokens = policy.get("max_context_tokens")
    threshold = policy.get("threshold_percent")
    if not isinstance(max_tokens, (int, float)) or max_tokens <= 0:
        return
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        return

    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return

    used = _last_assistant_usage_tokens(transcript_path)
    if used is None:
        return

    pct = (used / max_tokens) * 100
    if pct < threshold:
        return

    _emit_nudge(used, max_tokens, threshold, pct)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
