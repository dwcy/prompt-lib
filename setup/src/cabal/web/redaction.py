"""Back-compat shim: the shared redaction rule set now lives in cabal.redaction."""

from __future__ import annotations

from cabal.redaction import (
    REDACTION_MARKER,
    SECRET_PATTERNS,
    TOKEN_PARAM_NAMES,
    URL_PATTERN,
    contains_secret,
    redact_text,
    redact_url,
    redact_value,
)

__all__ = [
    "REDACTION_MARKER",
    "SECRET_PATTERNS",
    "TOKEN_PARAM_NAMES",
    "URL_PATTERN",
    "contains_secret",
    "redact_text",
    "redact_url",
    "redact_value",
]
