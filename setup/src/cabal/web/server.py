"""Local HTTP server for the Cabal web UI."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from cabal.web.api import WebApi

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
ASSET_ROOT = Path(__file__).resolve().parent / "assets"


class CabalWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], project_root: Path) -> None:
        super().__init__(server_address, CabalWebHandler)
        self.api = WebApi(project_root, host=server_address[0])
        self.project_root = Path(project_root).resolve()


class CabalWebHandler(BaseHTTPRequestHandler):
    server: CabalWebServer

    def do_GET(self) -> None:
        self._dispatch(send_body=True)

    def do_HEAD(self) -> None:
        self._dispatch(send_body=False)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "null")
        self.end_headers()

    def do_POST(self) -> None:
        self._api_response(*self.server.api.handle(self.path, "POST"))

    def do_PUT(self) -> None:
        self._api_response(*self.server.api.handle(self.path, "PUT"))

    def do_PATCH(self) -> None:
        self._api_response(*self.server.api.handle(self.path, "PATCH"))

    def do_DELETE(self) -> None:
        self._api_response(*self.server.api.handle(self.path, "DELETE"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _dispatch(self, *, send_body: bool) -> None:
        if self.path.startswith("/api/"):
            status, body = self.server.api.handle(self.path, "GET")
            self._api_response(status, body, send_body=send_body)
            return
        self._static_response(send_body=send_body)

    def _api_response(
        self, status: int, body: dict[str, Any], *, send_body: bool = True
    ) -> None:
        payload = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def _static_response(self, *, send_body: bool) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("", "/"):
            asset = ASSET_ROOT / "index.html"
        else:
            requested = path.lstrip("/")
            asset = (ASSET_ROOT / requested).resolve()
            if not _is_relative_to(asset, ASSET_ROOT):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        if not asset.exists() or not asset.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = asset.read_bytes()
        ctype = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        if asset.suffix == ".js":
            ctype = "application/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(payload)


def create_server(
    project_root: Path | str = ".",
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> CabalWebServer:
    return CabalWebServer((host, int(port)), Path(project_root).resolve())


def serve(
    project_root: Path | str = ".",
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    httpd = create_server(project_root, host=host, port=port)
    print(f"Cabal web UI: http://{host}:{httpd.server_port}/")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
        return True
    except ValueError:
        return False
