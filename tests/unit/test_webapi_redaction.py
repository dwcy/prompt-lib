"""Regression tests for type-preserving Web API redaction."""

from cabal.redaction import (
    REDACTION_MARKER,
    contains_secret,
    redact_text,
    redact_url,
    redact_value,
)


def test_numeric_token_metrics_are_not_mistaken_for_credentials() -> None:
    payload = redact_value(
        {
            "tokens_in": 10_000,
            "input_tokens": 10,
            "token_count": 1_000,
            "github_token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "clientSecret": "sensitive",
        }
    )

    assert payload["tokens_in"] == 10_000
    assert payload["input_tokens"] == 10
    assert payload["token_count"] == 1_000
    assert payload["github_token"] == REDACTION_MARKER
    assert payload["clientSecret"] == REDACTION_MARKER


def test_credential_url_with_out_of_range_port_is_masked_not_crashed() -> None:
    hostile = "https://user:hunter2@example.test:99999999/path"

    redacted = redact_text(f"connecting to {hostile}")

    assert "hunter2" not in redacted
    assert REDACTION_MARKER in redacted


def _github_token() -> str:
    return "ghp_" + ("Z" * 36)


def _anthropic_key() -> str:
    return "sk-ant-" + ("y" * 32)


def test_known_token_shapes_are_removed_from_free_text() -> None:
    token = _github_token()
    key = _anthropic_key()

    safe = redact_text(f"{token} and {key}")

    assert token not in safe
    assert key not in safe
    assert safe.count(REDACTION_MARKER) == 2


def test_assignment_shaped_secret_value_is_removed() -> None:
    secret = "PASSWORD=" + ("p" * 24)

    assert redact_text(secret) == REDACTION_MARKER


def test_redaction_recurses_through_nested_dicts_and_lists() -> None:
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


def test_url_query_redaction_preserves_non_secret_values() -> None:
    token = _github_token()

    safe = redact_url(f"https://example.test/path?token={token}&name=cabal")

    assert token not in safe
    assert f"token={REDACTION_MARKER}" in safe
    assert "name=cabal" in safe


def test_url_embedded_in_a_sentence_is_redacted_in_place() -> None:
    token = _github_token()

    safe = redact_text(f"retry https://example.test/cb?api_key={token} now")

    assert token not in safe
    assert REDACTION_MARKER in safe
    assert safe.startswith("retry https://")


def test_contains_secret_distinguishes_credentials_from_diagnostics() -> None:
    assert contains_secret("Bearer " + _github_token()) is True
    assert contains_secret("plain diagnostic") is False


def test_credential_named_keys_are_masked_even_mid_name() -> None:
    payload = redact_value(
        {
            "SECRET_KEY": "dj4ngo-s3cr3t",
            "password_hash": "not-a-known-shape",
            "api_key_id": "AKIA-lookalike",
            "token_preview": "abcd1234",
        }
    )

    assert all(value == REDACTION_MARKER for value in payload.values())
