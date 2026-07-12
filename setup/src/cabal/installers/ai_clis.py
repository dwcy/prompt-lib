# -*- coding: utf-8 -*-
"""AI CLI installers — Gemini, Codex, OpenCode, Grok, Hugging Face, Copilot, Ollama."""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from cabal.installers._common import _npm_global_install, _run_install, _WINGET_FLAGS


OPENCODE_DESKTOP_DOWNLOADS = {
    "Windows": (
        "https://opencode.ai/download/stable/windows-x64-nsis",
        "opencode-desktop-setup.exe",
    ),
    "LinuxDeb": (
        "https://opencode.ai/download/stable/linux-x64-deb",
        "opencode-desktop.deb",
    ),
    "LinuxRpm": (
        "https://opencode.ai/download/stable/linux-x64-rpm",
        "opencode-desktop.rpm",
    ),
}


def gemini_install() -> tuple[bool, str]:
    return _npm_global_install("@google/gemini-cli")


def huggingface_install() -> tuple[bool, str]:
    """Install Hugging Face's current `hf` CLI."""
    sysname = platform.system()
    if sysname in {"Darwin", "Linux"} and shutil.which("brew"):
        return _run_install(["brew", "install", "hf"])
    if shutil.which("uv"):
        return _run_install(["uv", "tool", "install", "hf"])
    if shutil.which("pipx"):
        return _run_install(["pipx", "install", "hf"])
    if shutil.which("python"):
        return _run_install(["python", "-m", "pip", "install", "--user", "huggingface_hub"])
    return (
        False,
        "Install Python, uv, pipx, or Homebrew first, then install the Hugging Face CLI "
        "from https://huggingface.co/docs/huggingface_hub/en/guides/cli.",
    )


def codex_install() -> tuple[bool, str]:
    return _npm_global_install("@openai/codex")


def opencode_install() -> tuple[bool, str]:
    return _npm_global_install("opencode-ai")


def _download_opencode_desktop(url: str, filename: str) -> tuple[Path | None, str]:
    target = Path(tempfile.gettempdir()) / filename
    try:
        with urllib.request.urlopen(url, timeout=120) as response, target.open(
            "wb"
        ) as out:
            shutil.copyfileobj(response, out)
    except (OSError, urllib.error.URLError) as exc:
        return None, f"download failed: {exc}"
    return target, f"downloaded {url} to {target}"


def _launch_windows_installer(path: Path) -> tuple[bool, str]:
    try:
        subprocess.Popen([str(path)], close_fds=True)
    except OSError as exc:
        return False, f"failed to launch installer: {exc}"
    return True, f"launched {path}; complete the OpenCode Desktop installer window"


def opencode_desktop_install() -> tuple[bool, str]:
    sysname = platform.system()
    machine = platform.machine().lower()
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "opencode-desktop"])
        return (
            False,
            "Install OpenCode Desktop manually from https://opencode.ai/download",
        )
    if sysname == "Windows":
        if machine not in {"amd64", "x86_64"}:
            return (
                False,
                "OpenCode Desktop automatic install currently targets Windows x64.",
            )
        path, msg = _download_opencode_desktop(*OPENCODE_DESKTOP_DOWNLOADS["Windows"])
        if path is None:
            return False, msg
        ok, launched = _launch_windows_installer(path)
        return ok, f"{msg}\n{launched}"
    if sysname == "Linux":
        if machine not in {"amd64", "x86_64"}:
            return (
                False,
                "OpenCode Desktop automatic install currently targets Linux x64.",
            )
        if shutil.which("apt-get") and shutil.which("dpkg"):
            path, msg = _download_opencode_desktop(
                *OPENCODE_DESKTOP_DOWNLOADS["LinuxDeb"]
            )
            if path is None:
                return False, msg
            ok, out = _run_install(["sudo", "dpkg", "-i", str(path)])
            return ok, f"{msg}\n{out}"
        if shutil.which("dnf"):
            path, msg = _download_opencode_desktop(
                *OPENCODE_DESKTOP_DOWNLOADS["LinuxRpm"]
            )
            if path is None:
                return False, msg
            ok, out = _run_install(["sudo", "dnf", "install", "-y", str(path)])
            return ok, f"{msg}\n{out}"
        return (
            False,
            "Install OpenCode Desktop manually from https://opencode.ai/download",
        )
    return False, f"Unsupported platform: {sysname}"


def lm_studio_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            return _run_install(["winget", "install", "--id", "LMStudio.LMStudio", *_WINGET_FLAGS])
        return False, "Install manually from https://lmstudio.ai/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            return _run_install(["brew", "install", "--cask", "lm-studio"])
        return False, "Install manually from https://lmstudio.ai/"
    if sysname == "Linux":
        return False, "Download the Linux AppImage or package from https://lmstudio.ai/"
    return False, f"Unsupported platform: {sysname}"


def hermes_agent_install() -> tuple[bool, str]:
    return (
        False,
        "Hermes Agent install is source-gated. Configure a trusted official "
        "source URL and install channel before enabling automation.",
    )


def grok_install() -> tuple[bool, str]:
    # xAI's Grok CLI ships via npm.
    return _npm_global_install("@vibe-kit/grok-cli")


def copilot_install() -> tuple[bool, str]:
    """Install the current GitHub Copilot CLI, not the deprecated gh extension."""
    sysname = platform.system()
    if sysname == "Windows" and shutil.which("winget"):
        return _run_install(["winget", "install", "--id", "GitHub.Copilot", *_WINGET_FLAGS])
    if sysname in {"Darwin", "Linux"} and shutil.which("brew"):
        return _run_install(["brew", "install", "copilot-cli"])
    if shutil.which("npm"):
        return _npm_global_install("@github/copilot")
    return (
        False,
        "Install GitHub Copilot CLI manually from https://github.com/github/copilot-cli "
        "or install winget, brew, or npm first.",
    )


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
        "`uv venv --python 3.14 --seed --managed-python`, activate it, then "
        "`uv pip install -U vllm --torch-backend=auto`. Docker users can run "
        "`vllm/vllm-openai:latest` with GPU access.",
    )
