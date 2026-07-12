"""Console entry point for `cabal-backend`: bind, write handshake atomically, serve, clean up."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import platformdirs
import uvicorn

from cabal.webapi import security
from cabal.webapi.app import create_app
from cabal.webapi.envelope import utc_now_iso


def default_handshake_path() -> Path:
    return Path(platformdirs.user_data_dir("cabal")) / "webapi-handshake.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabal-backend",
        description="Local web API backend for the Cabal desktop workspace.",
    )
    parser.add_argument("--project", type=Path, default=None, help="Project directory to scope project modules to")
    parser.add_argument("--storage-path", type=Path, default=None, help="SQLite file for jobs/tickets/audit/diagnostics")
    parser.add_argument("--handshake-path", type=Path, default=None, help="Where to write the cabal-handshake.v1 file")
    parser.add_argument("--token", default=None, help="Bearer token (generated when omitted)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Bind port; 0 = OS-assigned ephemeral port")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handshake_path = args.handshake_path or default_handshake_path()

    # read_handshake yields None for absent, corrupt, AND stale (dead-pid) files, so a
    # non-None result always means a live backend; stale files are replaced by the
    # fresh atomic write below.
    existing = security.read_handshake(handshake_path)
    if existing is not None:
        print(
            f"cabal-backend: another instance is already running (pid {existing.get('pid')}); refusing to start",
            file=sys.stderr,
        )
        return 2

    token = args.token or security.generate_token()
    app = create_app(
        args.project,
        storage_path=args.storage_path,
        handshake_path=handshake_path,
        token=token,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((args.host, args.port))
    port = sock.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=port, log_level="warning"))
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)

    security.write_handshake_atomic(
        handshake_path,
        port=port,
        token=token,
        pid=security.effective_server_pid(),
        started_at=utc_now_iso(),
    )
    try:
        server.run(sockets=[sock])
    finally:
        security.remove_handshake(handshake_path)
        app.state.storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
