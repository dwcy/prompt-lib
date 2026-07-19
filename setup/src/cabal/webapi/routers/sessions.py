"""Sessions router: bounded summaries and lazy per-session tabs."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import envelope_response
from cabal.webapi.sessions_service import session_detail_payload, list_sessions_payload

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/sessions")
def list_sessions(
    request: Request,
    project: str | None = None,
    sort: str = "date_desc",
    cursor: str | None = None,
    limit: int = 50,
):
    return envelope_response(
        data=list_sessions_payload(project=project, sort=sort, cursor=cursor, limit=limit),
        source="sessions",
    )


@router.get("/api/sessions/{session_id}")
def session_detail(
    request: Request,
    session_id: str,
    tab: Literal["overview", "activity", "raw", "triggers"] = "overview",
):
    return envelope_response(data=session_detail_payload(session_id, tab), source="sessions")
