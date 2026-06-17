# -*- coding: utf-8 -*-
"""GitHub collector for the dashboard — all `gh` subprocess I/O lives here."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from cabal.dashboard_links import parse_github_remote
from cabal.gh_accounts import _run_gh, parse_auth_status
from cabal.models.dashboard import (
    AvailabilityState,
    GitHubSection,
    GitRemote,
    PullRequest,
    WorkflowRun,
)

_GH = "gh"
_ORIGIN = "origin"
_RUN_LIMIT = "10"
_PR_LIMIT = "30"
_PR_STATE = "open"
_RUN_FIELDS = "databaseId,name,status,conclusion,headBranch,url,createdAt"
_PR_FIELDS = "number,title,author,url"

_HINT_NO_REMOTE = "no GitHub remote"
_HINT_NO_CLI = "gh CLI not found"
_HINT_NOT_AUTHED = "not authenticated — run `gh auth login`"
_HINT_TIMEOUT = "gh command timed out"


def collect_github(
    project: Path,
    current_branch: str | None,
    remotes: list[GitRemote],
) -> GitHubSection:
    """Collect GitHub Actions + open PRs for `project`'s chosen remote; never raises."""
    remote = _choose_remote(remotes)
    if remote is None:
        return GitHubSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NO_REMOTE)

    parsed = parse_github_remote(remote.url)
    owner_repo = f"{parsed[0]}/{parsed[1]}" if parsed is not None else None

    if shutil.which(_GH) is None:
        return GitHubSection(
            state=AvailabilityState.NO_CLI,
            hint=_HINT_NO_CLI,
            owner_repo=owner_repo,
            remote_used=remote.name,
        )

    if not _is_authed():
        return GitHubSection(
            state=AvailabilityState.NOT_AUTHED,
            hint=_HINT_NOT_AUTHED,
            owner_repo=owner_repo,
            remote_used=remote.name,
        )

    if owner_repo is None:
        return GitHubSection(
            state=AvailabilityState.ERROR,
            hint=_HINT_NO_REMOTE,
            remote_used=remote.name,
        )

    try:
        runs = _collect_runs(owner_repo, current_branch)
        pull_requests = _collect_pull_requests(owner_repo)
    except subprocess.TimeoutExpired:
        return GitHubSection(
            state=AvailabilityState.TIMEOUT,
            hint=_HINT_TIMEOUT,
            connected=True,
            owner_repo=owner_repo,
            remote_used=remote.name,
        )
    except (OSError, ValueError) as exc:
        return GitHubSection(
            state=AvailabilityState.ERROR,
            hint=str(exc),
            connected=True,
            owner_repo=owner_repo,
            remote_used=remote.name,
        )

    return GitHubSection(
        state=AvailabilityState.OK,
        connected=True,
        owner_repo=owner_repo,
        remote_used=remote.name,
        runs=runs,
        pull_requests=pull_requests,
    )


def _choose_remote(remotes: list[GitRemote]) -> GitRemote | None:
    github_remotes = [r for r in remotes if r.is_github]
    if not github_remotes:
        return None
    for remote in github_remotes:
        if remote.name == _ORIGIN:
            return remote
    return github_remotes[0]


def _is_authed() -> bool:
    _, out = _run_gh(["auth", "status"])
    accounts = parse_auth_status(out)
    return any(account.valid for account in accounts)


def _collect_runs(owner_repo: str, current_branch: str | None) -> list[WorkflowRun]:
    args = ["run", "list", "--repo", owner_repo]
    if current_branch:
        args += ["--branch", current_branch]
    args += ["--limit", _RUN_LIMIT, "--json", _RUN_FIELDS]
    code, out = _run_gh(args)
    if code != 0:
        return []
    return [
        WorkflowRun(
            name=str(item.get("name") or ""),
            branch=str(item.get("headBranch") or ""),
            status=str(item.get("status") or ""),
            conclusion=item.get("conclusion") or None,
            url=str(item.get("url") or ""),
            created_at=str(item.get("createdAt") or ""),
        )
        for item in _parse_json_list(out)
    ]


def _collect_pull_requests(owner_repo: str) -> list[PullRequest]:
    args = [
        "pr",
        "list",
        "--repo",
        owner_repo,
        "--state",
        _PR_STATE,
        "--limit",
        _PR_LIMIT,
        "--json",
        _PR_FIELDS,
    ]
    code, out = _run_gh(args)
    if code != 0:
        return []
    pull_requests: list[PullRequest] = []
    for item in _parse_json_list(out):
        author = item.get("author")
        login = author.get("login") if isinstance(author, dict) else None
        pull_requests.append(
            PullRequest(
                number=int(item.get("number") or 0),
                title=str(item.get("title") or ""),
                author=str(login or ""),
                url=str(item.get("url") or ""),
            )
        )
    return pull_requests


def _parse_json_list(out: str) -> list[dict]:
    data = json.loads(out or "[]")
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
