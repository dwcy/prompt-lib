"""System routes: health with ModuleHealth rows, diagnostics, jobs, overview/dashboard, shutdown."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from cabal.dashboard_git_service import collect_current_branch
from cabal.webapi import security, sse
from cabal.webapi.dashboard_service import get_dashboard_section
from cabal.webapi.envelope import ApiError, ModuleHealth, envelope_response, utc_now_iso
from cabal.webapi.overview_service import build_overview, drift_flags
from cabal.webapi.probe_cache import (
    BRANCH_TTL_S,
    ENVIRONMENT_TTL_S,
    UPDATES_TTL_S,
    ttl_cached,
)
from cabal.webapi.terminal_service import build_terminal_summary
from cabal.env_detect import detect_env
from cabal.updates import check_for_updates

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

# Feature modules in the console navigation, including post-spec operational additions.
MODULE_KEYS = (
    "project_gate",
    "home_overview",
    "project_dashboard",
    "tools",
    "config_deploy",
    "cleanup_restore",
    "settings",
    "mcp",
    "local_config",
    "knowledge",
    "services",
    "package_security",
    "sessions",
    "scheduled_tasks",
    "account",
    "doctor",
    "model_assignments",
    "environment",
    "git_identity",
    "provider",
    "init_wizard",
    "codex",
    "diagnostics",
    "docs",
    "news",
)

# Modules whose routers are mounted; the rest honestly report "unavailable".
IMPLEMENTED_MODULES = frozenset(
    {
        "diagnostics",
        "project_gate",
        "home_overview",
        "project_dashboard",
        "tools",
        "config_deploy",
        "cleanup_restore",
        "settings",
        "local_config",
        "codex",
        "sessions",
        "scheduled_tasks",
        "account",
        "doctor",
        "model_assignments",
        "knowledge",
        "mcp",
        "services",
        "package_security",
        "environment",
        "git_identity",
        "provider",
        "init_wizard",
        "docs",
        "news",
    }
)


def _backend_version() -> str:
    try:
        return metadata.version("cabal")
    except metadata.PackageNotFoundError:
        return "0.0.0-dev"


_MACHINE_TOOLS = (
    ("git", "Git", "git_version"),
    ("python", "Python", "python"),
    ("node", "Node.js", "node"),
    ("npm", "npm", "npm"),
    ("pnpm", "pnpm", "pnpm"),
    ("bun", "Bun", "bun"),
    ("uv", "uv", "uv"),
    ("dotnet", ".NET SDK", "dotnet"),
    ("docker", "Docker", "docker"),
    ("podman", "Podman", "podman"),
    ("kubectl", "kubectl", "kubectl"),
    ("terraform", "Terraform", "terraform"),
    ("az", "Azure CLI", "az"),
    ("gcloud", "Google Cloud CLI", "gcloud"),
    ("aws", "AWS CLI", "aws"),
    ("bash", "Bash", "bash"),
    ("claude", "Claude CLI", "claude"),
    ("gh", "GitHub CLI", "gh"),
    ("gemini", "Gemini CLI", "gemini"),
    ("huggingface", "Hugging Face CLI", "huggingface"),
    ("codex", "Codex CLI", "codex"),
    ("opencode", "OpenCode", "opencode"),
    ("grok", "Grok CLI", "grok"),
    ("skills", "Skills CLI", "skills"),
    ("cursor", "Cursor", "cursor"),
    ("windsurf", "Windsurf", "windsurf"),
    ("copilot", "Copilot CLI", "copilot"),
    ("antigravity", "Antigravity", "antigravity"),
    ("vllm", "vLLM", "vllm"),
    ("vscode", "VS Code", "vscode"),
    ("rider", "Rider", "rider"),
    ("visualstudio", "Visual Studio", "visualstudio"),
    ("ollama", "Ollama", "ollama"),
    ("lm-studio", "LM Studio", "lm-studio"),
    ("sqlcmd", "SQLCMD", "sqlcmd"),
    ("psql", "PostgreSQL CLI", "psql"),
    ("supabase", "Supabase CLI", "supabase"),
    ("neonctl", "Neon CLI", "neonctl"),
    ("sqlite", "SQLite", "sqlite"),
    ("duckdb", "DuckDB", "duckdb"),
    ("zed", "Zed", "zed"),
    ("postman", "Postman", "postman"),
    ("hugo", "Hugo", "hugo"),
    ("uvicorn", "Uvicorn", "uvicorn"),
    ("dbeaver", "DBeaver", "dbeaver"),
    ("ssms", "SQL Server Management Studio", "ssms"),
)


def _machine_summary(environment: dict | None = None) -> dict:
    environment = environment or _cached_environment()
    tools = []
    for key, label, field in _MACHINE_TOOLS:
        value = environment.get(field)
        installed = bool(value)
        version = value if isinstance(value, str) else None
        tools.append({"key": key, "label": label, "installed": installed, "version": version})
    return {
        "os": environment.get("os") or "Unknown",
        "release": environment.get("release") or "",
        "package_manager": environment.get("pkg_manager"),
        "tools": tools,
    }


def _cabal_summary() -> dict:
    update = _cached_updates()
    return {
        "version": _backend_version(),
        "status": update.get("status", "error"),
        "local_hash": update.get("local_hash") or update.get("local"),
        "latest_hash": update.get("latest_hash") or update.get("remote") or update.get("hash"),
        "latest_date": update.get("latest_date") or update.get("date") or "",
        "behind_count": update.get("behind_count"),
        "branch": update.get("branch"),
        "subject": update.get("subject") or "",
    }


@ttl_cached(BRANCH_TTL_S)
def _cached_branch(project: Path) -> str | None:
    return collect_current_branch(project)


@ttl_cached(ENVIRONMENT_TTL_S)
def _cached_environment() -> dict:
    return detect_env()


@ttl_cached(UPDATES_TTL_S)
def _cached_updates() -> dict:
    return check_for_updates()


@router.get("/api/health")
def health(request: Request):
    modules = [
        ModuleHealth(
            module=key,
            state="ok" if key in IMPLEMENTED_MODULES else "unavailable",
            detail="" if key in IMPLEMENTED_MODULES else "module router not yet mounted",
            last_success_at=utc_now_iso() if key in IMPLEMENTED_MODULES else None,
        ).model_dump()
        for key in MODULE_KEYS
    ]
    project = request.app.state.project
    data = {
        "version": _backend_version(),
        "started_at": request.app.state.started_at,
        "modules": modules,
        "drift_flags": drift_flags(),
        "project_branch": _cached_branch(Path(project)) if project is not None else None,
    }
    return envelope_response(data=data, source="system")


@router.get("/api/system/overview")
def system_overview():
    environment = _cached_environment()
    data = {
        "cabal": _cabal_summary(),
        "machine": _machine_summary(environment),
        "terminal": build_terminal_summary(environment),
    }
    return envelope_response(data=data, source="system")


@router.get("/api/diagnostics")
def diagnostics(request: Request, limit: int | None = None, severity: str | None = None):
    events = request.app.state.diagnostics.list(limit=limit, severity=severity)
    return envelope_response(data={"events": events}, source="diagnostics")


@router.get("/api/diagnostics/stream")
def diagnostics_stream(request: Request):
    recorder = request.app.state.diagnostics
    if not sse.wants_event_stream(request.headers.get("accept", "")):
        # Non-SSE clients (health sweeps, curl) get a bounded snapshot instead of
        # an unbounded stream that would never terminate a plain GET.
        return envelope_response(data={"events": recorder.feed_after(0)}, source="diagnostics")
    last_event_id = sse.parse_last_event_id(request.headers.get("last-event-id"))
    return StreamingResponse(
        sse.diagnostics_event_stream(recorder, last_event_id),
        media_type=sse.SSE_MEDIA_TYPE,
    )


@router.get("/api/overview")
def overview(request: Request):
    project = request.app.state.project
    data, degraded, failed_sections = build_overview(Path(project) if project is not None else None)
    error = (
        {"code": "section_unavailable", "message": f"Sections unavailable: {', '.join(failed_sections)}"}
        if degraded
        else None
    )
    return envelope_response(
        data=data, source="overview", status="degraded" if degraded else "ok", error=error
    )


@router.get("/api/dashboard")
def dashboard(request: Request, section: Literal["git", "github", "supabase", "vercel"]):
    project = request.app.state.project
    if project is None:
        raise ApiError(404, "no_project_selected", "Select a project before requesting a dashboard section")
    data, stale = get_dashboard_section(Path(project), section)
    return envelope_response(data=data, source="dashboard", stale=stale)


@router.get("/api/jobs")
def list_jobs(request: Request):
    return envelope_response(data={"jobs": request.app.state.jobs.list_records()}, source="jobs")


@router.get("/api/jobs/{job_id}")
def get_job(request: Request, job_id: str):
    record = request.app.state.jobs.get_record(job_id)
    if record is None:
        raise ApiError(404, "job_not_found", f"Unknown job {job_id!r}")
    return envelope_response(data=record, source="jobs")


@router.get("/api/jobs/{job_id}/stream")
def stream_job(request: Request, job_id: str):
    manager = request.app.state.jobs
    job = manager.get(job_id)
    last_event_id = sse.parse_last_event_id(request.headers.get("last-event-id"))
    if job is not None:
        generator = sse.job_event_stream(job, last_event_id)
    else:
        record = request.app.state.storage.load_job(job_id)
        if record is None:
            raise ApiError(404, "job_not_found", f"Unknown job {job_id!r}")
        generator = sse.terminal_record_stream(record)
    return StreamingResponse(generator, media_type=sse.SSE_MEDIA_TYPE)


@router.post("/api/system/shutdown")
def shutdown(request: Request):
    from cabal import service_supervisor

    service_supervisor.shutdown_all()
    handshake_path = getattr(request.app.state, "handshake_path", None)
    if handshake_path is not None:
        security.remove_handshake(handshake_path, expected_token=request.app.state.token)
    request.app.state.request_shutdown()
    return envelope_response(data={"stopping": True}, source="system")
