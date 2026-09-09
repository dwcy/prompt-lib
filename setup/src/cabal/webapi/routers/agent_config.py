"""Read-only agent config endpoints: the skills inventory (/api/agent-config/skills and its
detail/asset reads) plus the folder/file browser (/tree, /file) over the Claude/Codex/Antigravity
global and per-project local config directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.agent_config_service import build_agent_config_tree, read_agent_config_file
from cabal.webapi.envelope import envelope_response
from cabal.webapi.skills_service import (
    build_skill_detail,
    build_skill_inventory,
    read_skill_asset,
)

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])

AgentKey = Literal["claude", "codex", "antigravity"]
ScopeKey = Literal["global", "local"]


def _selected_project(state: Any) -> Path | None:
    project = getattr(state, "project", None)
    return Path(project) if project is not None else None


@router.get("/api/agent-config/skills")
def agent_config_skills(request: Request):
    project = _selected_project(request.app.state)
    data = build_skill_inventory(project)
    return envelope_response(data=data, source="agent_config")


@router.get("/api/agent-config/skills/detail")
def agent_config_skill_detail(request: Request, skill_id: str):
    project = _selected_project(request.app.state)
    data = build_skill_detail(skill_id, project)
    return envelope_response(data=data, source="agent_config")


@router.get("/api/agent-config/skills/asset")
def agent_config_skill_asset(request: Request, skill_id: str, rel_path: str):
    project = _selected_project(request.app.state)
    data = read_skill_asset(skill_id, rel_path, project)
    return envelope_response(data=data, source="agent_config")


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
