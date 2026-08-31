"""Console entry point for `cabal-backend`: bind, write handshake atomically, serve, clean up."""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

import platformdirs
import uvicorn

from cabal.webapi import security
from cabal.webapi.app import create_app
from cabal.webapi.envelope import utc_now_iso


def default_handshake_path() -> Path:
    return Path(platformdirs.user_data_dir("cabal", appauthor=False)) / "webapi-handshake.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabal-backend",
        description="Local web API backend for the Cabal desktop workspace.",
    )
    parser.add_argument("--project", type=Path, default=None, help="Project directory to scope project modules to")
    parser.add_argument("--storage-path", type=Path, default=None, help="SQLite file for jobs/tickets/audit/diagnostics")
    parser.add_argument("--handshake-path", type=Path, default=None, help="Where to write the cabal-handshake.v1 file")
    parser.add_argument("--token", default=None, help="Bearer token (generated when omitted)")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        choices=["127.0.0.1"],
        help="Loopback bind host (fixed to 127.0.0.1)",
    )
    parser.add_argument("--port", type=int, default=0, help="Bind port; 0 = OS-assigned ephemeral port")
    # Default stays "warning" so packaged builds keep their quiet console; the dev supervisor
    # raises it to "info" to make per-request activity visible alongside Vite's output.
    parser.add_argument(
        "--log-level",
        default="warning",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level (default: warning)",
    )
    return parser


def _startup_log(message: str) -> None:
    log_path = os.environ.get("CABAL_BACKEND_STARTUP_LOG")
    if not log_path:
        return
    try:
        with Path(log_path).open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now_iso()} {message}\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    _startup_log("parse_args:start")
    args = _build_parser().parse_args(argv)
    handshake_path = args.handshake_path or default_handshake_path()
    _startup_log(f"handshake_path:{handshake_path}")

    # read_handshake yields None for absent, corrupt, AND stale (dead-pid) files, so a
    # non-None result always means a live backend; stale files are replaced by the
    # fresh atomic write below.
    _startup_log("read_existing_handshake:start")
    existing = security.read_handshake(handshake_path)
    if existing is not None:
        _startup_log("read_existing_handshake:live_existing")
        print(
            f"cabal-backend: another instance is already running (pid {existing.get('pid')}); refusing to start",
            file=sys.stderr,
        )
        return 2

    token = args.token or security.generate_token()
    _startup_log("create_app:start")
    app = create_app(
        args.project,
        storage_path=args.storage_path,
        handshake_path=handshake_path,
        token=token,
    )
    _startup_log("create_app:done")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((args.host, args.port))
    port = sock.getsockname()[1]
    _startup_log(f"socket_bound:{args.host}:{port}")

    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=port, log_level=args.log_level))
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)

    _startup_log("write_handshake:start")
    security.write_handshake_atomic(
        handshake_path,
        port=port,
        token=token,
        pid=security.effective_server_pid(),
        started_at=utc_now_iso(),
    )
    _startup_log("write_handshake:done")
    try:
        _startup_log("server_run:start")
        server.run(sockets=[sock])
    finally:
        _startup_log("shutdown_cleanup:start")
        security.remove_handshake(handshake_path, expected_token=token)
        app.state.storage.close()
        _startup_log("shutdown_cleanup:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
