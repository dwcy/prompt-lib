#!/usr/bin/env python3
"""Run every test suite that can run from this checkout.

The root project and each service are separate Python projects. This runner keeps
that boundary intact while giving maintainers one command to exercise the repo.
Missing local tools are reported as skipped by default so a fresh machine can
still show what remains to install.
"""

from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    ROOT / "services" / "a2a-bridge",
    ROOT / "services" / "orchestrator",
    ROOT / "services" / "mcp-bus",
)
WINDOWS_GIT_DIRS = (
    Path(r"C:\Program Files\Git\cmd"),
    Path(r"C:\Program Files (x86)\Git\cmd"),
)


@dataclass(frozen=True)
class Suite:
    name: str
    cwd: Path
    command: list[str]
    env: dict[str, str] | None = None


@dataclass(frozen=True)
class SkippedSuite:
    name: str
    reason: str


def _module_available(module: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _suite_env(include_integration: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("CABAL_CACHE_DIR", str(ROOT / ".pytest_cache" / "cabal"))
    if platform.system() == "Windows" and not shutil.which("git", path=env.get("PATH")):
        for git_dir in WINDOWS_GIT_DIRS:
            if (git_dir / "git.exe").exists():
                env["PATH"] = f"{git_dir}{os.pathsep}{env.get('PATH', '')}"
                break
    if include_integration:
        env["INTEGRATION"] = "1"
    return env


def _discover_suites(include_integration: bool) -> tuple[list[Suite], list[SkippedSuite]]:
    suites: list[Suite] = []
    skipped: list[SkippedSuite] = []
    uv = shutil.which("uv")

    if uv:
        suites.append(
            Suite(
                name="root",
                cwd=ROOT,
                command=[
                    uv,
                    "run",
                    "--with",
                    "pytest",
                    "--with",
                    "pytest-asyncio",
                    "pytest",
                ],
                env=_suite_env(include_integration),
            )
        )
    elif _module_available("pytest"):
        suites.append(
            Suite(
                name="root",
                cwd=ROOT,
                command=[sys.executable, "-m", "pytest"],
                env=_suite_env(include_integration),
            )
        )
    else:
        skipped.append(SkippedSuite("root", "pytest is not importable and uv is not on PATH"))

    for service in SERVICES:
        if not service.exists():
            skipped.append(SkippedSuite(service.name, "service directory is missing"))
            continue
        if not uv:
            skipped.append(SkippedSuite(service.name, "uv is not on PATH"))
            continue
        suites.append(
            Suite(
                name=service.name,
                cwd=service,
                command=[uv, "run", "pytest"],
                env=_suite_env(include_integration),
            )
        )

    return suites, skipped


def _run_suite(suite: Suite) -> int:
    rel = suite.cwd.relative_to(ROOT)
    print(f"\n== {suite.name} ({rel}) ==", flush=True)
    print(f"$ {shlex.join(suite.command)}", flush=True)
    result = subprocess.run(suite.command, cwd=suite.cwd, env=suite.env, check=False)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-integration",
        action="store_true",
        help="set INTEGRATION=1 for suites that have external integration tests",
    )
    parser.add_argument(
        "--strict-missing",
        action="store_true",
        help="treat skipped suites caused by missing local tools as a failure",
    )
    args = parser.parse_args(argv)

    suites, skipped = _discover_suites(include_integration=args.include_integration)
    failures: list[str] = []

    for suite in suites:
        if _run_suite(suite) != 0:
            failures.append(suite.name)

    if skipped:
        print("\nSkipped suites:")
        for item in skipped:
            print(f"- {item.name}: {item.reason}")

    if failures:
        print("\nFailed suites:")
        for name in failures:
            print(f"- {name}")
        return 1

    if skipped and args.strict_missing:
        print("\nSome suites were skipped and --strict-missing was set.")
        return 2

    print("\nAll runnable suites passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
