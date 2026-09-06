"""Config-deployment routes: component tree + drift digest, per-file diff, target-only
extras, and backup sets — for both the claude and codex deploy targets."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request

from cabal.webapi import security
from cabal.webapi.config_service import build_config_tree, config_backups, config_diff, config_extras
from cabal.webapi.envelope import envelope_response

# Auth is declared at router level so routes keep the guard when flattened onto the app.
router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


@router.get("/api/config/tree")
def config_tree(request: Request, target: Literal["claude", "codex"]):
    payload = build_config_tree(target)
    # The drift digest doubles as the deploy action's precondition (data-model FR-008/030).
    return envelope_response(
        data={k: v for k, v in payload.items() if k != "digest"},
        source="config_deploy",
        precondition_digest=payload["digest"],
    )


@router.get("/api/config/diff")
def config_diff_route(request: Request, target: Literal["claude", "codex"], path: str):
    return envelope_response(data=config_diff(target, path), source="config_deploy")


@router.get("/api/config/extras")
def config_extras_route(request: Request, target: Literal["claude", "codex"]):
    return envelope_response(data=config_extras(target), source="cleanup_restore")


@router.get("/api/config/backups")
def config_backups_route(request: Request, kind: Literal["cleanup", "settings"]):
    return envelope_response(data=config_backups(kind), source="cleanup_restore")
