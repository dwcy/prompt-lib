#!/usr/bin/env python3
"""git-identity -- agent commit identity + policy wrapper.

Subcommands:
    capture              snapshot --global user.name/user.email (idempotent)
    commit -m "<msg>"    capture -> set --local agent identity -> commit -> restore
    restore              unset --local user.name/user.email (safety net)
    tag NAME -m "<msg>"  annotated tag, gated by policy.tags.agent_may_tag
    policy show          print current policy
    policy set           modify agent_name / agent_email / agent_may_tag / auto_push
    policy add-type T    add a commit-type prefix to policy.allowed_types
    policy remove-type T remove a commit-type prefix from policy.allowed_types

Policy file lookup order:
    1. ~/.claude/git-policy.json           (user file -- edit to change values)
    2. ~/.claude/git/git-policy.default.json  (default seeded by apply script)
    3. Built-in defaults below.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
POLICY_PATH = CLAUDE_DIR / "git-policy.json"
POLICY_DEFAULT_PATH = CLAUDE_DIR / "git" / "git-policy.default.json"
IDENTITY_BACKUP = CLAUDE_DIR / "identity" / "git-original.json"

BUILTIN_DEFAULTS: dict = {
    "agent_name": "Claude Agent",
    "agent_email": "my@agent.commit",
    "allowed_types": ["feat", "task", "fix", "refactor", "test", "docs"],
    "refuse_on_branches": ["main", "master"],
    "tags": {"agent_may_tag": False, "auto_push": False},
}

_SUBJECT_RE = re.compile(r"^([a-z]+):\s")


def _git(
    *args: str, repo: Path | None = None, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=capture, text=True, check=check)


def _load_policy() -> dict:
    for path in (POLICY_PATH, POLICY_DEFAULT_PATH):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(json.dumps(BUILTIN_DEFAULTS))


def _save_policy(policy: dict) -> None:
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")


def _resolve_repo(arg: str | None) -> Path:
    return Path(arg).expanduser().resolve() if arg else Path.cwd()


def _apply_agent(repo: Path, policy: dict) -> None:
    _git("config", "--local", "user.name", policy["agent_name"], repo=repo)
    _git("config", "--local", "user.email", policy["agent_email"], repo=repo)


def _restore_local(repo: Path) -> None:
    for key in ("user.name", "user.email"):
        _git("config", "--local", "--unset", key, repo=repo, check=False)


def _current_branch(repo: Path) -> str:
    """Current branch name; works on empty repos (returns "" if HEAD is detached)."""
    r = _git("symbolic-ref", "--short", "HEAD", repo=repo, check=False)
    return r.stdout.strip()


def _validate_branch(repo: Path, policy: dict) -> str | None:
    branch = _current_branch(repo)
    if not branch:
        return None
    if branch in policy.get("refuse_on_branches", []):
        return (
            f"refusing to commit on '{branch}' -- policy.refuse_on_branches blocks it"
        )
    return None


def _validate_type(subject: str, policy: dict) -> str | None:
    allowed = policy.get("allowed_types", [])
    if not allowed:
        return None
    m = _SUBJECT_RE.match(subject)
    if not m:
        return f"commit subject must start with one of {allowed} followed by ': '"
    prefix = m.group(1)
    if prefix not in allowed:
        return f"commit type '{prefix}' not in policy.allowed_types {allowed}"
    return None


def cmd_capture(_args: argparse.Namespace) -> int:
    if IDENTITY_BACKUP.exists():
        backup = json.loads(IDENTITY_BACKUP.read_text(encoding="utf-8"))
        if backup.get("name") and backup.get("email"):
            print(
                f"git-identity: already captured ({backup['name']} <{backup['email']}>) at {backup.get('captured_at')}"
            )
            return 0
    name = _git("config", "--global", "--get", "user.name", check=False).stdout.strip()
    email = _git(
        "config", "--global", "--get", "user.email", check=False
    ).stdout.strip()
    if not name or not email:
        print(
            "git-identity: --global user.name/user.email not set -- nothing to capture (skipping)"
        )
        return 0
    IDENTITY_BACKUP.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "email": email,
        "source": "global",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    IDENTITY_BACKUP.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"git-identity: captured {name} <{email}> -> {IDENTITY_BACKUP}")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args.repo)
    policy = _load_policy()
    if (err := _validate_branch(repo, policy)) is not None:
        print(f"git-identity commit: {err}", file=sys.stderr)
        return 1
    if (err := _validate_type(args.message[0], policy)) is not None:
        print(f"git-identity commit: {err}", file=sys.stderr)
        return 1
    cmd_capture(argparse.Namespace())
    _apply_agent(repo, policy)
    try:
        flat = [arg for m in args.message for arg in ("-m", m)]
        return _git("commit", *flat, repo=repo, capture=False, check=False).returncode
    finally:
        _restore_local(repo)


def cmd_restore(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args.repo)
    _restore_local(repo)
    name = _git("config", "user.name", repo=repo, check=False).stdout.strip()
    email = _git("config", "user.email", repo=repo, check=False).stdout.strip()
    print(
        f"git-identity: --local user.name/email cleared; effective identity now: {name} <{email}>"
    )
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args.repo)
    policy = _load_policy()
    tags_pol = policy.get("tags", {})
    if not tags_pol.get("agent_may_tag", False):
        print(
            "git-identity tag: refused -- policy.tags.agent_may_tag is false. Edit ~/.claude/git-policy.json to allow.",
            file=sys.stderr,
        )
        return 1
    cmd_capture(argparse.Namespace())
    _apply_agent(repo, policy)
    try:
        rc = _git(
            "tag",
            "-a",
            args.name,
            "-m",
            args.message,
            repo=repo,
            capture=False,
            check=False,
        ).returncode
        if rc != 0:
            return rc
    finally:
        _restore_local(repo)
    if tags_pol.get("auto_push", False):
        rc = _git(
            "push", "origin", args.name, repo=repo, capture=False, check=False
        ).returncode
        if rc != 0:
            return rc
        print(f"git-identity: tag '{args.name}' created and pushed")
    else:
        print(
            f"git-identity: tag '{args.name}' created locally (auto_push=false; push manually with `git push origin {args.name}`)"
        )
    return 0


def cmd_policy_show(_args: argparse.Namespace) -> int:
    policy = _load_policy()
    source = (
        POLICY_PATH
        if POLICY_PATH.exists()
        else POLICY_DEFAULT_PATH
        if POLICY_DEFAULT_PATH.exists()
        else "<built-in defaults>"
    )
    print(json.dumps(policy, indent=2))
    print(f"\n(source: {source})")
    return 0


def cmd_policy_set(args: argparse.Namespace) -> int:
    policy = _load_policy()
    changed = False
    if args.agent_name is not None:
        policy["agent_name"] = args.agent_name
        changed = True
    if args.agent_email is not None:
        policy["agent_email"] = args.agent_email
        changed = True
    if args.agent_may_tag is not None:
        policy.setdefault("tags", {})["agent_may_tag"] = args.agent_may_tag
        changed = True
    if args.auto_push is not None:
        policy.setdefault("tags", {})["auto_push"] = args.auto_push
        changed = True
    if not changed:
        print(
            "git-identity policy set: no fields given (use --agent-name / --agent-email / --agent-may-tag / --auto-push)",
            file=sys.stderr,
        )
        return 1
    _save_policy(policy)
    print(f"git-identity: wrote {POLICY_PATH}")
    return 0


def cmd_policy_add_type(args: argparse.Namespace) -> int:
    policy = _load_policy()
    types = policy.setdefault("allowed_types", [])
    if args.type in types:
        print(f"git-identity: '{args.type}' already in allowed_types")
        return 0
    types.append(args.type)
    _save_policy(policy)
    print(f"git-identity: added '{args.type}' to allowed_types")
    return 0


def cmd_policy_remove_type(args: argparse.Namespace) -> int:
    policy = _load_policy()
    types = policy.setdefault("allowed_types", [])
    if args.type not in types:
        print(f"git-identity: '{args.type}' not in allowed_types", file=sys.stderr)
        return 1
    types.remove(args.type)
    _save_policy(policy)
    print(f"git-identity: removed '{args.type}' from allowed_types")
    return 0


def _bool_flag(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="git-identity", description="Agent commit identity + policy."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "capture", help="snapshot --global user.name/user.email (idempotent)"
    ).set_defaults(func=cmd_capture)

    cp = sub.add_parser(
        "commit", help="capture -> apply agent identity -> git commit -> restore"
    )
    cp.add_argument(
        "-m",
        "--message",
        action="append",
        required=True,
        help="commit message (repeat for multi-paragraph)",
    )
    cp.add_argument("--repo", default=None, help="repo path (default: cwd)")
    cp.set_defaults(func=cmd_commit)

    rp = sub.add_parser(
        "restore", help="unset --local user.name and user.email (safety net)"
    )
    rp.add_argument("--repo", default=None, help="repo path (default: cwd)")
    rp.set_defaults(func=cmd_restore)

    tp = sub.add_parser("tag", help="create an annotated tag (gated by policy.tags)")
    tp.add_argument("name")
    tp.add_argument("-m", "--message", required=True, help="annotated tag message")
    tp.add_argument("--repo", default=None, help="repo path (default: cwd)")
    tp.set_defaults(func=cmd_tag)

    pol = sub.add_parser("policy", help="show / modify ~/.claude/git-policy.json")
    psub = pol.add_subparsers(dest="pol_cmd", required=True)

    psub.add_parser("show", help="print current policy").set_defaults(
        func=cmd_policy_show
    )

    ps = psub.add_parser("set", help="modify policy values")
    ps.add_argument("--agent-name", default=None)
    ps.add_argument("--agent-email", default=None)
    ps.add_argument(
        "--agent-may-tag", type=_bool_flag, default=None, metavar="true|false"
    )
    ps.add_argument("--auto-push", type=_bool_flag, default=None, metavar="true|false")
    ps.set_defaults(func=cmd_policy_set)

    pa = psub.add_parser("add-type", help="add a commit-type prefix to allowed_types")
    pa.add_argument("type")
    pa.set_defaults(func=cmd_policy_add_type)

    pr = psub.add_parser(
        "remove-type", help="remove a commit-type prefix from allowed_types"
    )
    pr.add_argument("type")
    pr.set_defaults(func=cmd_policy_remove_type)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
