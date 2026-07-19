"""System routes: health with ModuleHealth rows, diagnostics, jobs, overview/dashboard, shutdown."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from cabal.webapi import security, sse
from cabal.webapi.dashboard_service import get_dashboard_section
from cabal.webapi.envelope import ApiError, ModuleHealth, envelope_response, utc_now_iso
from cabal.webapi.overview_service import build_overview, drift_flags

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

# The 22 module keys of the spec's Feature Module Breakdown, in table order.
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
    "account",
    "doctor",
    "model_assignments",
    "environment",
    "git_identity",
    "provider",
    "init_wizard",
    "codex",
    "diagnostics",
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
    }
)


def _backend_version() -> str:
    try:
        return metadata.version("cabal")
    except metadata.PackageNotFoundError:
        return "0.0.0-dev"


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
    data = {
        "version": _backend_version(),
        "started_at": request.app.state.started_at,
        "modules": modules,
        "drift_flags": drift_flags(),
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
