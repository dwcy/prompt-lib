#!/usr/bin/env python3
"""SessionEnd hook — release the per-branch session lock claimed by this cwd.

Reads <git-common-dir>/claude-session-locks/<branch>.json and deletes it if
the lock's `cwd` matches the current working directory. Never fails the
session: any error exits 0.
"""
import json
import subprocess
import sys
from pathlib import Path


def _resolve_git_path(raw: str, cwd: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def main() -> None:
    cwd = Path.cwd()

    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse",
             "--git-common-dir", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode != 0:
        return
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    if len(lines) != 2:
        return
    common_dir_raw, branch = lines
    if not branch or branch in ("HEAD", "main", "master"):
        return

    branch_slug = branch.replace("/", "-")
    common_dir = _resolve_git_path(common_dir_raw, cwd)
    lock_path = common_dir / "claude-session-locks" / f"{branch_slug}.json"
    if not lock_path.exists():
        return

    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return

    our_cwd = str(cwd.resolve())
    if data.get("cwd") != our_cwd:
        return

    try:
        lock_path.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
