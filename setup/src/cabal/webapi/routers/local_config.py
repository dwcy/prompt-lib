"""Settings + Local Project Config routes (both project-scoped: local overrides and
scaffolding target the currently selected project)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import envelope_response
from cabal.webapi.local_config_service import local_config_actions
from cabal.webapi.settings_service import settings_entries

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


def _project(request: Request) -> Path | None:
    project = request.app.state.project
    return Path(project) if project is not None else None


@router.get("/api/settings")
def settings(request: Request):
    return envelope_response(data=settings_entries(_project(request)), source="settings")


@router.get("/api/local-config")
def local_config(request: Request, template: str | None = None, gitignore: str | None = None):
    data = local_config_actions(_project(request), template_stem=template, gitignore_stem=gitignore)
    return envelope_response(data=data, source="local_config")
