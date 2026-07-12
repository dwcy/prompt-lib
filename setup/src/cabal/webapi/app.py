"""FastAPI application factory: state wiring, auth, CORS, and envelope exception handlers."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from cabal.webapi import security
from cabal.webapi.actions import ActionRegistry
from cabal.webapi.audit import AuditRecorder, DiagnosticsRecorder
from cabal.webapi.envelope import ApiError, error_response, utc_now_iso
from cabal.webapi.jobs import JobManager
from cabal.webapi.routers import actions as actions_router
from cabal.webapi.routers import projects as projects_router
from cabal.webapi.routers import system as system_router
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
    app.state.handshake_path = Path(handshake_path) if handshake_path is not None else None
    app.state.started_at = utc_now_iso()
    app.state.request_shutdown = lambda: None

    security.apply_cors(app)
    # Flatten routes onto the app instead of include_router: FastAPI >= 0.139 defers
    # inclusion behind _IncludedRouter wrappers, which hides path/methods from
    # app.routes — the enumerable-route surface the action-safety contract relies on.
    # Auth dependencies are declared on each APIRouter, so they travel with the routes.
    app.router.routes.extend(system_router.router.routes)
    app.router.routes.extend(actions_router.router.routes)
    app.router.routes.extend(projects_router.router.routes)

    _register_exception_handlers(app)
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
