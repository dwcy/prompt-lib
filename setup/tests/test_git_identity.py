# -*- coding: utf-8 -*-
"""Smoke + policy-enforcement tests for global/scripts/git-identity.py.

Tests run the script as a subprocess against a fully isolated environment:
fake $HOME so `~/.claude/...` resolves to tmp, GIT_CONFIG_GLOBAL so `git config
--global` writes/reads from tmp instead of the user's real ~/.gitconfig.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "global" / "scripts" / "git-identity.py"


def _run_git(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=cwd, env=env
    )


def _run_script(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env
    )


@pytest.fixture
def env_setup(tmp_path: Path) -> dict:
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "git").mkdir(parents=True)

    default_policy = {
        "agent_name": "Test Agent",
        "agent_email": "test@agent",
        "allowed_types": ["feat", "fix"],
        "refuse_on_branches": ["main", "master"],
        "tags": {"agent_may_tag": False, "auto_push": False},
    }
    (claude / "git" / "git-policy.default.json").write_text(
        json.dumps(default_policy) + "\n", encoding="utf-8"
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
    }
    _run_git("init", "-q", "-b", "feature", cwd=repo, env=env)
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    _run_git("add", "a.txt", cwd=repo, env=env)
    _run_git("config", "--global", "user.name", "Real User", env=env)
    _run_git("config", "--global", "user.email", "real@user.com", env=env)

    return {"home": home, "claude": claude, "repo": repo, "env": env}


def test_commit_round_trip_preserves_global_and_attributes_agent(
    env_setup: dict,
) -> None:
    s = env_setup
    rc = _run_script(
        "commit", "--repo", str(s["repo"]), "-m", "feat: hello", env=s["env"]
    )
    assert rc.returncode == 0, rc.stderr

    r = _run_git("config", "--global", "--get", "user.email", env=s["env"])
    assert r.stdout.strip() == "real@user.com"

    r = _run_git("config", "--local", "--get", "user.name", cwd=s["repo"], env=s["env"])
    assert r.stdout.strip() == ""
    r = _run_git(
        "config", "--local", "--get", "user.email", cwd=s["repo"], env=s["env"]
    )
    assert r.stdout.strip() == ""

    r = _run_git("log", "-1", "--format=%an <%ae>", cwd=s["repo"], env=s["env"])
    assert r.stdout.strip() == "Test Agent <test@agent>"

    backup = s["claude"] / "identity" / "git-original.json"
    assert backup.exists()
    data = json.loads(backup.read_text(encoding="utf-8"))
    assert data["name"] == "Real User"
    assert data["email"] == "real@user.com"
    assert data["source"] == "global"


def test_disallowed_commit_type_is_rejected(env_setup: dict) -> None:
    s = env_setup
    rc = _run_script(
        "commit", "--repo", str(s["repo"]), "-m", "wip: stuff", env=s["env"]
    )
    assert rc.returncode == 1
    assert "not in policy.allowed_types" in rc.stderr


def test_tag_refused_when_agent_may_tag_false(env_setup: dict) -> None:
    s = env_setup
    _run_script("commit", "--repo", str(s["repo"]), "-m", "feat: initial", env=s["env"])

    rc = _run_script(
        "tag", "v1.0.0", "-m", "release", "--repo", str(s["repo"]), env=s["env"]
    )
    assert rc.returncode == 1
    assert "agent_may_tag is false" in rc.stderr

    r = _run_git("tag", cwd=s["repo"], env=s["env"])
    assert r.stdout.strip() == ""


def test_tag_created_locally_when_auto_push_false(env_setup: dict) -> None:
    s = env_setup
    policy = {
        "agent_name": "Test Agent",
        "agent_email": "test@agent",
        "allowed_types": ["feat", "fix"],
        "refuse_on_branches": ["main", "master"],
        "tags": {"agent_may_tag": True, "auto_push": False},
    }
    (s["claude"] / "git-policy.json").write_text(
        json.dumps(policy) + "\n", encoding="utf-8"
    )

    _run_script("commit", "--repo", str(s["repo"]), "-m", "feat: initial", env=s["env"])
    rc = _run_script(
        "tag", "v1.0.0", "-m", "release", "--repo", str(s["repo"]), env=s["env"]
    )
    assert rc.returncode == 0, rc.stderr

    r = _run_git("tag", cwd=s["repo"], env=s["env"])
    assert "v1.0.0" in r.stdout.split()

    r = _run_git("config", "--local", "--get", "user.name", cwd=s["repo"], env=s["env"])
    assert r.stdout.strip() == ""


def test_policy_edit_picked_up_by_next_commit(env_setup: dict) -> None:
    s = env_setup
    rc = _run_script(
        "commit", "--repo", str(s["repo"]), "-m", "wip: before", env=s["env"]
    )
    assert rc.returncode == 1

    rc = _run_script("policy", "add-type", "wip", env=s["env"])
    assert rc.returncode == 0, rc.stderr

    rc = _run_script(
        "commit", "--repo", str(s["repo"]), "-m", "wip: after", env=s["env"]
    )
    assert rc.returncode == 0, rc.stderr

    r = _run_git("log", "-1", "--format=%s", cwd=s["repo"], env=s["env"])
    assert r.stdout.strip() == "wip: after"
