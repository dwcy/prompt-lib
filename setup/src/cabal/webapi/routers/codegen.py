# -*- coding: utf-8 -*-
"""Codegen module read routes: availability, run history, run detail, the pending
approval-gate intent, and stage bindings. Mutations go through the existing
prepare/execute ticket protocol via `actions_catalog/codegen.py`; this router only reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from cabal.webapi import codegen_service, security
from cabal.webapi.envelope import envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/codegen/availability")
def availability(request: Request):
    result = codegen_service.probe_availability(request.app.state.project)
    return envelope_response(
        data={"available": result.available, "reason": result.reason, "detail": result.detail},
        source="codegen",
    )


@router.get("/api/codegen/runs")
def runs(request: Request):
    data = {"runs": codegen_service.list_runs(request.app.state.project)}
    return envelope_response(data=data, source="codegen")


@router.get("/api/codegen/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    data = codegen_service.get_run(request.app.state.project, run_id)
    return envelope_response(data=data, source="codegen")


@router.get("/api/codegen/pending")
def pending(request: Request):
    data = codegen_service.get_pending_intent(request.app.state.project)
    return envelope_response(data=data, source="codegen")


@router.get("/api/codegen/bindings")
def bindings(request: Request):
    data = {"bindings": [vars(binding) for binding in codegen_service.list_stage_bindings()]}
    return envelope_response(data=data, source="codegen")
