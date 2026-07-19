"""US4 account, doctor, model assignments, and assistant-info routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.account_service import (
    account_payload,
    claude_info_payload,
    doctor_payload,
    models_payload,
)
from cabal.webapi.envelope import envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/account")
def account(request: Request):
    return envelope_response(data=account_payload(), source="account")


@router.get("/api/doctor")
def doctor(request: Request):
    project = request.app.state.project
    return envelope_response(
        data=doctor_payload(Path(project) if project is not None else None),
        source="doctor",
    )


@router.get("/api/models")
def models(request: Request):
    return envelope_response(data=models_payload(), source="models")


@router.get("/api/claude-info")
def claude_info(request: Request):
    project = request.app.state.project
    return envelope_response(
        data=claude_info_payload(Path(project) if project is not None else None),
        source="claude-info",
    )
