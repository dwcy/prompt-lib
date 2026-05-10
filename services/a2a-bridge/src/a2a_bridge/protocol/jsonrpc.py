"""JSON-RPC 2.0 envelope and error-code primitives (T013).

Implements the wire-format helpers required by ``contracts/error-codes.md``
and ``contracts/jsonrpc-methods.md``: request parsing with the standard
``-32700`` / ``-32600`` failure modes, an ``ErrorCode`` enum for the five
standard codes the bridge ever emits, a ``JsonRpcError`` exception that
carries straight to a JSON-RPC envelope, and explicit success/error envelope
builders.

Internal-error responses NEVER leak exception detail: any caller-supplied
``data`` payload for ``ErrorCode.INTERNAL_ERROR`` is reduced to a single
``ref`` UUID, generated here when missing.
"""

from __future__ import annotations

import json
import uuid
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

_REQUIRED_FIELDS = ("jsonrpc", "method")
_JSONRPC_VERSION = "2.0"


class ErrorCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


class ParsedRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    jsonrpc: str
    method: str
    params: dict[str, Any] | list[Any] | None = None
    id: str | int | None = None


class JsonRpcError(Exception):
    def __init__(
        self,
        code: int | ErrorCode,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.data = data

    def to_envelope(self, request_id: str | int | None) -> dict[str, Any]:
        return build_error_response(request_id, self.code, self.message, self.data)


def parse_request(body: bytes) -> ParsedRequest:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise JsonRpcError(ErrorCode.PARSE_ERROR, "Parse error") from exc

    if not isinstance(payload, dict):
        raise JsonRpcError(
            ErrorCode.INVALID_REQUEST,
            "Invalid Request",
            data={"missing": list(_REQUIRED_FIELDS)},
        )

    missing = [field for field in _REQUIRED_FIELDS if field not in payload]
    if missing:
        raise JsonRpcError(
            ErrorCode.INVALID_REQUEST,
            "Invalid Request",
            data={"missing": missing},
        )

    if payload.get("jsonrpc") != _JSONRPC_VERSION:
        raise JsonRpcError(
            ErrorCode.INVALID_REQUEST,
            "Invalid Request",
            data={"reason": "unsupported_jsonrpc_version"},
        )

    return ParsedRequest.model_validate(payload)


def build_error_response(
    request_id: str | int | None,
    code: int | ErrorCode,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code_int = int(code)
    error: dict[str, Any] = {"code": code_int, "message": message}

    if code_int == ErrorCode.INTERNAL_ERROR:
        ref = None
        if isinstance(data, dict):
            candidate = data.get("ref")
            if isinstance(candidate, str) and candidate:
                ref = candidate
        if ref is None:
            ref = str(uuid.uuid4())
        error["data"] = {"ref": ref}
    elif data is not None:
        error["data"] = data

    return {"jsonrpc": _JSONRPC_VERSION, "id": request_id, "error": error}


def build_success_response(
    request_id: str | int | None,
    result: Any,
) -> dict[str, Any]:
    return {"jsonrpc": _JSONRPC_VERSION, "id": request_id, "result": result}
