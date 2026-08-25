"""Read-only terminal, shell, and profile configuration discovery."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_SHELLS = (
    ("pwsh", "PowerShell", ("pwsh", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()")),
    (
        "powershell",
        "Windows PowerShell",
        ("powershell", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
    ),
    ("cmd", "Command Prompt", ("cmd", "/d", "/c", "ver")),
    ("bash", "Bash", ("bash", "--version")),
    ("zsh", "Zsh", ("zsh", "--version")),
    ("fish", "Fish", ("fish", "--version")),
    ("nu", "Nushell", ("nu", "--version")),
)

_TERMINAL_APPS = (
    ("wezterm", "WezTerm", ("wezterm", "--version")),
    ("alacritty", "Alacritty", ("alacritty", "--version")),
    ("kitty", "Kitty", ("kitty", "--version")),
    ("hyper", "Hyper", ("hyper", "--version")),
    ("tabby", "Tabby", ("tabby", "--version")),
    ("gnome-terminal", "GNOME Terminal", ("gnome-terminal", "--version")),
    ("konsole", "Konsole", ("konsole", "--version")),
)

_PROFILE_MARKERS = (
    ("oh-my-posh", "Oh My Posh", "prompt"),
    ("starship", "Starship", "prompt"),
    ("posh-git", "posh-git", "integration"),
    ("psreadline", "PSReadLine", "integration"),
    ("zoxide", "zoxide", "integration"),
    ("fzf", "fzf", "integration"),
    ("direnv", "direnv", "integration"),
)


def _command_path(command: str) -> str | None:
    if command == "cmd" and os.name == "nt":
        command = os.environ.get("COMSPEC", "cmd.exe")
    return shutil.which(command)


def _version(command: tuple[str, ...], executable: str) -> str | None:
    try:
        result = subprocess.run(
            (executable, *command[1:]),
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0].strip() if output else None


def _profile_candidates(home: Path) -> dict[str, list[Path]]:
    documents = home / "Documents"
    return {
        "pwsh": [
            documents / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            documents / "PowerShell" / "profile.ps1",
        ],
        "powershell": [
            documents / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
            documents / "WindowsPowerShell" / "profile.ps1",
        ],
        "bash": [home / ".bashrc", home / ".bash_profile", home / ".profile"],
        "zsh": [home / ".zshrc", home / ".zprofile"],
        "fish": [home / ".config" / "fish" / "config.fish"],
        "nu": [
            home / ".config" / "nushell" / "config.nu",
            home / "AppData" / "Roaming" / "nushell" / "config.nu",
        ],
    }


def _first_file(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.is_file()), None)


def _strip_jsonc(value: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(value):
        char = value[index]
        following = value[index + 1] if index + 1 < len(value) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and following == "/":
            index += 2
            while index < len(value) and value[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and following == "*":
            end = value.find("*/", index + 2)
            index = len(value) if end < 0 else end + 2
            continue
        output.append(char)
        index += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(output))


def _load_settings(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(_strip_jsonc(path.read_text(encoding="utf-8-sig")))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _windows_terminal_settings() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    base = Path(local_app_data)
    candidates = (
        base
        / "Packages"
        / "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
        / "LocalState"
        / "settings.json",
        base
        / "Packages"
        / "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"
        / "LocalState"
        / "settings.json",
        base / "Microsoft" / "Windows Terminal" / "settings.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def _profile_name(settings: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    profile_settings = settings.get("profiles")
    if not isinstance(profile_settings, dict):
        return None, [], {}
    profiles = [item for item in profile_settings.get("list", []) if isinstance(item, dict)]
    defaults = profile_settings.get("defaults")
    defaults = defaults if isinstance(defaults, dict) else {}
    default_guid = str(settings.get("defaultProfile", "")).casefold()
    default = next(
        (profile for profile in profiles if str(profile.get("guid", "")).casefold() == default_guid),
        None,
    )
    name = str(default.get("name")) if default and default.get("name") else None
    return name, profiles, defaults


def _terminal_modifications(
    settings_path: Path | None,
    settings: dict[str, Any],
    profiles: list[dict[str, Any]],
    defaults: dict[str, Any],
    shell_profiles: list[Path],
) -> list[dict[str, str]]:
    modifications: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(key: str, label: str, detail: str, kind: str, source: str) -> None:
        if key in seen:
            return
        seen.add(key)
        modifications.append(
            {"key": key, "label": label, "detail": detail, "kind": kind, "source": source}
        )

    settings_source = str(settings_path) if settings_path else "terminal settings"
    if profiles:
        add("profiles", "Profiles", f"{len(profiles)} configured", "profile", settings_source)
    schemes = settings.get("schemes")
    if isinstance(schemes, list) and schemes:
        add("schemes", "Color schemes", f"{len(schemes)} configured", "theme", settings_source)
    actions = settings.get("actions") or settings.get("keybindings")
    if isinstance(actions, list) and actions:
        add("actions", "Key bindings", f"{len(actions)} actions", "keybindings", settings_source)
    startup_actions = settings.get("startupActions")
    if isinstance(startup_actions, str) and startup_actions.strip():
        add("startup", "Startup actions", "Custom startup command", "behavior", settings_source)

    font_faces: set[str] = set()
    appearance_keys = {"opacity", "useAcrylic", "backgroundImage", "colorScheme", "theme"}
    appearance_changed = any(key in defaults for key in appearance_keys)
    for profile in (defaults, *profiles):
        font = profile.get("font")
        if isinstance(font, dict) and font.get("face"):
            font_faces.add(str(font["face"]))
        if profile.get("fontFace"):
            font_faces.add(str(profile["fontFace"]))
        appearance_changed = appearance_changed or any(key in profile for key in appearance_keys)
    if font_faces:
        add("fonts", "Fonts", ", ".join(sorted(font_faces)), "appearance", settings_source)
    if appearance_changed:
        add("appearance", "Appearance", "Custom profile appearance", "appearance", settings_source)

    for path in shell_profiles:
        source = str(path)
        try:
            content = path.read_text(encoding="utf-8", errors="replace").casefold()
        except OSError:
            continue
        add(f"profile:{source.casefold()}", "Shell profile", path.name, "profile", source)
        for marker, label, kind in _PROFILE_MARKERS:
            if marker in content:
                add(f"tool:{marker}", label, "Loaded by a shell profile", kind, source)
        if "set-alias" in content or re.search(r"(?m)^\s*alias\s+", content):
            add("aliases", "Custom aliases", "Defined in a shell profile", "behavior", source)
        if re.search(r"(?m)^\s*function\s+", content):
            add("functions", "Custom functions", "Defined in a shell profile", "behavior", source)
    return modifications


def build_terminal_summary(environment: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return installed shells, terminal applications, and safe configuration metadata."""
    environment = environment or {}
    home = Path.home()
    profile_candidates = _profile_candidates(home)
    current_shell = str(environment.get("shell") or os.environ.get("SHELL") or os.environ.get("COMSPEC") or "")
    current_shell_name = Path(current_shell).stem.casefold()

    shells: list[dict[str, Any]] = []
    shell_profiles: list[Path] = []
    for key, label, command in _SHELLS:
        executable = _command_path(command[0])
        profile = _first_file(profile_candidates.get(key, []))
        if profile is not None:
            shell_profiles.append(profile)
        active_names = {key, Path(executable).stem.casefold() if executable else ""}
        shells.append(
            {
                "key": key,
                "label": label,
                "installed": executable is not None,
                "version": _version(command, executable) if executable else None,
                "path": executable,
                "active": current_shell_name in active_names,
                "configured": profile is not None,
                "profile_path": str(profile) if profile else None,
            }
        )

    settings_path = _windows_terminal_settings()
    settings = _load_settings(settings_path) if settings_path else {}
    default_profile, profiles, defaults = _profile_name(settings)
    wt_path = _command_path("wt")
    terminal_apps: list[dict[str, Any]] = [
        {
            "key": "windows-terminal",
            "label": "Windows Terminal",
            "installed": wt_path is not None or settings_path is not None,
            "version": None,
            "path": wt_path,
            "configured": settings_path is not None,
            "settings_path": str(settings_path) if settings_path else None,
            "active": bool(os.environ.get("WT_SESSION")),
        }
    ]
    term_program = os.environ.get("TERM_PROGRAM", "").casefold()
    for key, label, command in _TERMINAL_APPS:
        executable = _command_path(command[0])
        terminal_apps.append(
            {
                "key": key,
                "label": label,
                "installed": executable is not None,
                "version": _version(command, executable) if executable else None,
                "path": executable,
                "configured": False,
                "settings_path": None,
                "active": key in term_program,
            }
        )

    default_terminal = os.environ.get("TERM_PROGRAM")
    if not default_terminal and settings_path is not None:
        default_terminal = "Windows Terminal"
    if not default_terminal and os.name == "nt":
        default_terminal = "Windows Console Host"

    return {
        "default_terminal": default_terminal,
        "default_profile": default_profile,
        "shells": shells,
        "applications": terminal_apps,
        "modifications": _terminal_modifications(
            settings_path, settings, profiles, defaults, shell_profiles
        ),
    }
