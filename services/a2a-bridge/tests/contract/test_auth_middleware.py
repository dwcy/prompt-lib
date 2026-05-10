"""Contract tests for the FastAPI bearer-token auth middleware (T009).

These tests assert the HTTP-level auth contract: requests to ``/jsonrpc``
without a valid ``Authorization: Bearer <token>`` header MUST be rejected
with ``401`` and the body documented in ``contracts/error-codes.md`` BEFORE
any task processing or SSE event would be emitted. Discovery
(``/.well-known/agent-card.json``) MUST remain unauthenticated per the A2A
spec.

Per Constitution Principle III, this file lands BEFORE its implementation
(T010). Until then every test is expected to fail with ImportError.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BEARER_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG_AND_AT_LEAST_32_CHARS"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from a2a_bridge.adapters.base import build_app

    app = build_app(bearer_token=BEARER_TOKEN)
    app.state.method_registry["test/auth-passthrough"] = lambda params: {"echoed": True}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_post_jsonrpc_without_authorization_header_returns_401(client: AsyncClient):
    response = await client.post("/jsonrpc", json={"jsonrpc": "2.0", "id": 1, "method": "noop"})

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}


async def test_post_jsonrpc_with_wrong_bearer_token_returns_401(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "noop"},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}


async def test_post_jsonrpc_with_correct_bearer_token_returns_200(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "test/auth-passthrough"},
        headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json() == {"jsonrpc": "2.0", "id": 1, "result": {"echoed": True}}


async def test_post_jsonrpc_with_non_bearer_scheme_returns_401(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "noop"},
        headers={"Authorization": f"NotBearer {BEARER_TOKEN}"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}


async def test_get_agent_card_without_auth_returns_200(client: AsyncClient):
    response = await client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    assert response.json()["name"] == "stub"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "NotBearer xyz"},
    ],
    ids=["no-header", "wrong-token", "wrong-scheme"],
)
async def test_401_response_body_contains_no_event_lines(
    client: AsyncClient, headers: dict[str, str]
):
    response = await client.post(
        "/jsonrpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/sendSubscribe"},
        headers=headers,
    )

    assert response.status_code == 401
    body = response.text
    for line in body.splitlines():
        assert not line.startswith("event:"), (
            f"401 response leaked an SSE event line before auth resolved: {line!r}"
        )
