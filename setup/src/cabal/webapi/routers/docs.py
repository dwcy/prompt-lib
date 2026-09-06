"""Read-only README summary and docs/ listing routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.docs_service import docs_payload, document_content
from cabal.webapi.envelope import ApiError, envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


def _project_path(state: Any) -> Path:
    project = getattr(state, "project", None)
    if project is None:
        raise ApiError(404, "no_project_selected", "Select a project before browsing docs")
    return Path(project)


@router.get("/api/docs")
def docs(request: Request):
    return envelope_response(data=docs_payload(_project_path(request.app.state)), source="docs")


@router.get("/api/docs/content")
def docs_content(request: Request, path: str):
    content = document_content(_project_path(request.app.state), path)
    if content is None:
        raise ApiError(404, "document_not_found", f"No docs/ markdown file at {path}")
    return envelope_response(data={"path": path, "content": content}, source="docs")
