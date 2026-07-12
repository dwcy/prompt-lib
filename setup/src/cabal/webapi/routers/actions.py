"""Action-safety HTTP surface: prepare, execute, and the mutation audit listing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import ApiError, envelope_response

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.post("/api/actions/{action_id}/prepare")
def prepare_action(request: Request, action_id: str, params: dict[str, Any] = Body(default={})):
    ticket = request.app.state.actions.prepare(action_id, params, request.app.state)
    return envelope_response(
        data=ticket,
        source="actions",
        precondition_digest=ticket.get("precondition_digest"),
    )


@router.post("/api/actions/{action_id}/execute")
def execute_action(request: Request, action_id: str, payload: dict[str, Any] = Body(...)):
    ticket_id = payload.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        raise ApiError(422, "params_invalid", "execute body requires a string 'ticket_id'")
    http_status, data = request.app.state.actions.execute(action_id, ticket_id, request.app.state)
    return envelope_response(data=data, source="actions", http_status=http_status)


@router.get("/api/audit")
def list_audit(request: Request):
    return envelope_response(data={"entries": request.app.state.audit.list()}, source="audit")
