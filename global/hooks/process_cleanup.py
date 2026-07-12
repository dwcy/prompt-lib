#!/usr/bin/env python3
"""SessionStart/SessionEnd hook — sweep orphaned Claude Code helper processes.

Windows-only: shells out to the sibling claude-process-check.ps1 with -Kill,
which targets only orphaned Claude-related helpers (node.exe, claude.exe,
sh.exe, bash.exe, and small unix helpers) whose parent process is gone —
never a live dev server. Appends one line per run to
~/.claude/process_cleanup.log. Emits additionalContext only when something
was actually killed, and only on SessionStart (SessionEnd output is never
read). Never fails the session: any error exits 0.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


SCRIPT_PATH = Path(__file__).parent / "claude-process-check.ps1"
LOG_PATH = Path.home() / ".claude" / "process_cleanup.log"

ORPHAN_COUNT_RE = re.compile(r"Flagged as orphaned:\s*(\d+)\s*processes")
KILLED_LINE_RE = re.compile(r"^\s*killed \d+ \S+", re.MULTILINE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(event: str, found: int, killed: int, note: str = "") -> None:
    line = f"{_now_iso()} event={event} orphans_found={found} orphans_killed={killed}"
    if note:
        line += f" note={note}"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _run_cleanup() -> tuple[int, int, str]:
    """Return (orphans_found, orphans_killed, note)."""
    if not SCRIPT_PATH.exists():
        return 0, 0, "script missing"
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-Kill",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 0, 0, str(exc)

    stdout = result.stdout or ""
    found_match = ORPHAN_COUNT_RE.search(stdout)
    found = int(found_match.group(1)) if found_match else 0
    killed = len(KILLED_LINE_RE.findall(stdout))
    return found, killed, ""


def main() -> None:
    if should_skip("process_cleanup"):
        return
    if sys.platform != "win32":
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    event = data.get("hook_event_name") or "unknown"

    found, killed, note = _run_cleanup()
    _log(event, found, killed, note)

    if killed and event == "SessionStart":
        plural = "es" if killed != 1 else ""
        print(
            json.dumps(
                {
                    "additionalContext": (
                        f"Cleaned up {killed} orphaned Claude helper process{plural} "
                        "left over from a previous session."
                    )
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
