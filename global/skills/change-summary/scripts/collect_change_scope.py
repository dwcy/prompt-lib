"""Resolve a diff scope (staged / PR / branch range) and emit its facts as JSON."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

UNIT_SEP = "\x1f"
RECORD_SEP = "\x1e"


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


GIT = _git_executable()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([GIT, *args], capture_output=True, text=True)


def gh(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        return None


def parse_name_status(output: str) -> list[dict]:
    files = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        files.append({"status": status[0], "path": path})
    return files


def parse_commits(output: str) -> list[dict]:
    commits = []
    for record in output.split(RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        fields = record.split(UNIT_SEP)
        if len(fields) < 3:
            continue
        commits.append({"hash": fields[0], "subject": fields[1], "body": fields[2].strip()})
    return commits


def commit_log(rev_range: str) -> list[dict]:
    fmt = f"%H{UNIT_SEP}%s{UNIT_SEP}%b{RECORD_SEP}"
    result = git("log", rev_range, f"--format={fmt}")
    if result.returncode != 0:
        return []
    return parse_commits(result.stdout)


def pr_json(*view_args: str) -> dict | None:
    result = gh("pr", "view", *view_args, "--json", "number,title,body,baseRefName,headRefName")
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def merge_base_default_branch() -> str | None:
    for candidate in ("main", "master"):
        check = git("show-ref", "--verify", "--quiet", f"refs/heads/{candidate}")
        if check.returncode == 0:
            base = git("merge-base", candidate, "HEAD")
            if base.returncode == 0:
                return base.stdout.strip()
    return None


def result(kind: str, description: str, files: list[dict], commits: list[dict], pr: dict | None) -> dict:
    return {
        "scope": {"kind": kind, "description": description},
        "files": files,
        "commits": commits,
        "pr": pr,
    }


def diff_pr(pr: dict) -> dict:
    base_ref, head_ref = f"origin/{pr['baseRefName']}", pr["headRefName"]
    git("fetch", "origin", pr["baseRefName"])
    diff = git("diff", "--name-status", f"{base_ref}...{head_ref}")
    files = parse_name_status(diff.stdout)
    commits = commit_log(f"{base_ref}..{head_ref}")
    return result("pr", f"PR #{pr['number']}: {pr['title']}", files, commits, pr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", help="PR number to summarize")
    parser.add_argument("--base", help="Base ref to diff from")
    parser.add_argument("--head", default="HEAD", help="Head ref to diff to (default: HEAD)")
    parser.add_argument("--staged", action="store_true", help="Summarize staged changes only")
    args = parser.parse_args()

    if git("rev-parse", "--git-dir").returncode != 0:
        print(json.dumps(result("error", "Not inside a git repository.", [], [], None)))
        return

    if args.staged:
        diff = git("diff", "--cached", "--name-status")
        print(json.dumps(result("staged", "Currently staged changes.", parse_name_status(diff.stdout), [], None)))
        return

    if args.pr:
        pr = pr_json(args.pr)
        if pr is None:
            print(json.dumps(result("error", f"Could not read PR #{args.pr} via gh.", [], [], None)))
            return
        print(json.dumps(diff_pr(pr)))
        return

    if args.base:
        diff = git("diff", "--name-status", f"{args.base}...{args.head}")
        files = parse_name_status(diff.stdout)
        commits = commit_log(f"{args.base}..{args.head}")
        print(json.dumps(result("range", f"{args.base}...{args.head}", files, commits, None)))
        return

    staged = git("diff", "--cached", "--name-status")
    if staged.stdout.strip():
        print(json.dumps(result("staged", "Currently staged changes.", parse_name_status(staged.stdout), [], None)))
        return

    unstaged = git("diff", "--name-status")
    if unstaged.stdout.strip():
        print(
            json.dumps(
                result("unstaged", "Currently unstaged working-tree changes.", parse_name_status(unstaged.stdout), [], None)
            )
        )
        return

    pr = pr_json()
    if pr:
        print(json.dumps(diff_pr(pr)))
        return

    base = merge_base_default_branch()
    if base:
        diff = git("diff", "--name-status", f"{base}...HEAD")
        files = parse_name_status(diff.stdout)
        commits = commit_log(f"{base}..HEAD")
        print(json.dumps(result("branch", f"{base[:7]}...HEAD (vs main/master)", files, commits, None)))
        return

    print(
        json.dumps(
            result(
                "none",
                "No changes found — no staged/unstaged edits, no PR, no default branch to diff against.",
                [],
                [],
                None,
            )
        )
    )


if __name__ == "__main__":
    main()
