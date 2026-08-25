"""Read-only snapshot route for local Claude and Codex scheduled tasks."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cabal.webapi import security
from cabal.webapi.envelope import envelope_response
from cabal.webapi.scheduled_tasks_service import scheduled_tasks_payload

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/scheduled-tasks")
def scheduled_tasks():
    return envelope_response(data=scheduled_tasks_payload(), source="scheduled_tasks")
