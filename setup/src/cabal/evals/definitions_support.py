# -*- coding: utf-8 -*-
"""Low-level parsing and git-probe helpers shared by the definition loaders in `definitions.py`."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from cabal.evals.definitions_model import (
    CHECK_KINDS,
    CHECK_PARSERS,
    DEFAULT_CHECK_PARSER,
    DEFAULT_CHECK_TIMEOUT_SECONDS,
    CheckSpec,
    fail,
)

GIT_TIMEOUT_SECONDS = 30


def load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(path, "file", "file does not exist")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        fail(path, "toml", f"invalid TOML: {exc}")


def reject_unknown_keys(data: dict[str, Any], allowed: frozenset[str], file: Path, prefix: str = "") -> None:
    for key in data:
        if key not in allowed:
            fail(file, f"{prefix}{key}", "unknown key")


def str_list(data: dict[str, Any], key: str, file: Path) -> list[str]:
    raw = data.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        fail(file, key, f"{key} must be a list of strings")
    return list(raw)


def git_output(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def is_git_repo(repo: Path) -> bool:
    if (repo / ".git").exists():
        return True
    # Guard against git's upward discovery blessing a plain directory inside some outer repo.
    toplevel = git_output(repo, "rev-parse", "--show-toplevel")
    return toplevel is not None and Path(toplevel).resolve() == repo.resolve()


def parse_checks(raw: Any, file: Path) -> list[CheckSpec]:
    if not isinstance(raw, list) or not raw:
        fail(file, "checks", "at least one [[checks]] entry is required")
    allowed = frozenset({"kind", "cmd", "parser", "timeout_seconds"})
    checks: list[CheckSpec] = []
    for index, entry in enumerate(raw):
        prefix = f"checks[{index}]."
        if not isinstance(entry, dict):
            fail(file, f"checks[{index}]", "each [[checks]] entry must be a table")
        reject_unknown_keys(entry, allowed, file, prefix)
        kind = entry.get("kind")
        if kind not in CHECK_KINDS:
            fail(file, f"{prefix}kind", f"kind must be one of {CHECK_KINDS}")
        cmd = entry.get("cmd")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(arg, str) for arg in cmd):
            fail(file, f"{prefix}cmd", "cmd must be a non-empty argv list of strings")
        parser = entry.get("parser", DEFAULT_CHECK_PARSER)
        if parser not in CHECK_PARSERS:
            fail(file, f"{prefix}parser", f"parser must be one of {CHECK_PARSERS}")
        timeout = entry.get("timeout_seconds", DEFAULT_CHECK_TIMEOUT_SECONDS)
        if not isinstance(timeout, int) or timeout < 1:
            fail(file, f"{prefix}timeout_seconds", "timeout_seconds must be a positive integer")
        checks.append(CheckSpec(kind=kind, cmd=list(cmd), parser=parser, timeout_seconds=timeout))
    return checks
