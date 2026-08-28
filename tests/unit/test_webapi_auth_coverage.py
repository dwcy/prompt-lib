"""Regression tests: every mounted /api route must resolve the bearer-token gate."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import APIRouter

from cabal.webapi import security
from cabal.webapi.app import create_app


@pytest.fixture
def app(tmp_path: Path):
    return create_app(
        None,
        storage_path=tmp_path / "webapi.sqlite3",
        handshake_path=tmp_path / "handshake.json",
        token="unit-test-token",
    )


def test_shipped_app_has_no_unauthenticated_api_routes(app) -> None:
    assert security.unauthenticated_api_routes(app) == []


def test_router_without_the_auth_dependency_is_reported(app) -> None:
    rogue = APIRouter()
    rogue.add_api_route("/api/rogue", lambda: {}, methods=["GET"])
    app.router.routes.extend(rogue.routes)

    assert "/api/rogue" in security.unauthenticated_api_routes(app)


def test_construction_fails_loudly_when_a_route_is_unguarded(app) -> None:
    rogue = APIRouter()
    rogue.add_api_route("/api/rogue", lambda: {}, methods=["GET"])
    app.router.routes.extend(rogue.routes)

    with pytest.raises(RuntimeError, match="require_bearer_token"):
        security.assert_api_routes_authenticated(app)
