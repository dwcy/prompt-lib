"""Regression tests for type-preserving Web API redaction."""

from cabal.redaction import REDACTION_MARKER, redact_text, redact_value


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
