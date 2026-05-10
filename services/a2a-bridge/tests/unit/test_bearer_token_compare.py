"""Contract tests for the bearer-token compare and startup-validation helpers (T007).

Pins the constant-time compare contract and the startup token-strength rules
defined in ``data-model.md`` § BearerToken. Per Constitution Principle III,
this file lands BEFORE its implementation (T008).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

SECRET_TOKEN = "SECRET_TOKEN_12345_DO_NOT_LOG_AND_AT_LEAST_32_CHARS"
SHORT_TOKEN = "short-but-not-empty"
LONG_TOKEN = "a" * 32


def _import_auth_module():
    from a2a_bridge.protocol import auth

    return auth


def test_auth_module_exposes_compare_token_and_validate_token_at_startup():
    auth = _import_auth_module()

    assert hasattr(auth, "compare_token")
    assert hasattr(auth, "validate_token_at_startup")


async def test_delegation_client_supports_async_context_manager():
    from a2a_bridge.client.delegation import DelegationClient

    client = DelegationClient(peer_url="http://127.0.0.1:8766", peer_bearer_token=LONG_TOKEN)

    async with client as entered:
        assert entered is client


def test_compare_token_returns_true_for_exact_match():
    auth = _import_auth_module()

    assert auth.compare_token(SECRET_TOKEN, SECRET_TOKEN) is True


def test_compare_token_returns_false_for_mismatch():
    auth = _import_auth_module()

    assert auth.compare_token("wrong-token-value-padded-to-be-long-enough", SECRET_TOKEN) is False


def test_compare_token_returns_false_for_empty_provided_token():
    auth = _import_auth_module()

    assert auth.compare_token("", SECRET_TOKEN) is False


def test_compare_token_returns_false_for_empty_expected_token():
    auth = _import_auth_module()

    assert auth.compare_token(SECRET_TOKEN, "") is False


def test_compare_token_does_not_raise_on_unusual_inputs():
    auth = _import_auth_module()

    auth.compare_token("", "")
    auth.compare_token("a", "b")
    auth.compare_token("a" * 1024, "b" * 1024)


def test_compare_token_uses_hmac_compare_digest():
    auth = _import_auth_module()

    with patch("a2a_bridge.protocol.auth.hmac.compare_digest", return_value=True) as mock_cd:
        result = auth.compare_token(SECRET_TOKEN, SECRET_TOKEN)

    assert mock_cd.called
    assert result is True


def test_compare_token_does_not_log_token_value(capsys):
    auth = _import_auth_module()

    auth.compare_token(SECRET_TOKEN, SECRET_TOKEN)
    auth.compare_token("definitely-the-wrong-value-do-not-log", SECRET_TOKEN)

    captured = capsys.readouterr()
    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err
    assert "definitely-the-wrong-value-do-not-log" not in captured.out
    assert "definitely-the-wrong-value-do-not-log" not in captured.err


def test_validate_token_at_startup_raises_on_none():
    auth = _import_auth_module()

    with pytest.raises(ValueError):
        auth.validate_token_at_startup(None)


def test_validate_token_at_startup_raises_on_empty_string():
    auth = _import_auth_module()

    with pytest.raises(ValueError):
        auth.validate_token_at_startup("")


def test_validate_token_at_startup_raises_on_whitespace_only():
    auth = _import_auth_module()

    with pytest.raises(ValueError):
        auth.validate_token_at_startup("   \t\n  ")


def test_validate_token_at_startup_raises_for_short_token():
    auth = _import_auth_module()

    with pytest.raises(ValueError):
        auth.validate_token_at_startup(SHORT_TOKEN)


def test_validate_token_at_startup_accepts_token_of_32_or_more_chars(capsys):
    auth = _import_auth_module()

    auth.validate_token_at_startup(LONG_TOKEN)

    captured = capsys.readouterr()
    assert "warn" not in captured.out.lower()
    assert "warn" not in captured.err.lower()


def test_validate_token_at_startup_does_not_log_token_value(capsys):
    auth = _import_auth_module()

    try:
        auth.validate_token_at_startup(SHORT_TOKEN)
    except ValueError:
        pass
    try:
        auth.validate_token_at_startup(LONG_TOKEN)
    except ValueError:
        pass

    captured = capsys.readouterr()
    assert SHORT_TOKEN not in captured.out
    assert SHORT_TOKEN not in captured.err
    assert LONG_TOKEN not in captured.out
    assert LONG_TOKEN not in captured.err
