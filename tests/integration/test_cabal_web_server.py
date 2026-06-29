"""HTTP integration checks for the local Cabal web server."""

from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from cabal.web import serializers
from cabal.web.server import DEFAULT_HOST, create_server
from cabal.web.serializers import diagnostic_event


@pytest.fixture
def web_server(tmp_path):
    server = create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _get_json(url: str) -> tuple[str, dict]:
    with urlopen(url, timeout=5) as response:
        return response.headers["Content-Type"], json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> tuple[str, str]:
    with urlopen(url, timeout=5) as response:
        return response.headers["Content-Type"], response.read().decode("utf-8")


def _get_bytes(url: str) -> tuple[str, bytes]:
    with urlopen(url, timeout=5) as response:
        return response.headers["Content-Type"], response.read()


def _token() -> str:
    return "github_pat_" + ("q" * 30)


def test_create_server_defaults_to_localhost(tmp_path) -> None:
    server = create_server(tmp_path, port=0)
    try:
        assert server.server_address[0] == DEFAULT_HOST
    finally:
        server.server_close()


def test_static_shell_and_assets_are_served(web_server) -> None:
    _server, base_url = web_server

    html_type, html = _get_text(base_url + "/")
    css_type, css = _get_text(base_url + "/styles.css")
    js_type, js = _get_text(base_url + "/app.js")
    logo_type, logo = _get_bytes(base_url + "/brand/cabal-logo.png")

    assert html_type.startswith("text/html")
    assert css_type.startswith("text/css")
    assert js_type.startswith("application/javascript")
    assert logo_type.startswith("image/png")
    assert logo.startswith(b"\x89PNG")
    assert "Cabal" in html
    assert ":root" in css
    assert "/api/overview" in js


def test_api_json_content_type_and_health_payload(web_server) -> None:
    _server, base_url = web_server

    content_type, body = _get_json(base_url + "/api/health")

    assert content_type.startswith("application/json")
    assert body["data"]["app"] == "cabal-web"
    assert body["data"]["read_only"] is True


def test_mutating_method_rejected_over_http(web_server) -> None:
    _server, base_url = web_server

    request = Request(base_url + "/api/tools", method="POST")
    with pytest.raises(HTTPError) as excinfo:
        urlopen(request, timeout=5)

    assert excinfo.value.code == 405
    body = json.loads(excinfo.value.read().decode("utf-8"))
    assert body["status"] == "error"


def test_tools_endpoint_contains_catalog_keys_without_raw_fixture_tokens(monkeypatch, web_server) -> None:
    token = _token()
    monkeypatch.setattr(serializers, "_tool_unavailable_reason", lambda _key: None)
    _server, base_url = web_server

    _content_type, body = _get_json(base_url + "/api/tools")
    encoded = json.dumps(body)

    assert body["data"]["items"]
    assert {"key", "label", "status"} <= set(body["data"]["items"][0])
    assert token not in encoded


def test_knowledge_and_project_diagnostics_redact_fixture_tokens(monkeypatch, web_server) -> None:
    token = _token()
    server, base_url = web_server
    server.api._diagnostics.append(diagnostic_event("knowledge", "failed " + token))

    _content_type, body = _get_json(base_url + "/api/diagnostics")

    assert token not in json.dumps(body)
    assert "[redacted]" in json.dumps(body)
