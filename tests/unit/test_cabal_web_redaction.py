"""Unit coverage for Cabal web redaction helpers."""

from __future__ import annotations

from cabal.web.redaction import REDACTION_MARKER, contains_secret, redact_text, redact_url, redact_value


def _github_token() -> str:
    return "ghp_" + ("Z" * 36)


def _anthropic_key() -> str:
    return "sk-ant-" + ("y" * 32)


def test_redact_text_removes_known_token_shapes() -> None:
    token = _github_token()
    key = _anthropic_key()

    safe = redact_text(f"{token} and {key}")

    assert token not in safe
    assert key not in safe
    assert safe.count(REDACTION_MARKER) == 2


def test_redact_text_removes_assignment_like_secret_values() -> None:
    secret = "PASSWORD=" + ("p" * 24)

    assert redact_text(secret) == REDACTION_MARKER


def test_redact_value_recurses_nested_dicts_and_lists() -> None:
    token = _github_token()
    payload = {
        "access_token": token,
        "nested": [{"message": f"Bearer {token}"}],
        "safe": "visible",
    }

    safe = redact_value(payload)

    assert safe["access_token"] == REDACTION_MARKER
    assert safe["nested"][0]["message"] == REDACTION_MARKER
    assert safe["safe"] == "visible"


def test_redact_url_preserves_non_secret_query_values() -> None:
    token = _github_token()

    safe = redact_url(f"https://example.test/path?token={token}&name=cabal")

    assert token not in safe
    assert "token=[redacted]" in safe
    assert "name=cabal" in safe


def test_redact_text_handles_url_inside_sentence() -> None:
    token = _github_token()

    safe = redact_text(f"retry https://example.test/cb?api_key={token} now")

    assert token not in safe
    assert REDACTION_MARKER in safe
    assert safe.startswith("retry https://")


def test_contains_secret_detects_known_patterns() -> None:
    assert contains_secret("Bearer " + _github_token()) is True
    assert contains_secret("plain diagnostic") is False
