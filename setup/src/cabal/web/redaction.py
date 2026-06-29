"""Recursive redaction helpers for Cabal web payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit

REDACTION_MARKER = "[redacted]"

TOKEN_PARAM_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "key",
    "password",
    "refresh_token",
    "secret",
    "signature",
    "token",
}

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:Bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b(?:sk|sk-ant|sk-proj)-[A-Za-z0-9_-]{20,}\b"),
)

URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+")


def redact_text(value: object) -> str:
    """Return a string with credential-shaped fragments removed."""
    text = "" if value is None else str(value)
    text = _redact_urls_in_text(text)
    return _redact_secret_patterns(text)


def _redact_secret_patterns(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTION_MARKER, text)
    return text


def redact_url(value: object) -> str:
    """Redact token-like query-string values while preserving the URL shape."""
    raw = "" if value is None else str(value)
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return _redact_secret_patterns(raw)
    query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        if _looks_secret_key(key):
            query.append((key, REDACTION_MARKER))
        else:
            query.append((key, _redact_secret_patterns(item)))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            _encode_query(query),
            parts.fragment,
        )
    )


def redact_value(value):
    """Recursively redact strings inside JSON-like structures."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return redact_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            safe_key = str(key)
            if _looks_secret_key(safe_key):
                result[safe_key] = REDACTION_MARKER
            else:
                result[safe_key] = redact_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value


def contains_secret(value: object) -> bool:
    """Return True when the raw value contains a known credential pattern."""
    text = "" if value is None else str(value)
    return redact_text(text) != text


def _looks_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in TOKEN_PARAM_NAMES or any(
        marker in normalized for marker in ("token", "secret", "password", "api_key", "apikey")
    )


def _redact_urls_in_text(text: str) -> str:
    if "://" not in text or "?" not in text:
        return text
    return URL_PATTERN.sub(lambda match: redact_url(match.group(0)), text)


def _encode_query(query: list[tuple[str, str]]) -> str:
    parts = []
    for key, value in query:
        safe_value = REDACTION_MARKER if value == REDACTION_MARKER else quote_plus(value)
        parts.append(f"{quote_plus(key)}={safe_value}")
    return "&".join(parts)
