# -*- coding: utf-8 -*-
"""Azure DevOps collector for the dashboard — all `az` subprocess I/O lives here.

Org/project come from AZURE_DEVOPS_ORG / AZURE_DEVOPS_PROJECT (optionally
AZURE_DEVOPS_REPO to scope pull requests to one repo) rather than being parsed
from the git remote, since an Azure DevOps remote URL doesn't map unambiguously
to one org/project the way a GitHub remote does.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cabal.models.dashboard import (
    AvailabilityState,
    AzureDevOpsSection,
    AzurePipelineRun,
    AzurePullRequest,
)

_AZ = "az"
_TIMEOUT = 15
_ORG_ENV = "AZURE_DEVOPS_ORG"
_PROJECT_ENV = "AZURE_DEVOPS_PROJECT"
_REPO_ENV = "AZURE_DEVOPS_REPO"
_RUN_LIMIT = "10"
_PR_LIMIT = "30"

_HINT_NO_CLI = "az CLI not found"
_HINT_NOT_CONFIGURED = "set AZURE_DEVOPS_ORG and AZURE_DEVOPS_PROJECT"
_HINT_NOT_AUTHED = "not authenticated — run `az login`"
_HINT_TIMEOUT = "az command timed out"

_RUN_QUERY = (
    "[].{name:definition.name, status:status, result:result, "
    "sourceBranch:sourceBranch, url:_links.web.href}"
)
_PR_QUERY = "[].{id:pullRequestId, title:title, author:createdBy.displayName, repo:repository.name}"


def collect_azure_devops(project: Path) -> AzureDevOpsSection:
    """Collect Azure DevOps pipeline runs + open PRs for the configured org/project.

    `project` is unused today (org/project come from env, not the repo) but kept
    for signature parity with the other dashboard collectors. Never raises.
    """
    del project
    org = os.environ.get(_ORG_ENV)
    devops_project = os.environ.get(_PROJECT_ENV)
    if not org or not devops_project:
        return AzureDevOpsSection(state=AvailabilityState.NOT_LINKED, hint=_HINT_NOT_CONFIGURED)

    if shutil.which(_AZ) is None:
        return AzureDevOpsSection(
            state=AvailabilityState.NO_CLI, hint=_HINT_NO_CLI, org=org, project=devops_project
        )

    org_url = f"https://dev.azure.com/{org}"
    try:
        if not _is_authed():
            return AzureDevOpsSection(
                state=AvailabilityState.NOT_AUTHED,
                hint=_HINT_NOT_AUTHED,
                org=org,
                project=devops_project,
            )
        runs = _collect_runs(org_url, devops_project)
        pull_requests = _collect_pull_requests(org_url, devops_project)
    except subprocess.TimeoutExpired:
        return AzureDevOpsSection(
            state=AvailabilityState.TIMEOUT,
            hint=_HINT_TIMEOUT,
            connected=True,
            org=org,
            project=devops_project,
        )
    except OSError as exc:
        return AzureDevOpsSection(
            state=AvailabilityState.ERROR,
            hint=str(exc),
            connected=True,
            org=org,
            project=devops_project,
        )

    return AzureDevOpsSection(
        state=AvailabilityState.OK,
        connected=True,
        org=org,
        project=devops_project,
        runs=runs,
        pull_requests=pull_requests,
    )


def _run_az(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    return subprocess.run(
        [_AZ, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT,
    )


def _is_authed() -> bool:
    result = _run_az(["account", "show", "-o", "none"])
    return result is not None and result.returncode == 0


def _collect_runs(org_url: str, devops_project: str) -> list[AzurePipelineRun]:
    result = _run_az(
        [
            "pipelines",
            "runs",
            "list",
            "--organization",
            org_url,
            "--project",
            devops_project,
            "--top",
            _RUN_LIMIT,
            "--query",
            _RUN_QUERY,
            "-o",
            "json",
        ]
    )
    if result is None or result.returncode != 0:
        return []
    return [
        AzurePipelineRun(
            name=str(item.get("name") or ""),
            status=str(item.get("status") or ""),
            result=item.get("result") or None,
            source_branch=str(item.get("sourceBranch") or ""),
            url=str(item.get("url") or ""),
        )
        for item in _parse_json_list(result.stdout or "")
    ]


def _collect_pull_requests(org_url: str, devops_project: str) -> list[AzurePullRequest]:
    repo = os.environ.get(_REPO_ENV)
    args = [
        "repos",
        "pr",
        "list",
        "--organization",
        org_url,
        "--project",
        devops_project,
        "--status",
        "active",
        "--top",
        _PR_LIMIT,
        "--query",
        _PR_QUERY,
        "-o",
        "json",
    ]
    if repo:
        args += ["--repository", repo]
    result = _run_az(args)
    if result is None or result.returncode != 0:
        return []
    pull_requests: list[AzurePullRequest] = []
    for item in _parse_json_list(result.stdout or ""):
        pr_id = int(item.get("id") or 0)
        repo_name = str(item.get("repo") or repo or "")
        url = (
            f"{org_url}/{devops_project}/_git/{repo_name}/pullrequest/{pr_id}"
            if repo_name
            else ""
        )
        pull_requests.append(
            AzurePullRequest(
                id=pr_id,
                title=str(item.get("title") or ""),
                author=str(item.get("author") or ""),
                url=url,
            )
        )
    return pull_requests


def _parse_json_list(out: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(out or "[]")
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
