"""Deterministic fake CLI subprocess for contract tests of the CLI runner.

Spawned by tests via ``python -m tests.fixtures.fake_cli --case <name>`` so the
CLI runner contract tests can drive every fragile path (happy stream, non-zero
exit, malformed NDJSON, hang-then-cancel, empty output) without requiring the
real ``gemini`` or ``claude`` binaries.

Output contract:
* NDJSON event lines on stdout — one JSON object per line, terminated by ``\\n``.
* Diagnostic / failure text on stderr.
* Exit code is deterministic per case (see the case table below).

Cases:
* ``happy_path`` — three NDJSON events (``start``, ``output`` carrying ``pong``,
  ``end``), exit ``0``.
* ``nonzero_exit`` — one event then ``boom`` on stderr, exit ``2``.
* ``timeout`` — sleep 60s then exit ``0`` (used to test the runner's timeout
  cancellation; tests configure the runner with a sub-second deadline).
* ``malformed`` — emits ``not json`` on stdout, exit ``0``.
* ``empty`` — no output, exit ``0``.

The optional ``--delay-ms`` arg inserts a uniform delay between emitted lines so
tests can simulate slow streams without sleeping in the test code.

The optional ``--prompt`` arg is accepted but not used; it exists so the runner
can pass the user prompt through and tests can assert on argv shape.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable


def _emit_ndjson(events: Iterable[dict[str, object]], delay_ms: int) -> None:
    delay_s = delay_ms / 1000.0
    for index, event in enumerate(events):
        if index > 0 and delay_ms > 0:
            time.sleep(delay_s)
        sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def _run_happy_path(delay_ms: int) -> int:
    _emit_ndjson(
        [
            {"type": "start"},
            {"type": "output", "content": "pong"},
            {"type": "end"},
        ],
        delay_ms,
    )
    return 0


def _run_nonzero_exit(delay_ms: int) -> int:
    _emit_ndjson([{"type": "start"}], delay_ms)
    sys.stderr.write("boom\n")
    sys.stderr.flush()
    return 2


def _run_timeout(delay_ms: int) -> int:
    del delay_ms
    time.sleep(60)
    return 0


def _run_malformed(delay_ms: int) -> int:
    del delay_ms
    sys.stdout.write("not json\n")
    sys.stdout.flush()
    return 0


def _run_empty(delay_ms: int) -> int:
    del delay_ms
    return 0


_CASES = {
    "happy_path": _run_happy_path,
    "nonzero_exit": _run_nonzero_exit,
    "timeout": _run_timeout,
    "malformed": _run_malformed,
    "empty": _run_empty,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic fake CLI for contract tests.")
    parser.add_argument("--case", required=True, choices=sorted(_CASES.keys()))
    parser.add_argument("--prompt", default="", help="Accepted but unused.")
    parser.add_argument("--delay-ms", type=int, default=0)
    args = parser.parse_args(argv)

    return _CASES[args.case](args.delay_ms)


if __name__ == "__main__":
    raise SystemExit(main())
