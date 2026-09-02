"""FastAPI application factory: state wiring, auth, CORS, and envelope exception handlers."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from cabal.webapi import security
from cabal.webapi.actions import ActionRegistry
from cabal.webapi.actions_catalog import config as config_actions
from cabal.webapi.actions_catalog import codegen as codegen_actions
from cabal.webapi.actions_catalog import codex as codex_actions
from cabal.webapi.actions_catalog import evals as evals_actions
from cabal.webapi.actions_catalog import git_health as git_health_actions
from cabal.webapi.actions_catalog import knowledge as knowledge_actions
from cabal.webapi.actions_catalog import jobs as jobs_actions
from cabal.webapi.actions_catalog import local_config as local_config_actions
from cabal.webapi.actions_catalog import mcp as mcp_actions
from cabal.webapi.actions_catalog import sessions as sessions_actions
from cabal.webapi.actions_catalog import services as services_actions
from cabal.webapi.actions_catalog import scheduled_tasks as scheduled_tasks_actions
from cabal.webapi.actions_catalog import tools as tools_actions
from cabal.webapi.actions_catalog import system as system_actions
from cabal.webapi.audit import AuditRecorder, DiagnosticsRecorder
from cabal.webapi.envelope import ApiError, error_response, utc_now_iso
from cabal.webapi.jobs import JobManager
from cabal.webapi.routers import account as account_router
from cabal.webapi.routers import actions as actions_router
from cabal.webapi.routers import agent_config as agent_config_router
from cabal.webapi.routers import codegen as codegen_router
from cabal.webapi.routers import codex as codex_router
from cabal.webapi.routers import config as config_router
from cabal.webapi.routers import docs as docs_router
from cabal.webapi.routers import environment as environment_router
from cabal.webapi.routers import evals as evals_router
from cabal.webapi.routers import knowledge as knowledge_router
from cabal.webapi.routers import local_config as local_config_router
from cabal.webapi.routers import mcp as mcp_router
from cabal.webapi.routers import news as news_router
from cabal.webapi.routers import projects as projects_router
from cabal.webapi.routers import security_scan as security_scan_router
from cabal.webapi.routers import sessions as sessions_router
from cabal.webapi.routers import services as services_router
from cabal.webapi.routers import scheduled_tasks as scheduled_tasks_router
from cabal.webapi.routers import system as system_router
from cabal.webapi.routers import tools as tools_router
from cabal.webapi.storage import Storage, WriteGuard

_HTTP_ERROR_CODES = {
    401: "unauthorized",
    404: "not_found",
    405: "method_not_allowed",
    422: "params_invalid",
}


def create_app(
    project: Path | None = None,
    *,
    storage_path: Path | None = None,
    handshake_path: Path | None = None,
    token: str | None = None,
) -> FastAPI:
    """Build the backend in-process (no socket bind); callers own serving and handshake."""
    app = FastAPI(title="cabal-backend", docs_url=None, redoc_url=None, openapi_url=None)

    write_guard = WriteGuard()
    storage = Storage(storage_path, write_guard=write_guard)
    diagnostics = DiagnosticsRecorder(storage)
    audit = AuditRecorder(storage, diagnostics)

    app.state.token = token or security.generate_token()
    app.state.project = Path(project) if project is not None else None
    app.state.project_selected_at = utc_now_iso() if project is not None else None
    app.state.storage = storage
    app.state.write_guard = write_guard
    app.state.diagnostics = diagnostics
    app.state.audit = audit
    app.state.jobs = JobManager(storage)
    app.state.actions = ActionRegistry(storage=storage, audit=audit)
    app.state.actions.register(projects_router.PROJECT_SELECT_DESCRIPTOR)
    app.state.actions.register(jobs_actions.JOBS_CANCEL_DESCRIPTOR)
    for descriptor in projects_router.PROJECT_LIFECYCLE_DESCRIPTORS:
        app.state.actions.register(descriptor)
    app.state.actions.register(tools_actions.TOOLS_INSTALL_DESCRIPTOR)
    app.state.actions.register(tools_actions.TOOLS_UPDATE_DESCRIPTOR)
    app.state.actions.register(system_actions.SYSTEM_UPDATE_DESCRIPTOR)
    for descriptor in config_actions.CONFIG_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in local_config_actions.LOCAL_CONFIG_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in git_health_actions.GIT_HEALTH_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in codex_actions.CODEX_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in sessions_actions.OBSERVABILITY_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in knowledge_actions.KNOWLEDGE_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in mcp_actions.MCP_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in services_actions.SERVICES_DESCRIPTORS:
        app.state.actions.register(descriptor)
    app.state.actions.register(scheduled_tasks_actions.SCHEDULED_TASKS_DELETE_DESCRIPTOR)
    for descriptor in security_scan_router.SECURITY_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in environment_router.ENVIRONMENT_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in codegen_actions.CODEGEN_DESCRIPTORS:
        app.state.actions.register(descriptor)
    for descriptor in evals_actions.EVALS_DESCRIPTORS:
        app.state.actions.register(descriptor)
    app.state.handshake_path = Path(handshake_path) if handshake_path is not None else None
    app.state.started_at = utc_now_iso()
    app.state.request_shutdown = lambda: None
    app.state.news_items = None
    app.state.news_health = None

    security.apply_cors(app)
    # Flatten routes onto the app instead of include_router: FastAPI >= 0.139 defers
    # inclusion behind _IncludedRouter wrappers, which hides path/methods from
    # app.routes — the enumerable-route surface the action-safety contract relies on.
    # Auth dependencies are declared on each APIRouter, so they travel with the routes.
    app.router.routes.extend(system_router.router.routes)
    app.router.routes.extend(actions_router.router.routes)
    app.router.routes.extend(projects_router.router.routes)
    app.router.routes.extend(tools_router.router.routes)
    app.router.routes.extend(config_router.router.routes)
    app.router.routes.extend(local_config_router.router.routes)
    app.router.routes.extend(codex_router.router.routes)
    app.router.routes.extend(sessions_router.router.routes)
    app.router.routes.extend(account_router.router.routes)
    app.router.routes.extend(knowledge_router.router.routes)
    app.router.routes.extend(mcp_router.router.routes)
    app.router.routes.extend(news_router.router.routes)
    app.router.routes.extend(services_router.router.routes)
    app.router.routes.extend(scheduled_tasks_router.router.routes)
    app.router.routes.extend(security_scan_router.router.routes)
    app.router.routes.extend(environment_router.router.routes)
    app.router.routes.extend(docs_router.router.routes)
    app.router.routes.extend(codegen_router.router.routes)
    app.router.routes.extend(evals_router.router.routes)
    app.router.routes.extend(agent_config_router.router.routes)

    _register_exception_handlers(app)
    security.assert_api_routes_authenticated(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError):
        return error_response(exc)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException):
        code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        return error_response(ApiError(exc.status_code, code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        message = "; ".join(str(item.get("msg", "invalid")) for item in exc.errors()) or "invalid request"
        return error_response(ApiError(422, "params_invalid", message))
