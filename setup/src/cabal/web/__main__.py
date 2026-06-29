"""Command-line entrypoint for `python -m cabal.web`."""

from __future__ import annotations

import argparse
from pathlib import Path

from cabal.web.server import DEFAULT_HOST, DEFAULT_PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local read-only Cabal web UI.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host. Defaults to 127.0.0.1.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Bind port. Defaults to 8765.")
    parser.add_argument("--project", default=".", help="Project path to inspect. Defaults to current directory.")
    args = parser.parse_args(argv)
    serve(Path(args.project), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
