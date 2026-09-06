"""Single shared redaction rule set for every Cabal surface (web, webapi, TUI exports)."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit

REDACTION_MARKER = "[redacted]"

# URL query parameters whose values are always secret-shaped. Broader than the
# dict-key set below: in a query string, names like "code" (OAuth) and bare
# "key" carry credentials, while as JSON keys they are ordinary data fields.
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

# Order matters: broad context patterns (assignments, Bearer) must run before the
# bare token-prefix patterns so "Bearer ghp_..." collapses to one marker.
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:Bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b(?:sk|sk-ant|sk-proj)-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b"),
)

URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+")

# High-entropy blob adjacent to a credential keyword; the entropy gate keeps long
# English words ("internationalization" ~= 3.6 bits/char) out of scope.
_CREDENTIAL_CONTEXT = re.compile(
    r"(?i)\b(?:token|secret|password|passwd|pwd|credential|api[-_ ]?key|auth)\b"
    r"[^\S\n]{0,3}[:=]?[^\S\n]{0,3}(?P<blob>[A-Za-z0-9+/_.~-]{20,})"
)
_ENTROPY_THRESHOLD_BITS = 3.8


def redact_text(value: object) -> str:
    """Return a string with credential-shaped fragments removed."""
    text = "" if value is None else str(value)
    text = _redact_urls_in_text(text)
    return _redact_secret_patterns(text)


def _redact_secret_patterns(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTION_MARKER, text)
    return _CREDENTIAL_CONTEXT.sub(_redact_entropic_blob, text)


def _redact_entropic_blob(match: re.Match[str]) -> str:
    blob = match.group("blob")
    if _shannon_entropy(blob) < _ENTROPY_THRESHOLD_BITS:
        return match.group(0)
    start, end = match.span("blob")
    offset = match.start()
    whole = match.group(0)
    return whole[: start - offset] + REDACTION_MARKER + whole[end - offset :]


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def redact_url(value: object) -> str:
    """Redact URL credentials and token-like query values while preserving shape."""
    raw = "" if value is None else str(value)
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return _redact_secret_patterns(raw)
    netloc = parts.netloc
    if parts.username or parts.password:
        host = parts.hostname or ""
        try:
            port = parts.port
        except ValueError:
            # Out-of-range port makes .port raise; dropping it keeps the
            # credential-masking path alive instead of crashing the caller.
            port = None
        if port:
            host = f"{host}:{port}"
        netloc = f"{REDACTION_MARKER}@{host}"
    query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        if _looks_secret_key(key):
            query.append((key, REDACTION_MARKER))
        else:
            query.append((key, _redact_secret_patterns(item)))
    return urlunsplit(
        (
            parts.scheme,
            netloc,
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
            if _looks_secret_dict_key(safe_key, item):
                result[safe_key] = REDACTION_MARKER
            else:
                result[safe_key] = redact_value(item)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value


def redact_env_display(name: str, value: str) -> str:
    """Display form of an environment value: fully masked for secret-named keys, pattern-scrubbed otherwise."""
    if _looks_secret_key(name):
        return REDACTION_MARKER if value else ""
    return redact_text(value)


def contains_secret(value: object) -> bool:
    """Return True when the raw value contains a known credential pattern."""
    text = "" if value is None else str(value)
    return redact_text(text) != text


def _looks_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in TOKEN_PARAM_NAMES or any(
        marker in normalized for marker in ("token", "secret", "password", "api_key", "apikey")
    )


def _looks_secret_dict_key(key: str, value: object = None) -> bool:
    """Narrower than the URL-param check: envelope fields like "code" and "key" are data."""
    # Metric keys such as tokens_in, input_tokens, and token_count carry numbers,
    # never credentials; the type guard is what lets the name test stay broad.
    if isinstance(value, (bool, int, float)):
        return False
    normalized = key.lower().replace("-", "_")
    if normalized in {"authorization", "signature"}:
        return True
    return any(
        marker in normalized
        for marker in ("token", "secret", "password", "api_key", "apikey")
    )


def _redact_urls_in_text(text: str) -> str:
    if "://" not in text or ("?" not in text and "@" not in text):
        return text
    return URL_PATTERN.sub(lambda match: redact_url(match.group(0)), text)


def _encode_query(query: list[tuple[str, str]]) -> str:
    parts = []
    for key, value in query:
        safe_value = REDACTION_MARKER if value == REDACTION_MARKER else quote_plus(value)
        parts.append(f"{quote_plus(key)}={safe_value}")
    return "&".join(parts)
