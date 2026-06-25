# -*- coding: utf-8 -*-
"""Host environment detection — runtimes, package managers, CLIs, editors.

Pure subprocess introspection. No mutation, no network. Used by the env
screens, EnvPanel widget, and `render_env_summary`.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from cabal._paths import TARGET


def _probe_version(cmd: str, *args: str) -> str | None:
    """Run `cmd args...`, return trimmed first stdout line on success, else None.

    Uses the absolute path from shutil.which so Windows .CMD/.BAT shims
    (npm, gemini, opencode, etc.) execute via subprocess without `shell=True`.
    """
    resolved = shutil.which(cmd)
    if not resolved:
        return None
    try:
        result = subprocess.run(
            [resolved, *args], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = (result.stdout or result.stderr).strip().splitlines()
    return out[0] if out else None


def _detect_pkg_manager() -> str | None:
    """Return the name of the OS-native package manager the wizard would use."""
    sysname = platform.system()
    if sysname == "Windows":
        for pm in ("winget", "scoop", "choco"):
            if shutil.which(pm):
                return pm
    elif sysname == "Darwin":
        for pm in ("brew", "port"):
            if shutil.which(pm):
                return pm
    elif sysname == "Linux":
        for pm in ("apt-get", "dnf", "pacman", "zypper", "apk", "emerge"):
            if shutil.which(pm):
                return pm
    return None


def _git_user_name() -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        r = subprocess.run(
            [git, "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = (r.stdout or "").strip()
    return name or None


def _kubectl_version() -> str | None:
    """Return kubectl client version string (e.g. 'v1.30.0'), or None."""
    cmd = shutil.which("kubectl")
    if not cmd:
        return None
    try:
        r = subprocess.run(
            [cmd, "version", "--client", "--output=json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    return (data.get("clientVersion") or {}).get("gitVersion")


def _dotnet_sdks() -> list[str]:
    """Return installed .NET SDK major.minor versions, sorted, deduped. Empty if dotnet missing."""
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return []
    try:
        r = subprocess.run(
            [dotnet, "--list-sdks"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    versions: set[str] = set()
    for line in (r.stdout or "").splitlines():
        first = line.split(None, 1)[0].strip() if line.strip() else ""
        parts = first.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            versions.add(f"{parts[0]}.{parts[1]}")
    return sorted(versions, key=lambda v: tuple(int(p) for p in v.split(".")))


def _has_rider() -> bool:
    """JetBrains Rider — Toolbox usually puts `rider` (or `rider64` on Windows) on PATH."""
    return shutil.which("rider") is not None or shutil.which("rider64") is not None


def _has_visual_studio() -> bool:
    """Visual Studio — `devenv` on PATH, or any edition discoverable via `vswhere`."""
    if shutil.which("devenv"):
        return True
    if platform.system() != "Windows":
        return False
    vswhere = Path(
        "C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if not vswhere.exists():
        return False
    try:
        r = subprocess.run(
            [str(vswhere), "-products", "*", "-property", "installationPath"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _path_exists_any(paths: list[Path]) -> bool:
    return any(path.exists() for path in paths)


def _has_lm_studio() -> bool:
    if shutil.which("lms"):
        return True
    sysname = platform.system()
    home = Path.home()
    if sysname == "Windows":
        return _path_exists_any(
            [
                home / "AppData/Local/Programs/LM Studio/LM Studio.exe",
                Path("C:/Program Files/LM Studio/LM Studio.exe"),
            ]
        )
    if sysname == "Darwin":
        return Path("/Applications/LM Studio.app").exists()
    if sysname == "Linux":
        return shutil.which("lm-studio") is not None
    return False


def _has_opencode_desktop() -> bool:
    sysname = platform.system()
    home = Path.home()
    if sysname == "Windows":
        return _path_exists_any(
            [
                home / "AppData/Local/Programs/OpenCode/OpenCode.exe",
                Path("C:/Program Files/OpenCode/OpenCode.exe"),
            ]
        )
    if sysname == "Darwin":
        return Path("/Applications/OpenCode.app").exists()
    if sysname == "Linux":
        return shutil.which("opencode-desktop") is not None
    return False


def _opencode_status() -> str | None:
    cli = shutil.which("opencode") is not None
    app = _has_opencode_desktop()
    if cli and app:
        return "CLI and desktop app"
    if cli:
        return "CLI installed; desktop app not detected"
    if app:
        return "desktop app installed; CLI missing"
    return None


def _has_copilot_cli() -> bool:
    """Return True only for the current GitHub Copilot CLI executable."""
    return shutil.which("copilot") is not None


def _has_desktop_command_or_path(command: str, windows_paths: list[str], mac_app: str) -> bool:
    if shutil.which(command):
        return True
    sysname = platform.system()
    if sysname == "Windows":
        return _path_exists_any([Path(path) for path in windows_paths])
    if sysname == "Darwin":
        return Path(f"/Applications/{mac_app}.app").exists()
    return False


def _ollama_models() -> list[str]:
    """Return locally installed Ollama model names (empty list if none or unavailable)."""
    ollama = shutil.which("ollama")
    if not ollama:
        return []
    try:
        r = subprocess.run(
            [ollama, "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    models: list[str] = []
    for line in (r.stdout or "").splitlines()[1:]:  # skip header row
        name = line.split(None, 1)[0].strip() if line.strip() else ""
        if name:
            models.append(name)
    return models


def _gh_login() -> str | None:
    """Return the authenticated GitHub username, or None.

    Uses `gh api user --jq .login` which requires `gh auth login` to have run.
    """
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        r = subprocess.run(
            [gh, "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    login = (r.stdout or "").strip()
    return login or None


def detect_env() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "shell": os.environ.get("SHELL") or os.environ.get("COMSPEC", "?"),
        "pkg_manager": _detect_pkg_manager(),
        "git": shutil.which("git") is not None,
        "git_user": _git_user_name(),
        "git_version": _probe_version("git", "--version"),
        "gh_login": _gh_login(),
        "bash": shutil.which("bash") is not None,
        "claude": shutil.which("claude") is not None,
        "gh": shutil.which("gh") is not None,
        "node": _probe_version("node", "--version"),
        "npm": _probe_version("npm", "--version"),
        "pnpm": _probe_version("pnpm", "--version"),
        "bun": _probe_version("bun", "--version"),
        "dotnet": _probe_version("dotnet", "--version"),
        "dotnet_sdks": _dotnet_sdks(),
        "docker": _probe_version("docker", "--version"),
        "podman": _probe_version("podman", "--version"),
        "kubectl": _kubectl_version(),
        "terraform": _probe_version("terraform", "--version"),
        "az": _probe_version("az", "--version"),
        "gcloud": _probe_version("gcloud", "--version"),
        "aws": _probe_version("aws", "--version"),
        "gemini": shutil.which("gemini") is not None,
        "codex": shutil.which("codex") is not None,
        "opencode": _opencode_status() is not None,
        "opencode_cli": shutil.which("opencode") is not None,
        "opencode_app": _has_opencode_desktop(),
        "grok": shutil.which("grok") is not None,
        "skills": shutil.which("skills") is not None,
        "cursor": shutil.which("cursor") is not None,
        "windsurf": shutil.which("windsurf") is not None,
        "copilot": _has_copilot_cli(),
        "antigravity": shutil.which("antigravity") is not None,
        "vllm": _probe_version("vllm", "--version")
        or (shutil.which("vllm") is not None),
        "vscode": shutil.which("code") is not None,
        "rider": _has_rider(),
        "visualstudio": _has_visual_studio(),
        "ollama": shutil.which("ollama") is not None,
        "lm-studio": _has_lm_studio(),
        "hermes-agent": False,
        "ollama_models": _ollama_models(),
        "sqlcmd": shutil.which("sqlcmd") is not None,
        "psql": shutil.which("psql") is not None,
        "supabase": shutil.which("supabase") is not None,
        "neonctl": shutil.which("neonctl") is not None,
        "sqlite": shutil.which("sqlite3") is not None,
        "duckdb": shutil.which("duckdb") is not None,
        "zed": shutil.which("zed") is not None,
        "postman": _has_desktop_command_or_path(
            "postman",
            [
                "C:/Users/Public/AppData/Local/Postman/Postman.exe",
                str(Path.home() / "AppData/Local/Postman/Postman.exe"),
            ],
            "Postman",
        ),
        "hugo": _probe_version("hugo", "version"),
        "uvicorn": _probe_version("uvicorn", "--version"),
        "dbeaver": shutil.which("dbeaver") is not None,
        "ssms": platform.system() == "Windows"
        and Path("C:/Program Files (x86)/Microsoft SQL Server Management Studio").exists(),
        "target_exists": TARGET.exists(),
    }


def find_env_vars(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(
        set(
            re.findall(
                r"\$\{([A-Z_][A-Z0-9_]*)\}",
                path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    )
