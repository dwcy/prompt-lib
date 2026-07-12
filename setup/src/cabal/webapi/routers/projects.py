"""Project context/recents routes and the project.select action descriptor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from cabal import recent_projects
from cabal.webapi import security
from cabal.webapi.actions import ActionDescriptor, ActionOutcome
from cabal.webapi.envelope import ApiError, compute_precondition_digest, envelope_response, utc_now_iso

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

PROJECT_SELECT_ACTION_ID = "project.select"


def _live_recents() -> list[dict[str, str]]:
    """Recents with dead paths pruned from the persisted store (T030 dead-path pruning)."""
    live: list[dict[str, str]] = []
    for recent in recent_projects.load_recents():
        if not Path(recent.path).is_dir():
            recent_projects.remove_recent(Path(recent.path))
            continue
        live.append(
            {
                "path": recent.path,
                "name": recent.name,
                "action": recent.action,
                "last_opened": recent.last_opened,
            }
        )
    return live


def _project_context(request: Request) -> dict[str, Any]:
    project = request.app.state.project
    path = Path(project) if project is not None else None
    return {
        "path": str(path) if path is not None else "",
        "name": path.name if path is not None else "",
        "is_git_repo": bool(path is not None and (path / ".git").exists()),
        "recents": _live_recents(),
        "selected_at": getattr(request.app.state, "project_selected_at", None),
    }


@router.get("/api/project")
def get_project(request: Request):
    return envelope_response(data=_project_context(request), source="projects")


def _select_prepare(params: dict, _state: Any) -> dict:
    target = Path(params["path"])
    if not target.is_dir():
        raise ApiError(422, "params_invalid", f"{target} is not an existing directory")
    return {
        "summary": f"Switch active project to {target}",
        "commands": [],
        "files_changed": [],
        "scopes": ["project"],
        "backup": None,
        "removals": [],
    }


def _select_digest(_params: dict, state: Any) -> str:
    """Digest over the *current* active project, so a concurrent switch invalidates the ticket."""
    return compute_precondition_digest({"active_project": str(getattr(state, "project", None))})


def _select_execute(params: dict, state: Any) -> ActionOutcome:
    target = Path(params["path"])
    state.project = target
    state.project_selected_at = utc_now_iso()
    recent_projects.record_recent(target, "open")
    return ActionOutcome(
        data={"path": str(target), "name": target.name, "selected_at": state.project_selected_at}
    )


PROJECT_SELECT_DESCRIPTOR = ActionDescriptor(
    action_id=PROJECT_SELECT_ACTION_ID,
    module="project_gate",
    destructive=False,
    backup_policy=None,
    params_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
    prepare=_select_prepare,
    execute=_select_execute,
    compute_digest=_select_digest,
)
