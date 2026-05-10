"""Contract tests for HTTP-level errors on ``/jsonrpc`` (T012).

Covers the 405 (non-POST) and 415 (non-JSON content-type) rows of the
HTTP-level error table in ``contracts/error-codes.md``. The 401 row is
already covered by ``test_auth_middleware.py``; this file deliberately
does not duplicate it.

Per Constitution Principle III, this file lands BEFORE its implementation
(T013/T020 will add 415 enforcement). Until then the 415 tests are expected
to fail because the stub adapter returns 200 for any content-type.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BEARER_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG_AND_AT_LEAST_32_CHARS"
AUTH_HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from a2a_bridge.adapters.base import build_app

    app = build_app(bearer_token=BEARER_TOKEN)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 415 Unsupported Media Type — POST with non-JSON Content-Type
# ---------------------------------------------------------------------------


async def test_post_jsonrpc_with_text_plain_returns_415(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        content=b"hi",
        headers={**AUTH_HEADERS, "Content-Type": "text/plain"},
    )

    assert response.status_code == 415


async def test_post_jsonrpc_with_text_plain_returns_documented_body(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        content=b"hi",
        headers={**AUTH_HEADERS, "Content-Type": "text/plain"},
    )

    assert response.json() == {"error": "expected application/json"}


async def test_post_jsonrpc_with_application_json_does_not_return_415(client: AsyncClient):
    response = await client.post(
        "/jsonrpc",
        content=b"{}",
        headers={**AUTH_HEADERS, "Content-Type": "application/json"},
    )

    assert response.status_code != 415


# ---------------------------------------------------------------------------
# 405 Method Not Allowed — non-POST verbs against /jsonrpc
# ---------------------------------------------------------------------------


async def test_get_jsonrpc_returns_405(client: AsyncClient):
    response = await client.get("/jsonrpc", headers=AUTH_HEADERS)

    assert response.status_code == 405


async def test_put_jsonrpc_returns_405(client: AsyncClient):
    response = await client.put(
        "/jsonrpc",
        content=b"{}",
        headers={**AUTH_HEADERS, "Content-Type": "application/json"},
    )

    assert response.status_code == 405
