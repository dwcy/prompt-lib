"""Base FastAPI app factory: auth middleware + JSON-RPC dispatcher (T010, T020, T021).

Builds a FastAPI app that satisfies the foundational contracts:

* ``contracts/error-codes.md`` — unauthenticated requests return HTTP 401
  with the documented body BEFORE any JSON-RPC processing or task event is
  emitted; non-JSON ``Content-Type`` returns 415; non-POST verbs against
  ``/jsonrpc`` return 405.
* ``contracts/jsonrpc-methods.md`` — ``POST /jsonrpc`` parses the JSON-RPC
  envelope, looks the method up in the per-app registry
  (``app.state.method_registry``), and returns the registered handler's
  result wrapped in a JSON-RPC success envelope. Unknown methods return
  ``-32601`` with the method name in ``data``; uncaught handler exceptions
  are reduced to ``-32603`` with a UUID ``ref`` (no exception text leaks).
* ``data-model.md`` § AgentCard — the card published at
  ``/.well-known/agent-card.json`` is built once at startup, validated
  against the schema, and the adapter refuses to start on validation
  failure.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import jsonschema
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from a2a_bridge.protocol.agent_card import AgentCard, build_agent_card, validate_against_schema
from a2a_bridge.protocol.auth import compare_token
from a2a_bridge.protocol.jsonrpc import (
    ErrorCode,
    JsonRpcError,
    build_error_response,
    build_success_response,
    parse_request,
)
from a2a_bridge.protocol.logging import _emit, log_auth_fail, log_auth_ok

_DISCOVERY_PATH = "/.well-known/agent-card.json"
_JSONRPC_PATH = "/jsonrpc"
_BEARER_PREFIX = "Bearer "
_JSON_CONTENT_TYPE = "application/json"

MethodHandler = Callable[[dict[str, Any] | list[Any] | None], Awaitable[Any] | Any]


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, bearer_token: str) -> None:
        super().__init__(app)
        self._bearer_token = bearer_token

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method == "GET" and request.url.path == _DISCOVERY_PATH:
            return await call_next(request)

        peer = request.client.host if request.client else "unknown"
        header = request.headers.get("Authorization", "")

        if not header.startswith(_BEARER_PREFIX):
            log_auth_fail(peer=peer, reason="missing_or_wrong_scheme")
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

        provided = header[len(_BEARER_PREFIX) :]
        if not compare_token(provided, self._bearer_token):
            log_auth_fail(peer=peer, reason="token_mismatch")
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

        log_auth_ok(peer=peer)
        return await call_next(request)


class _ContentTypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method == "POST" and request.url.path == _JSONRPC_PATH:
            content_type = request.headers.get("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != _JSON_CONTENT_TYPE:
                return JSONResponse(
                    status_code=415,
                    content={"error": "expected application/json"},
                )
        return await call_next(request)


def _stub_agent_card(name: str) -> AgentCard:
    return build_agent_card(
        name=name,
        host="127.0.0.1",
        port=8000,
        skills=[
            {
                "id": "stub",
                "name": "stub",
                "description": "stub",
                "input_modes": ["text/plain"],
                "output_modes": ["text/plain"],
            }
        ],
    )


def build_app(
    *,
    bearer_token: str,
    name: str = "stub",
    agent_card: AgentCard | None = None,
) -> FastAPI:
    card = agent_card if agent_card is not None else _stub_agent_card(name)

    try:
        validate_against_schema(card)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(f"Agent Card failed schema validation: {exc.message}") from exc

    app = FastAPI()
    app.state.agent_card = card
    app.state.method_registry: dict[str, MethodHandler] = {}

    app.add_middleware(_ContentTypeMiddleware)
    app.add_middleware(_BearerAuthMiddleware, bearer_token=bearer_token)

    @app.get(_DISCOVERY_PATH)
    async def get_agent_card() -> dict[str, Any]:
        return app.state.agent_card.model_dump(mode="json")

    @app.post(_JSONRPC_PATH)
    async def jsonrpc(request: Request) -> Response:
        body = await request.body()

        try:
            parsed = parse_request(body)
        except JsonRpcError as exc:
            request_id = _peek_request_id(body)
            return JSONResponse(content=exc.to_envelope(request_id), status_code=200)

        handler = app.state.method_registry.get(parsed.method)
        if handler is None:
            envelope = build_error_response(
                parsed.id,
                ErrorCode.METHOD_NOT_FOUND,
                "Method not found",
                {"method": parsed.method},
            )
            return JSONResponse(content=envelope, status_code=200)

        try:
            result = handler(parsed.params)
            if hasattr(result, "__await__"):
                result = await result
        except JsonRpcError as exc:
            return JSONResponse(content=exc.to_envelope(parsed.id), status_code=200)
        except Exception as exc:
            envelope = build_error_response(
                parsed.id, ErrorCode.INTERNAL_ERROR, "Internal error", None
            )
            ref = envelope["error"]["data"]["ref"]
            _emit(
                "ERROR",
                "jsonrpc.internal_error",
                method=parsed.method,
                ref=ref,
                exc_type=type(exc).__name__,
            )
            return JSONResponse(content=envelope, status_code=200)

        if isinstance(result, Response):
            return result

        return JSONResponse(
            content=build_success_response(parsed.id, result), status_code=200
        )

    return app


def _peek_request_id(body: bytes) -> str | int | None:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(payload, dict):
        candidate = payload.get("id")
        if isinstance(candidate, str | int):
            return candidate
    return None
