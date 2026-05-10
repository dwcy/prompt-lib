"""Bearer-token primitives for the A2A bridge (T008).

Implements the constant-time compare and the startup token-strength validator
defined in ``data-model.md`` § BearerToken. The token value is never logged;
warnings about weak tokens carry only the length, never the value or any
prefix/suffix.
"""

import hmac

from a2a_bridge.protocol.logging import _emit

_MIN_TOKEN_LENGTH = 32


def compare_token(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    if len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)


def validate_token_at_startup(token: str | None) -> None:
    if token is None or not token.strip():
        raise ValueError("A2A_BEARER_TOKEN must be set")

    if len(token) < _MIN_TOKEN_LENGTH:
        _emit(
            "WARNING",
            "auth.weak_token",
            reason=f"token shorter than {_MIN_TOKEN_LENGTH} chars",
            length=len(token),
        )
