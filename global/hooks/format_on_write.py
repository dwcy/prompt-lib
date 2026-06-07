#!/usr/bin/env python3
"""PostToolUse hook: auto-format files after Write/Edit.

Dispatches by extension:
  .py                              -> ruff format
  .ts/.tsx/.js/.jsx/.json/.jsonc   -> biome format --write
  .cs                              -> dotnet format

Silent skip when the tool is not installed, no project config is found above
the file, the path is inside a build/vendor directory, or the file is missing
or too large. Never blocks: exits 0 on every path.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from _gate import should_skip
except ImportError:

    def should_skip(_name: str) -> bool:
        return False


MAX_BYTES = 2 * 1024 * 1024
WALK_LIMIT = 12
TIMEOUT_SEC = 15

SKIP_DIRS = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "bin",
    "obj",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
}

BIOME_EXTS = {
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".jsonc",
}


def _find_upwards(start: Path, names: tuple[str, ...]) -> Path | None:
    cur = start.parent
    for _ in range(WALK_LIMIT):
        for name in names:
            candidate = cur / name
            if candidate.exists():
                return candidate
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _find_upwards_glob(start: Path, patterns: tuple[str, ...]) -> Path | None:
    cur = start.parent
    for _ in range(WALK_LIMIT):
        for pattern in patterns:
            for match in cur.glob(pattern):
                if match.is_file():
                    return match
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _run(cmd: list[str], cwd: Path) -> None:
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            timeout=TIMEOUT_SEC,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


def _format_python(path: Path) -> None:
    if not shutil.which("ruff"):
        return
    config = _find_upwards(path, ("pyproject.toml", "ruff.toml", ".ruff.toml"))
    if config is None:
        return
    _run(["ruff", "format", str(path)], cwd=config.parent)


def _format_biome(path: Path) -> None:
    if not shutil.which("biome"):
        return
    config = _find_upwards(path, ("biome.json", "biome.jsonc"))
    if config is None:
        return
    _run(["biome", "format", "--write", str(path)], cwd=config.parent)


def _format_csharp(path: Path) -> None:
    if not shutil.which("dotnet"):
        return
    project = _find_upwards_glob(path, ("*.sln", "*.csproj"))
    if project is None:
        return
    _run(
        [
            "dotnet",
            "format",
            str(project),
            "--include",
            str(path),
            "--no-restore",
            "--verbosity",
            "quiet",
        ],
        cwd=project.parent,
    )


def main() -> None:
    if should_skip("format_on_write"):
        return
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    raw_path = data.get("tool_input", {}).get("file_path", "")
    if not raw_path:
        return

    path = Path(raw_path)
    if not path.is_absolute():
        path = path.resolve()
    if not path.is_file():
        return

    if any(part in SKIP_DIRS for part in path.parts):
        return

    try:
        if path.stat().st_size > MAX_BYTES:
            return
    except OSError:
        return

    suffix = path.suffix.lower()
    if suffix == ".py":
        _format_python(path)
    elif suffix in BIOME_EXTS:
        _format_biome(path)
    elif suffix == ".cs":
        _format_csharp(path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
