"""Tools routes: catalog metadata, bulk/single status probes, and full tool detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import ApiError, envelope_response
from cabal.webapi.tools_service import build_tool_detail, catalog_payload, probe_all_status, probe_one_status

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/tools")
def list_tools(request: Request):
    return envelope_response(data=catalog_payload(), source="tools")


@router.get("/api/tools/status")
def bulk_tools_status(request: Request):
    return envelope_response(data={"items": probe_all_status()}, source="tools")


@router.get("/api/tools/{key}/status")
def single_tool_status(request: Request, key: str):
    status = probe_one_status(key)
    if status is None:
        raise ApiError(404, "tool_not_found", f"Unknown tool {key!r}")
    return envelope_response(data=status, source="tools")


@router.get("/api/tools/{key}")
def tool_detail(request: Request, key: str):
    detail = build_tool_detail(key)
    if detail is None:
        raise ApiError(404, "tool_not_found", f"Unknown tool {key!r}")
    return envelope_response(data=detail, source="tools")
