"""Knowledge graph, retrieval, context pack, preflight, and usage endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.envelope import envelope_response
from cabal.webapi.knowledge_service import (
    knowledge_context_pack,
    knowledge_digest,
    knowledge_graph,
    knowledge_preflight,
    knowledge_search,
    knowledge_summary,
    knowledge_usage,
)

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/knowledge")
def summary(request: Request):
    project = request.app.state.project
    data = knowledge_summary(project)
    return envelope_response(
        data=data,
        source="knowledge",
        precondition_digest=data["digest"],
    )


@router.get("/api/knowledge/graph")
def graph(
    request: Request,
    limit: int = 500,
    cursor: str | None = None,
    q: str | None = None,
    type: str | None = None,
    relation: str | None = None,
):
    return envelope_response(
        data=knowledge_graph(
            request.app.state.project,
            limit=limit,
            cursor=cursor,
            q=q,
            node_type=type,
            relation=relation,
        ),
        source="knowledge",
        precondition_digest=knowledge_digest(request.app.state.project),
    )


@router.get("/api/knowledge/search")
def search(
    request: Request,
    q: str = "",
    mode: Literal["fulltext", "semantic"] = "fulltext",
    limit: int = 10,
):
    return envelope_response(
        data=knowledge_search(
            request.app.state.project,
            query=q,
            mode=mode,
            limit=min(max(limit, 1), 50),
        ),
        source="knowledge",
    )


@router.get("/api/knowledge/context-pack")
def context_pack(
    request: Request,
    q: str = "",
    query: str = "",
    budget: Literal["tiny", "focused", "full"] = "focused",
):
    return envelope_response(
        data=knowledge_context_pack(
            request.app.state.project,
            query=query or q,
            budget=budget,
        ),
        source="knowledge",
    )


@router.get("/api/knowledge/preflight")
def preflight(request: Request, task: str = ""):
    return envelope_response(
        data=knowledge_preflight(request.app.state.project, task=task),
        source="knowledge",
    )


@router.get("/api/knowledge/usage")
def usage(request: Request, limit: int = 20):
    return envelope_response(
        data=knowledge_usage(request.app.state.project, limit=limit),
        source="knowledge",
    )
