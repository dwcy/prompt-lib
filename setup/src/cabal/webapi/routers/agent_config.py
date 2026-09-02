"""Read-only agent config folder/file browser: /api/agent-config/tree and /file, for the
Claude/Codex/Antigravity global and per-project local config directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.agent_config_service import build_agent_config_tree, read_agent_config_file
from cabal.webapi.envelope import envelope_response

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

AgentKey = Literal["claude", "codex", "antigravity"]
ScopeKey = Literal["global", "local"]


def _selected_project(state: Any) -> Path | None:
    project = getattr(state, "project", None)
    return Path(project) if project is not None else None


@router.get("/api/agent-config/tree")
def agent_config_tree(request: Request, agent: AgentKey, scope: ScopeKey):
    project = _selected_project(request.app.state)
    data = build_agent_config_tree(agent, scope, project)
    return envelope_response(data=data, source="agent_config")


@router.get("/api/agent-config/file")
def agent_config_file(request: Request, agent: AgentKey, scope: ScopeKey, rel_path: str):
    project = _selected_project(request.app.state)
    data = read_agent_config_file(agent, scope, project, rel_path)
    return envelope_response(data=data, source="agent_config")
