"""SnapshotEnvelope v2 models, precondition-digest helpers, and the redaction-at-boundary serializer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cabal.redaction import redact_value

SCHEMA_VERSION = "cabal-web.v2"

EnvelopeStatus = Literal["ok", "degraded", "error"]
ModuleState = Literal["ok", "loading", "degraded", "failed", "unavailable"]


class ModuleHealth(BaseModel):
    module: str
    state: ModuleState
    detail: str = ""
    last_success_at: str | None = None


class SnapshotEnvelope(BaseModel):
    schema_version: str = SCHEMA_VERSION
    captured_at: str
    status: EnvelopeStatus
    source: str
    stale: bool = False
    precondition_digest: str | None = None
    data: Any | None = None
    error: dict[str, Any] | None = None


class ApiError(Exception):
    """Machine-readable API failure carried to the envelope exception handler."""

    def __init__(
        self,
        http_status: int,
        code: str,
        message: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message
        self.extra = extra or {}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compute_precondition_digest(value: Any) -> str:
    """sha256 over canonical JSON — the shared digest namespace for mutation seeds."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def envelope_body(
    *,
    status: EnvelopeStatus = "ok",
    source: str = "backend",
    data: Any | None = None,
    error: dict[str, Any] | None = None,
    stale: bool = False,
    precondition_digest: str | None = None,
) -> dict[str, Any]:
    """Build a redacted v2 envelope dict; EVERY response body passes through here."""
    envelope = SnapshotEnvelope(
        captured_at=utc_now_iso(),
        status=status,
        source=source,
        stale=stale,
        precondition_digest=precondition_digest,
        data=data,
        error=error,
    )
    return redact_value(envelope.model_dump(mode="json"))


def envelope_response(
    *,
    http_status: int = 200,
    status: EnvelopeStatus = "ok",
    source: str = "backend",
    data: Any | None = None,
    error: dict[str, Any] | None = None,
    stale: bool = False,
    precondition_digest: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = envelope_body(
        status=status,
        source=source,
        data=data,
        error=error,
        stale=stale,
        precondition_digest=precondition_digest,
    )
    return JSONResponse(body, status_code=http_status, headers=headers)


def error_response(exc: ApiError, *, source: str = "backend") -> JSONResponse:
    error = {"code": exc.code, "message": exc.message, **exc.extra}
    return envelope_response(http_status=exc.http_status, status="error", source=source, error=error)
