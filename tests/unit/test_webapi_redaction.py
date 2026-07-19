"""Regression tests for type-preserving Web API redaction."""

from cabal.redaction import REDACTION_MARKER, redact_value


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
