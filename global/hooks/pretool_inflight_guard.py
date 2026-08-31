#!/usr/bin/env python3
"""PreToolUse guard: warn once before editing a file that already had uncommitted work.

Complements the per-branch session lock in session_start.py, which can only see a *live*
competing session. The likelier hazard is uncommitted work left behind by a session that
already exited: there is no lock holder to detect, and the file looks ordinary. Editing it
then risks two silent losses — sweeping someone else's change into your commit, or reverting
the file wholesale and destroying work git has no copy of (nothing unstaged is recoverable).

So this hook snapshots the repo's dirty set the first time a session touches it, and blocks
the FIRST edit of any file in that snapshot with an explanation. The second attempt proceeds:
the point is to make the decision conscious, not to make the file unwritable — a feature often
legitimately has to edit a file someone else also touched.

Exit 0 -> allow
Exit 2 -> block (once per file, per session)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


HOOK_NAME = "pretool_inflight_guard"
STATE_DIR_NAME = "claude-inflight"
_GIT_TIMEOUT = 15
# Porcelain codes for work that predates this session and is not recoverable from git:
# tracked-but-modified, and untracked-but-not-ignored. Staged entries count too — staged
# is still only in the index, which a checkout can discard.
_UNTRACKED_CODE = "??"


def _git_executable() -> str:
    override = os.environ.get("PROMPTLIB_GIT")
    if override:
        return override
    if sys.platform == "win32":
        for root in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            candidate = Path(root) / "Git" / "cmd" / "git.exe"
            if candidate.exists():
                return str(candidate)
    return "git"


def _run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            [_git_executable(), "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _nearest_existing_dir(file_path: str) -> Path | None:
    target = Path(file_path).expanduser()
    start = target if target.is_dir() else target.parent
    while not start.exists() and start != start.parent:
        start = start.parent
    return start if start.exists() else None


def _repo_roots(start: Path) -> tuple[Path, Path] | None:
    """Return (toplevel, common_dir) for the repo containing `start`, or None."""
    toplevel = _run_git(["rev-parse", "--show-toplevel"], start)
    common = _run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], start)
    if not toplevel or not common:
        return None
    top = Path(toplevel.strip())
    common_dir = Path(common.strip())
    if not top.is_dir() or not common_dir.is_dir():
        return None
    return top, common_dir


def _dirty_paths(toplevel: Path) -> set[str] | None:
    """Repo-relative paths carrying work that is not committed anywhere.

    `-uall` lists untracked files individually rather than collapsing a whole new directory
    to its name, so a path comparison against the edited file can actually match. Ignored
    files are excluded by default, which keeps build output and caches out of the snapshot.
    """
    output = _run_git(["status", "--porcelain", "-uall"], toplevel)
    if output is None:
        return None
    dirty: set[str] = set()
    for line in output.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip()
        # Renames report "old -> new"; the new name is the one an edit would target.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if not path:
            continue
        if code == _UNTRACKED_CODE or code.strip():
            dirty.add(path)
    return dirty


def _state_path(common_dir: Path, session_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_id) or "unknown"
    return common_dir / STATE_DIR_NAME / f"{safe}.json"


def _load_state(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def _relative(file_path: str, toplevel: Path) -> str | None:
    try:
        resolved = Path(file_path).expanduser().resolve()
        return resolved.relative_to(toplevel.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _block(relative: str, recorded_at: str) -> None:
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f"[In-flight Guard] '{relative}' already had uncommitted changes when this "
                    f"session started ({recorded_at}) — they are not yours.\n\n"
                    "Before editing it:\n"
                    "  1. Read the file, and `git diff HEAD -- <path>` to see whose work is in it.\n"
                    "  2. NEVER `git checkout --`/`git restore` it. Unstaged work has no copy in "
                    "git; reverting destroys it permanently.\n"
                    "  3. Keep it out of your commit unless the change is genuinely yours — stage "
                    "files explicitly, never `git add -A`.\n\n"
                    "If you do need to edit it, retry the same edit now and it will go through. "
                    "This warning fires once per file per session.\n"
                    f"To disable entirely: PROMPTLIB_DISABLED_HOOKS={HOOK_NAME}."
                ),
            }
        )
    )
    sys.exit(2)


def main() -> None:
    if should_skip(HOOK_NAME):
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if data.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    start = _nearest_existing_dir(file_path)
    if start is None:
        sys.exit(0)
    roots = _repo_roots(start)
    if roots is None:
        sys.exit(0)
    toplevel, common_dir = roots

    relative = _relative(file_path, toplevel)
    if relative is None:
        sys.exit(0)

    session_id = str(data.get("session_id") or "unknown")
    state_path = _state_path(common_dir, session_id)
    state = _load_state(state_path)

    if state is None:
        # First edit this session: snapshot what was already dirty. Anything this session
        # goes on to change is absent from the snapshot and so never warned about.
        dirty = _dirty_paths(toplevel)
        if dirty is None:
            sys.exit(0)
        state = {
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "baseline": sorted(dirty),
            "acknowledged": [],
        }
        _save_state(state_path, state)

    baseline = set(state.get("baseline") or [])
    acknowledged = set(state.get("acknowledged") or [])

    if relative not in baseline or relative in acknowledged:
        sys.exit(0)

    acknowledged.add(relative)
    state["acknowledged"] = sorted(acknowledged)
    _save_state(state_path, state)
    _block(relative, str(state.get("recorded_at", "unknown")))


if __name__ == "__main__":
    main()
