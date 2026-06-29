"""Contract checks for Cabal web local safety and redaction."""

from __future__ import annotations

import json

from cabal.web.api import WebApi
from cabal.web.redaction import REDACTION_MARKER, redact_text, redact_url, redact_value
from cabal.web.server import DEFAULT_HOST
from cabal.web.serializers import diagnostic_event


def _github_token() -> str:
    return "ghp_" + ("A" * 36)


def _openai_key() -> str:
    return "sk-" + ("b" * 32)


def test_default_bind_host_is_localhost_only() -> None:
    assert DEFAULT_HOST == "127.0.0.1"


def test_mutating_methods_are_rejected(tmp_path) -> None:
    api = WebApi(tmp_path)

    status, body = api.handle("/api/tools", "POST")

    assert status == 405
    assert body["status"] == "error"
    assert body["data"] is None


def test_nested_values_and_diagnostics_are_redacted() -> None:
    token = _github_token()
    payload = {
        "headers": {"Authorization": f"Bearer {token}"},
        "items": [f"API_KEY={_openai_key()}"],
        "diagnostic": diagnostic_event("tools", f"failed with {token}"),
    }

    safe = redact_value(payload)
    encoded = json.dumps(safe)

    assert token not in encoded
    assert _openai_key() not in encoded
    assert REDACTION_MARKER in encoded


def test_token_like_url_query_values_are_redacted() -> None:
    token = _github_token()

    safe = redact_url(f"https://example.test/callback?access_token={token}&state=ok")

    assert token not in safe
    assert "access_token=[redacted]" in safe
    assert "state=ok" in safe


def test_redaction_handles_urls_inside_diagnostic_text() -> None:
    token = _github_token()

    safe = redact_text(f"Open https://example.test/path?token={token} before retry.")

    assert token not in safe
    assert REDACTION_MARKER in safe


def test_api_diagnostics_do_not_return_raw_fixture_tokens(tmp_path) -> None:
    token = _github_token()
    api = WebApi(tmp_path)
    api._diagnostics.append(diagnostic_event("tools", f"probe failed with token {token}"))

    status, body = api.handle("/api/diagnostics")

    assert status == 200
    encoded = json.dumps(body)
    assert token not in encoded
    assert REDACTION_MARKER in encoded
