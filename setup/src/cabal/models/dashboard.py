# -*- coding: utf-8 -*-
"""Pure dataclasses for the project dashboard snapshot — no I/O, no Textual, no tokens."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class AvailabilityState(str, Enum):
    OK = "ok"
    NO_CLI = "no_cli"
    NOT_LINKED = "not_linked"
    NOT_AUTHED = "not_authed"
    TOKEN_MISSING = "token_missing"
    TOKEN_REJECTED = "token_rejected"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True)
class GitRemote:
    name: str
    url: str
    is_github: bool


@dataclass(frozen=True)
class GitWorktree:
    path: str
    branch: str | None
    detached: bool
    last_commit_at: str | None = None


@dataclass(frozen=True)
class GitBranch:
    name: str
    last_commit_at: str | None = None
    upstream_remote: str | None = None


@dataclass
class GitSection:
    state: AvailabilityState
    current_branch: str | None = None
    detached: bool = False
    local_branches: list[GitBranch] = field(default_factory=list)
    remotes: list[GitRemote] = field(default_factory=list)
    worktrees: list[GitWorktree] = field(default_factory=list)
    hint: str | None = None


@dataclass(frozen=True)
class WorkflowRun:
    name: str
    branch: str
    status: str
    conclusion: str | None
    url: str
    created_at: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    author: str
    url: str


@dataclass(frozen=True)
class RemoteBranch:
    name: str
    url: str


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    author: str
    url: str


@dataclass
class GitHubSection:
    state: AvailabilityState
    connected: bool = False
    owner_repo: str | None = None
    remote_used: str | None = None
    runs: list[WorkflowRun] = field(default_factory=list)
    pull_requests: list[PullRequest] = field(default_factory=list)
    remote_branches: list[RemoteBranch] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    hint: str | None = None


@dataclass(frozen=True)
class AzurePipelineRun:
    name: str
    status: str
    result: str | None
    source_branch: str
    url: str


@dataclass(frozen=True)
class AzurePullRequest:
    id: int
    title: str
    author: str
    url: str


@dataclass
class AzureDevOpsSection:
    state: AvailabilityState
    connected: bool = False
    org: str | None = None
    project: str | None = None
    runs: list[AzurePipelineRun] = field(default_factory=list)
    pull_requests: list[AzurePullRequest] = field(default_factory=list)
    hint: str | None = None


@dataclass(frozen=True)
class ProjectMember:
    name: str
    role: str | None = None


@dataclass
class SupabaseSection:
    state: AvailabilityState
    enrich_state: AvailabilityState = AvailabilityState.TOKEN_MISSING
    project_ref: str | None = None
    dashboard_url: str | None = None
    schema_visualizer_url: str | None = None
    db_location: str | None = None
    last_migration: str | None = None
    status: str | None = None
    region: str | None = None
    plan_name: str | None = None
    last_backup: str | None = None
    github_connected: bool | None = None
    members: list[ProjectMember] = field(default_factory=list)
    hint: str | None = None
    enrich_hint: str | None = None


@dataclass
class VercelSection:
    state: AvailabilityState
    enrich_state: AvailabilityState = AvailabilityState.TOKEN_MISSING
    project_name: str | None = None
    project_id: str | None = None
    dashboard_url: str | None = None
    latest_deployment_url: str | None = None
    latest_deployment_status: str | None = None
    team_plan: str | None = None
    region: str | None = None
    members: list[ProjectMember] = field(default_factory=list)
    hint: str | None = None
    enrich_hint: str | None = None


@dataclass
class DashboardSnapshot:
    project_path: str
    captured_at: str
    git: GitSection
    github: GitHubSection
    supabase: SupabaseSection
    vercel: VercelSection
    azure_devops: AzureDevOpsSection

    def to_cacheable(self) -> dict:
        """JSON-safe dict of all sections (enums → their value). Never raises; no tokens."""
        data = asdict(self)
        _coerce_enums(data)
        return data

    @classmethod
    def from_cached(cls, data: dict) -> DashboardSnapshot | None:
        """Reconstruct from a cached dict; return None on any malformed/old payload."""
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                project_path=str(data["project_path"]),
                captured_at=str(data["captured_at"]),
                git=_git_from(data["git"]),
                github=_github_from(data["github"]),
                supabase=_supabase_from(data["supabase"]),
                vercel=_vercel_from(data["vercel"]),
                azure_devops=_azure_devops_from(data["azure_devops"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _coerce_enums(data: dict) -> None:
    for section in ("git", "github", "supabase", "vercel", "azure_devops"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for key in ("state", "enrich_state"):
            value = block.get(key)
            if isinstance(value, AvailabilityState):
                block[key] = value.value


def _state(value: object) -> AvailabilityState:
    return AvailabilityState(value)


def _git_from(d: dict) -> GitSection:
    return GitSection(
        state=_state(d["state"]),
        current_branch=d.get("current_branch"),
        detached=bool(d.get("detached", False)),
        local_branches=[
            GitBranch(b["name"], b.get("last_commit_at"), b.get("upstream_remote"))
            for b in (d.get("local_branches") or [])
        ],
        remotes=[
            GitRemote(r["name"], r["url"], bool(r["is_github"]))
            for r in (d.get("remotes") or [])
        ],
        worktrees=[
            GitWorktree(w["path"], w.get("branch"), bool(w["detached"]), w.get("last_commit_at"))
            for w in (d.get("worktrees") or [])
        ],
        hint=d.get("hint"),
    )


def _github_from(d: dict) -> GitHubSection:
    return GitHubSection(
        state=_state(d["state"]),
        connected=bool(d.get("connected", False)),
        owner_repo=d.get("owner_repo"),
        remote_used=d.get("remote_used"),
        runs=[
            WorkflowRun(
                r["name"],
                r["branch"],
                r["status"],
                r.get("conclusion"),
                r["url"],
                r["created_at"],
            )
            for r in (d.get("runs") or [])
        ],
        pull_requests=[
            PullRequest(int(p["number"]), p["title"], p["author"], p["url"])
            for p in (d.get("pull_requests") or [])
        ],
        remote_branches=[
            RemoteBranch(b["name"], b["url"]) for b in (d.get("remote_branches") or [])
        ],
        issues=[
            Issue(int(i["number"]), i["title"], i["author"], i["url"])
            for i in (d.get("issues") or [])
        ],
        hint=d.get("hint"),
    )


def _azure_devops_from(d: dict) -> AzureDevOpsSection:
    return AzureDevOpsSection(
        state=_state(d["state"]),
        connected=bool(d.get("connected", False)),
        org=d.get("org"),
        project=d.get("project"),
        runs=[
            AzurePipelineRun(
                r["name"], r["status"], r.get("result"), r["source_branch"], r["url"]
            )
            for r in (d.get("runs") or [])
        ],
        pull_requests=[
            AzurePullRequest(int(p["id"]), p["title"], p["author"], p["url"])
            for p in (d.get("pull_requests") or [])
        ],
        hint=d.get("hint"),
    )


def _members_from(raw: object) -> list[ProjectMember]:
    return [ProjectMember(m["name"], m.get("role")) for m in (raw or [])]


def _supabase_from(d: dict) -> SupabaseSection:
    return SupabaseSection(
        state=_state(d["state"]),
        enrich_state=_state(
            d.get("enrich_state", AvailabilityState.TOKEN_MISSING.value)
        ),
        project_ref=d.get("project_ref"),
        dashboard_url=d.get("dashboard_url"),
        schema_visualizer_url=d.get("schema_visualizer_url"),
        db_location=d.get("db_location"),
        last_migration=d.get("last_migration"),
        status=d.get("status"),
        region=d.get("region"),
        plan_name=d.get("plan_name"),
        last_backup=d.get("last_backup"),
        github_connected=d.get("github_connected"),
        members=_members_from(d.get("members")),
        hint=d.get("hint"),
        enrich_hint=d.get("enrich_hint"),
    )


def _vercel_from(d: dict) -> VercelSection:
    return VercelSection(
        state=_state(d["state"]),
        enrich_state=_state(
            d.get("enrich_state", AvailabilityState.TOKEN_MISSING.value)
        ),
        project_name=d.get("project_name"),
        project_id=d.get("project_id"),
        dashboard_url=d.get("dashboard_url"),
        latest_deployment_url=d.get("latest_deployment_url"),
        latest_deployment_status=d.get("latest_deployment_status"),
        team_plan=d.get("team_plan"),
        region=d.get("region"),
        members=_members_from(d.get("members")),
        hint=d.get("hint"),
        enrich_hint=d.get("enrich_hint"),
    )
