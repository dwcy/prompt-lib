"""Codex Parity routes: the conversion audit and the Codex local-scaffold plan. The Codex
deploy tree / diff / extras are served by the shared config routes with target=codex."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.codex_service import codex_conversion, codex_local_actions
from cabal.webapi.envelope import envelope_response

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


def _project(request: Request) -> Path | None:
    project = request.app.state.project
    return Path(project) if project is not None else None


@router.get("/api/codex/conversion")
def codex_conversion_route(request: Request):
    return envelope_response(data=codex_conversion(), source="codex")


@router.get("/api/codex/local-config")
def codex_local_config_route(request: Request, template: str | None = None):
    return envelope_response(data=codex_local_actions(_project(request), template_stem=template), source="codex")
