# -*- coding: utf-8 -*-
"""AI CLI installers — Gemini, Codex, OpenCode, Grok, Copilot, Antigravity, Ollama."""

from __future__ import annotations

import platform
import shutil

from cabal.installers._common import _npm_global_install, _run_install, _WINGET_FLAGS


def gemini_install() -> tuple[bool, str]:
    return _npm_global_install("@google/gemini-cli")


def codex_install() -> tuple[bool, str]:
    return _npm_global_install("@openai/codex")


def opencode_install() -> tuple[bool, str]:
    return _npm_global_install("opencode-ai")


def grok_install() -> tuple[bool, str]:
    # xAI's Grok CLI ships via npm.
    return _npm_global_install("@vibe-kit/grok-cli")


def copilot_install() -> tuple[bool, str]:
    # Best path is the `gh` extension — needs gh CLI to be installed and authenticated.
    if not shutil.which("gh"):
        return (
            False,
            "gh CLI not found - install GitHub CLI first, then run "
            "`gh extension install github/gh-copilot`",
        )
    return _run_install(["gh", "extension", "install", "github/gh-copilot"])


def antigravity_install() -> tuple[bool, str]:
    # Google Antigravity has no native installer yet — point at the download page.
    return False, "Install manually from https://antigravity.google"


def ollama_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "Ollama.Ollama", *_WINGET_FLAGS])
        return False, "Install manually from https://ollama.com/download"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "ollama"])
        return False, "Install manually from https://ollama.com/download"
    if sysname == "Linux":
        return False, "Install manually from https://ollama.com/download"
    return False, f"Unsupported platform: {sysname}"


def vllm_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname != "Linux":
        return (
            False,
            "vLLM is only enabled for Linux in Cabal. On Windows, use WSL2 or "
            "a Linux Docker host for the official vLLM OpenAI-compatible server.",
        )
    return (
        False,
        "Install vLLM in a dedicated Linux Python environment. Recommended: "
        "`uv venv --python 3.12 --seed --managed-python`, activate it, then "
        "`uv pip install -U vllm --torch-backend=auto`. Docker users can run "
        "`vllm/vllm-openai:latest` with GPU access.",
    )
