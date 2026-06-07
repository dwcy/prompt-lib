# -*- coding: utf-8 -*-
"""Source-checkout update detection + git pull invocation.

When the wizard runs from a source checkout, the home/update screens use these
to show "behind by N commits — Subject of newest" and to invoke `git pull`.
"""

from __future__ import annotations

import shutil
import subprocess

from cabal._paths import REPO_DIR


def _current_branch() -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=5,
        )
        if r.returncode != 0:
            return None
        name = r.stdout.strip()
        return name or None
    except Exception:
        return None


def _upstream() -> tuple[str, str] | None:
    """Return (remote, ref) for the current branch's upstream, or None if unset.

    Compares against what `git pull` would actually merge — the current branch's
    tracking branch — not the remote's default branch. On a feature branch this
    is `origin/<feature>`, so we don't falsely report "behind" against main.
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=5,
        )
        if r.returncode != 0:
            return None
        full = r.stdout.strip()  # e.g. "origin/main"
        if "/" not in full:
            return None
        remote, ref = full.split("/", 1)
        return remote, ref
    except Exception:
        return None


def check_for_updates() -> dict:
    if REPO_DIR is None:
        return {"status": "no_repo"}
    if not shutil.which("git"):
        return {"status": "no_git"}
    try:
        branch = _current_branch()
        up = _upstream()
        if up is None:
            return {"status": "no_upstream", "branch": branch}
        remote, ref = up
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=5,
        )
        remote_ls = subprocess.run(
            ["git", "ls-remote", remote, ref],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=10,
        )
        if (
            local.returncode != 0
            or remote_ls.returncode != 0
            or not remote_ls.stdout.strip()
        ):
            return {"status": "error"}
        local_hash = local.stdout.strip()
        remote_hash = remote_ls.stdout.split()[0]
        short = lambda h: h[:8]
        if local_hash == remote_hash:
            date = ""
            d = subprocess.run(
                [
                    "git",
                    "log",
                    "-1",
                    "--format=%cs",
                    local_hash,
                ],  # %cs = committer date, short ISO
                capture_output=True,
                text=True,
                cwd=str(REPO_DIR),
                timeout=5,
            )
            if d.returncode == 0:
                date = d.stdout.strip()
            return {"status": "up_to_date", "hash": short(local_hash), "date": date}

        # Tips differ — fetch the upstream so we can count how many commits we're
        # actually behind (a different tip can also mean we're ahead — nothing to pull).
        behind_count: int | None = None
        subject = ""
        fetch = subprocess.run(
            ["git", "fetch", remote, ref, "--quiet"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=30,
        )
        if fetch.returncode == 0:
            cnt = subprocess.run(
                ["git", "rev-list", "--count", f"{local_hash}..{remote_hash}"],
                capture_output=True,
                text=True,
                cwd=str(REPO_DIR),
                timeout=5,
            )
            if cnt.returncode == 0 and cnt.stdout.strip().isdigit():
                behind_count = int(cnt.stdout.strip())
            subj = subprocess.run(
                ["git", "log", "-1", "--format=%s", remote_hash],
                capture_output=True,
                text=True,
                cwd=str(REPO_DIR),
                timeout=5,
            )
            if subj.returncode == 0:
                subject = subj.stdout.strip()

        # Different tip but zero commits to pull → we're level or ahead of upstream.
        if behind_count == 0:
            return {"status": "up_to_date", "hash": short(local_hash), "date": ""}

        return {
            "status": "behind",
            "local": short(local_hash),
            "remote": short(remote_hash),
            "behind_count": behind_count,
            "subject": subject,
            "branch": branch,
        }
    except Exception:
        return {"status": "error"}


def do_git_pull() -> tuple[bool, str]:
    if REPO_DIR is None:
        return False, "no git checkout available (running from a frozen build)"
    try:
        r = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            timeout=60,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)
