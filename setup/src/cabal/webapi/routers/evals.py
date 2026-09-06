# -*- coding: utf-8 -*-
"""Eval-harness module read routes: availability, benchmark definitions and validation,
run history, the A/B report, per-cell detail, and worktree listing. Mutations
(launch/cancel/resume/definition save+delete/worktree cleanup) go through the existing
prepare/execute ticket protocol via `actions_catalog/evals.py`; this router only reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from cabal.webapi import evals_definitions_service, evals_service, security
from cabal.webapi.envelope import envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/evals/availability")
def availability(request: Request):
    result = evals_service.probe_availability(request.app.state.project)
    return envelope_response(
        data={"available": result.available, "reason": result.reason, "detail": result.detail},
        source="evals",
    )


@router.get("/api/evals/definitions")
def definitions(request: Request):
    data = {"definitions": evals_definitions_service.list_definitions(request.app.state.project)}
    return envelope_response(data=data, source="evals")


@router.get("/api/evals/definitions/validate")
def definitions_validate(request: Request):
    data = evals_definitions_service.validate_definitions(request.app.state.project)
    return envelope_response(data=data, source="evals")


@router.get("/api/evals/runs")
def runs(request: Request):
    data = {
        "runs": evals_service.list_runs(request.app.state.project, storage=request.app.state.storage)
    }
    return envelope_response(data=data, source="evals")


@router.get("/api/evals/runs/{run_id}/report")
def run_report(request: Request, run_id: str):
    data = evals_service.get_report(request.app.state.project, run_id)
    return envelope_response(data=data, source="evals")


@router.get("/api/evals/runs/{run_id}/cells/{task}/{profile}/{rep}")
def cell_detail(request: Request, run_id: str, task: str, profile: str, rep: int):
    data = evals_service.get_cell_detail(request.app.state.project, run_id, task, profile, rep)
    return envelope_response(data=data, source="evals")


@router.get("/api/evals/worktrees")
def worktrees(request: Request):
    data = {"worktrees": evals_service.list_worktrees(request.app.state.project)}
    return envelope_response(data=data, source="evals")
