#!/usr/bin/env python3
"""SessionStart hook — detect project state and inject context for Claude.

Cross-platform (Windows / Linux / macOS). Emits JSON with `additionalContext`
on stdout so Claude knows what to do at session start. Never fails the session:
any error exits 0 with no output.

Also enforces parallel-session isolation: if another Claude session already
holds the per-branch lock at <git-common-dir>/claude-session-locks/<branch>.json,
auto-create a sibling worktree on a new branch and instruct the user to switch.
See docs/parallel-isolation.md.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def emit(message: str) -> None:
    print(json.dumps({"additionalContext": message}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            return str(pid) in out.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _resolve_git_path(raw: str, cwd: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = (cwd / p)
    return p.resolve()


def _next_session_slot(repo: str, branch_slug: str, main_checkout: Path) -> tuple[str, Path]:
    branches_out = subprocess.run(
        ["git", "-C", str(main_checkout), "branch", "--list", "--format=%(refname:short)"],
        capture_output=True, text=True, check=False, timeout=10,
    ).stdout
    existing_branches = {b.strip() for b in branches_out.splitlines() if b.strip()}
    parent = main_checkout.parent
    n = 2
    while True:
        candidate_branch = f"{branch_slug}-s{n}"
        candidate_dir = parent / f"{repo}-{branch_slug}-s{n}"
        if candidate_branch not in existing_branches and not candidate_dir.exists():
            return candidate_branch, candidate_dir
        n += 1


def _write_lock(lock_path: Path, our_pid: int, our_cwd: str) -> None:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps({"pid": our_pid, "started_at": _now_iso(), "cwd": our_cwd}),
            encoding="utf-8",
        )
    except OSError:
        pass


def _check_worktree_collision(cwd: Path) -> tuple[bool, str | None]:
    """Return (proceed_normally, collision_message_or_none).

    proceed_normally=True → continue to stack detection.
    proceed_normally=False → emit collision_message and skip stack detection.
    Any unexpected condition falls through as (True, None).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse",
             "--git-dir", "--git-common-dir", "--abbrev-ref", "HEAD", "--show-toplevel"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True, None
    if result.returncode != 0:
        return True, None
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    if len(lines) != 4:
        return True, None
    git_dir_raw, common_dir_raw, branch, toplevel = lines

    if not branch or branch in ("HEAD", "main", "master"):
        return True, None

    git_dir = _resolve_git_path(git_dir_raw, cwd)
    common_dir = _resolve_git_path(common_dir_raw, cwd)
    main_checkout = Path(toplevel).resolve()

    branch_slug = branch.replace("/", "-")
    lock_path = common_dir / "claude-session-locks" / f"{branch_slug}.json"
    our_cwd = str(cwd.resolve())
    our_pid = os.getppid()

    if git_dir != common_dir:
        _write_lock(lock_path, our_pid, our_cwd)
        return True, None

    existing: dict | None = None
    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = data
        except (json.JSONDecodeError, OSError):
            existing = None

    holder_alive = False
    holder_cwd = None
    if existing:
        holder_cwd = existing.get("cwd")
        holder_pid = existing.get("pid")
        if isinstance(holder_pid, int):
            holder_alive = _pid_alive(holder_pid)

    if not holder_alive or holder_cwd == our_cwd:
        _write_lock(lock_path, our_pid, our_cwd)
        return True, None

    if os.environ.get("CLAUDE_WORKTREE_AUTO") == "0":
        msg = (
            f"Another Claude session is active on branch `{branch}` at `{holder_cwd}`. "
            f"Auto-worktree creation is disabled (CLAUDE_WORKTREE_AUTO=0). "
            f"Run `/using-git-worktrees create {branch}-s2` from the main checkout, then "
            f"`cd` into the new worktree and start `claude` there. "
            f"Do not edit files in `{our_cwd}` until you switch — concurrent writes will "
            f"silently overwrite each other."
        )
        return False, msg

    repo = main_checkout.name
    try:
        new_branch, target_dir = _next_session_slot(repo, branch_slug, main_checkout)
        target_rel = f"../{target_dir.name}"
        subprocess.run(
            ["git", "-C", str(main_checkout), "worktree", "add", target_rel, "-b", new_branch],
            capture_output=True, text=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        err = getattr(exc, "stderr", None) or str(exc)
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        msg = (
            f"Another Claude session is active on branch `{branch}` at `{holder_cwd}`. "
            f"Attempted to auto-create a sibling worktree but failed: {err}. "
            f"Run `/using-git-worktrees create {branch}-s2` manually, then `cd` into it and "
            f"start `claude` there. Do not edit files in `{our_cwd}` until you switch."
        )
        return False, msg

    msg = (
        f"**Stop — another Claude session is already active on branch `{branch}`** "
        f"(at `{holder_cwd}`).\n\n"
        f"To prevent concurrent writes silently overwriting each other, a sibling worktree "
        f"has been created for this session:\n\n"
        f"- Path: `{target_dir}`\n"
        f"- Branch: `{new_branch}`\n\n"
        f"Tell the user to switch:\n\n"
        f"```\ncd {target_dir}\nclaude\n```\n\n"
        f"Until the user switches, refuse all Write/Edit/Bash actions that would modify "
        f"files in `{our_cwd}`. Only read-only operations (Read/Grep/Glob) are safe here."
    )
    return False, msg


def main() -> None:
    cwd = Path.cwd()

    try:
        proceed, collision_msg = _check_worktree_collision(cwd)
    except Exception:
        proceed, collision_msg = True, None

    if not proceed:
        if collision_msg:
            emit(collision_msg)
        return

    if not (cwd / "CLAUDE.md").exists():
        emit(
            f"No CLAUDE.md was found in this project directory ({cwd}). Before doing "
            "anything else, ask the user whether they want to describe the project now "
            "so a CLAUDE.md can be created, or be reminded next session. If they "
            "describe it, create a CLAUDE.md at the project root with: a project name "
            "heading, what the project does, the tech stack, key directories, and any "
            "important workflows. If they decline, proceed normally without creating it."
        )
        return

    hints: list[str] = []

    if list(cwd.glob("*.sln")) or any(cwd.glob(f"{'*/' * d}*.csproj") for d in range(4)):
        hints.append(".NET")

    if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists() or (cwd / "Pipfile").exists():
        hints.append("Python")

    pkg = cwd / "package.json"
    if pkg.exists():
        try:
            pkg_text = pkg.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pkg_text = ""
        is_monorepo = (
            '"workspaces"' in pkg_text
            or (cwd / "pnpm-workspace.yaml").exists()
            or (cwd / "turbo.json").exists()
            or (cwd / "nx.json").exists()
            or (cwd / "lerna.json").exists()
        )
        hints.append("Monorepo" if is_monorepo else "JavaScript/TypeScript")

    if (cwd / "Assets").exists() and (cwd / "ProjectSettings").exists():
        hints.append("Unity3D")

    stack = " + ".join(hints) if hints else "unknown stack"
    emit(
        f"Existing project detected ({stack}) in {cwd}. A CLAUDE.md exists. "
        "Proactively invoke the @load-project agent to read the project context and "
        "announce which specialist subagents are available for this session."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
