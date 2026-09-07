"""Bisect a pytest suite to find the test that pollutes shared state.

Symptom: a test passes when run alone but fails when the suite runs in its
default order. Some earlier test leaves state behind (an env var, a module
global, a file, a singleton) that the failing test trips over.

This script collects the suite in default order, takes every test that runs
before the failing one, confirms the pass-alone / fail-with-prefix shape, then
bisects the prefix until a single polluting test remains.

Usage:
    python find_polluter.py tests/test_foo.py::test_bar
    python find_polluter.py tests/test_foo.py::test_bar --tests-dir setup/tests
    python find_polluter.py tests/test_foo.py::test_bar -- -p no:cacheprovider

Everything after `--` is passed to every pytest invocation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run_pytest(node_ids: list[str], extra: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:randomly", *extra, *node_ids]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def collect(tests_dir: str, extra: list[str]) -> list[str]:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly", *extra, tests_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 5):
        sys.exit(f"collection failed:\n{result.stdout}\n{result.stderr}")
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


def bisect(prefix: list[str], target: str, extra: list[str]) -> str:
    candidates = prefix
    while len(candidates) > 1:
        half = len(candidates) // 2
        first, second = candidates[:half], candidates[half:]
        print(f"  trying {len(first)} tests before the target ...", flush=True)
        if not run_pytest([*first, target], extra):
            candidates = first
        else:
            candidates = second
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="node id of the test that fails in the suite but passes alone")
    parser.add_argument("--tests-dir", default="tests", help="directory pytest collects from (default: tests)")
    parser.add_argument("pytest_args", nargs="*", help="extra args for pytest, after --")
    args = parser.parse_args()
    extra = args.pytest_args

    print(f"collecting {args.tests_dir} ...", flush=True)
    suite = collect(args.tests_dir, extra)
    if args.target not in suite:
        print(f"target {args.target} not found in collected suite ({len(suite)} tests)", file=sys.stderr)
        return 2
    prefix = suite[: suite.index(args.target)]
    if not prefix:
        print("target is the first test in the suite; nothing runs before it")
        return 2

    print("checking the target passes alone ...", flush=True)
    if not run_pytest([args.target], extra):
        print("target fails on its own — this is not a pollution problem, debug the test directly", file=sys.stderr)
        return 2

    print(f"checking the target fails after the {len(prefix)} tests that precede it ...", flush=True)
    if run_pytest([*prefix, args.target], extra):
        print("target passes with the full prefix — the failure depends on something else (timing, environment, another file)", file=sys.stderr)
        return 2

    polluter = bisect(prefix, args.target, extra)
    print()
    print(f"polluter: {polluter}")
    print(f"reproduce: python -m pytest -q {polluter} {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
