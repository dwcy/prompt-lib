# -*- coding: utf-8 -*-
"""Claude CLI (claude-code) — Anthropic's terminal interface."""

from __future__ import annotations

import shutil
import subprocess


def claude_cli_status() -> str:
    if not shutil.which("claude"):
        return "not installed"
    r = subprocess.run(["claude", "--version"], capture_output=True, text=True)
    v = (r.stdout or r.stderr or "").strip().splitlines()[0] if r.returncode == 0 else ""
    return f"installed {v}" if v else "installed"


def claude_cli_install() -> tuple[bool, str]:
    if not shutil.which("npm"):
        return False, "npm not found — install Node.js from https://nodejs.org then re-run"
    r = subprocess.run(["npm", "install", "-g", "@anthropic-ai/claude-code"], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
