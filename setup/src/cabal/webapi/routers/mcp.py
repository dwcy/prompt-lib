"""MCP connector endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import envelope_response
from cabal.webapi.mcp_service import list_mcp_payload, mcp_digest, mcp_row_payload

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/mcp")
def list_mcp(request: Request):
    return envelope_response(
        data=list_mcp_payload(request.app.state),
        source="mcp",
        precondition_digest=mcp_digest(request.app.state),
    )


@router.get("/api/mcp/{name}/status")
def mcp_status(request: Request, name: str):
    return envelope_response(
        data=mcp_row_payload(request.app.state, name),
        source="mcp",
        precondition_digest=mcp_digest(request.app.state, name),
    )
