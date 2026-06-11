# -*- coding: utf-8 -*-
"""Vercel Claude Code plugin (vercel/vercel-plugin) — marketplace add + install."""

from __future__ import annotations

import shutil
import subprocess

_MARKETPLACE_REPO = "vercel/vercel-plugin"
_PLUGIN_REF = "vercel-plugin@vercel"


def _run_claude(args: list[str], timeout: int) -> tuple[int, str]:
    claude = shutil.which("claude")
    if not claude:
        return -1, "claude CLI not found — install Claude Code first"
    try:
        # claude emits UTF-8 (checkmarks etc.) — without an explicit encoding,
        # Windows decodes with cp1252 and crashes the reader thread.
        r = subprocess.run(
            [claude, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)
    return r.returncode, "\n".join(p for p in (r.stdout.strip(), r.stderr.strip()) if p)


def vercel_plugin_status() -> str:
    code, out = _run_claude(["plugin", "list"], timeout=30)
    if code != 0:
        return "not installed"
    return "installed" if "vercel-plugin" in out else "not installed"


def vercel_plugin_install() -> tuple[bool, str]:
    # marketplace add fails when the marketplace is already registered — fine.
    code, out = _run_claude(
        ["plugin", "marketplace", "add", _MARKETPLACE_REPO], timeout=120
    )
    if code != 0 and "already" not in out.lower():
        return False, f"claude plugin marketplace add failed: {out}"
    code, out = _run_claude(["plugin", "install", _PLUGIN_REF], timeout=120)
    if code == 0 or "already installed" in out.lower():
        return True, f"claude plugin install {_PLUGIN_REF}"
    return False, f"claude plugin install failed: {out}"
