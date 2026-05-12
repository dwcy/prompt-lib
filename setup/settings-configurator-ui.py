# -*- coding: utf-8 -*-
"""settings-configurator-ui.py — HEXTRAVAGANT Claude Code Setup Wizard (Textual TUI).

Run: python setup/settings-configurator-ui.py
Auto-installs textual on first run.

Modes (left/right arrows + Enter, or letter shortcut):
  - View README          (scrollable markdown)
  - Initialize env vars  (form + setx / shell rc + git config)
  - Operations:
      Update            deploy global/ → ~/.claude/ with preview
      MCP               list / toggle / edit servers (global or project)
      Doctor            drift report repo vs target
      Restore           roll back settings.json from backup
      Local             scaffold .claude/ in another project
"""

from __future__ import annotations

import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# Auto-install deps on first run
try:
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Center, Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll
    from textual.screen import ModalScreen, Screen
    from textual.widgets import (
        Button, Checkbox, DataTable, Footer, Header, Input, Label,
        MarkdownViewer, OptionList, RadioButton, RadioSet, Rule, Select, Static
    )
    from textual.widget import Widget
    from textual.widgets.option_list import Option
    from textual.widgets._header import HeaderIcon
    from textual.command import DiscoveryHit, Hits
    from textual.system_commands import SystemCommandsProvider
except ImportError:
    print("First run — installing textual...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "textual"])
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Center, Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll
    from textual.screen import ModalScreen, Screen
    from textual.widgets import (
        Button, Checkbox, DataTable, Footer, Header, Input, Label,
        MarkdownViewer, OptionList, RadioButton, RadioSet, Rule, Select, Static
    )
    from textual.widget import Widget
    from textual.widgets.option_list import Option
    from textual.widgets._header import HeaderIcon
    from textual.command import DiscoveryHit, Hits
    from textual.system_commands import SystemCommandsProvider
    from textual.widgets._header import HeaderIcon


# ─── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
GLOBAL_DIR = REPO_DIR / "global"
ENV_DIR = SCRIPT_DIR / "env"
ENV_FILE = ENV_DIR / "setup.env.example.json"
TARGET = Path.home() / ".claude"


# ─── Visual constants ──────────────────────────────────────────────────────────

MASCOT = r"""  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/
__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/
  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/
__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/"""

LOGO = r"""██╗  ██╗███████╗██╗  ██╗████████╗██████╗  █████╗ ██╗   ██╗ █████╗  ██████╗  █████╗ ███╗   ██╗████████╗
██║  ██║██╔════╝╚██╗██╔╝╚══██╔══╝██╔══██╗██╔══██╗██║   ██║██╔══██╗██╔════╝ ██╔══██╗████╗  ██║╚══██╔══╝
███████║█████╗   ╚███╔╝    ██║   ██████╔╝███████║██║   ██║███████║██║  ███╗███████║██╔██╗ ██║   ██║
██╔══██║██╔══╝   ██╔██╗    ██║   ██╔══██╗██╔══██║╚██╗ ██╔╝██╔══██║██║   ██║██╔══██║██║╚██╗██║   ██║
██║  ██║███████╗██╔╝ ██╗   ██║   ██║  ██║██║  ██║ ╚████╔╝ ██║  ██║╚██████╔╝██║  ██║██║ ╚████║   ██║
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝"""

LOGO_GRADIENT = ["#FFB6C1", "#FF85B3", "#FF55A5", "#FF2897", "#FF0080", "#CC006B"]
MASCOT_GRADIENT = ["#CC006B", "#FF2897", "#FF85B3", "#FFB6C1"]


def render_banner() -> Text:
    """Mascot + logo + tagline as a single Rich Text with gradient coloring."""
    txt = Text()
    mascot_lines = MASCOT.splitlines()
    n = len(mascot_lines)
    for i, line in enumerate(mascot_lines):
        idx = (i * len(MASCOT_GRADIENT)) // max(1, n - 1) if n > 1 else 0
        idx = min(idx, len(MASCOT_GRADIENT) - 1)
        txt.append(line + "\n", style=f"bold {MASCOT_GRADIENT[idx]}")
    txt.append("\n")
    logo_lines = LOGO.splitlines()
    n = len(logo_lines)
    for i, line in enumerate(logo_lines):
        idx = (i * len(LOGO_GRADIENT)) // max(1, n - 1) if n > 1 else 0
        idx = min(idx, len(LOGO_GRADIENT) - 1)
        txt.append(line + "\n", style=f"bold {LOGO_GRADIENT[idx]}")
    txt.append("\n« Claude Code Setup Wizard »", style="italic bright_cyan")
    return txt


def render_env_summary() -> Text:
    env = detect_env()
    txt = Text()
    txt.append("OS: ", style="bold bright_blue")
    txt.append(f"{env['os']} {env['release']}    ", style="white")
    txt.append("Python: ", style="bold bright_blue")
    txt.append(f"{env['python']}    ", style="white")
    txt.append("git/bash: ", style="bold bright_blue")
    txt.append("✓" if env["git"] else "✗", style="green" if env["git"] else "red")
    txt.append("/")
    txt.append("✓" if env["bash"] else "✗", style="green" if env["bash"] else "red")
    txt.append("    Claude CLI: ", style="bold bright_blue")
    txt.append("✓ installed" if env["claude"] else "✗ not found", style="green" if env["claude"] else "red")
    txt.append("    gh: ", style="bold bright_blue")
    txt.append("✓ installed" if env["gh"] else "✗ not found", style="green" if env["gh"] else "red")
    txt.append("\nSource: ", style="bold bright_blue")
    txt.append(f"{GLOBAL_DIR}\n", style="cyan")
    txt.append("Target: ", style="bold bright_blue")
    txt.append(f"{TARGET} ", style="cyan")
    txt.append(
        "(exists)" if env["target_exists"] else "(will be created)",
        style="green" if env["target_exists"] else "yellow",
    )
    return txt


# ─── Components ────────────────────────────────────────────────────────────────

def _os_should_skip(filename: str) -> bool:
    """Filename-prefix convention for OS-specific files.

    Names starting with linux_ / darwin_ / windows_ deploy only on the matching OS.
    Anything else deploys everywhere.
    """
    sys = platform.system()  # "Windows" | "Linux" | "Darwin"
    if filename.startswith("linux_") and sys != "Linux":
        return True
    if filename.startswith("darwin_") and sys != "Darwin":
        return True
    if filename.startswith("windows_") and sys != "Windows":
        return True
    return False


@dataclass
class Component:
    key: str
    label: str
    type: str
    src: str
    dst: str
    glob: str = "*"
    recursive: bool = False

    @property
    def src_path(self) -> Path:
        return GLOBAL_DIR / self.src

    @property
    def dst_path(self) -> Path:
        return TARGET / self.dst

    def list_files(self) -> list[tuple[Path, Path]]:
        if not self.src_path.exists():
            return []
        if self.type == "file":
            if _os_should_skip(self.src_path.name):
                return []
            return [(self.src_path, Path(self.src).name)]
        out: list[tuple[Path, Path]] = []
        iterator = self.src_path.rglob("*") if self.recursive else self.src_path.glob(self.glob)
        for f in iterator:
            if f.is_file() and not _os_should_skip(f.name):
                out.append((f, f.relative_to(self.src_path)))
        return out


COMPONENTS: list[Component] = [
    Component("settings",          "settings.json",      "file", "settings.json",      "settings.json"),
    Component("claude_md",         "CLAUDE.md",          "file", "CLAUDE.md",          "CLAUDE.md"),
    Component("design_md",         "DESIGN.md",          "file", "DESIGN.md",          "DESIGN.md"),
    Component("keybindings",       "keybindings.json",   "file", "keybindings.json",   "keybindings.json"),
    Component("statusline",        "statusline.py",      "file", "statusline.py",      "statusline.py"),
    Component("agents",            "agents/",            "dir",  "agents",             "agents",           glob="*.md"),
    Component("hooks",             "hooks/",             "dir",  "hooks",              "hooks",            glob="*"),
    Component("skills",            "skills/",            "dir",  "skills",             "skills",           glob="*.md"),
    Component("rules",             "rules/",             "dir",  "rules",              "rules",            glob="*.md"),
    Component("output_styles",     "output-styles/",     "dir",  "output-styles",      "output-styles",    glob="*.md"),
    Component("project_templates", "project-templates/", "dir",  "project-templates",  "project-templates", glob="*.md"),
    Component("git_templates",     "git/ templates",     "dir",  "git",                "git",              recursive=True),
]

ENV_DESCRIPTIONS: dict[str, str] = {
    "GITHUB_PERSONAL_ACCESS_TOKEN": (
        "GitHub MCP server — gives Claude access to repos, issues, PRs, and code search. "
        "Create at github.com/settings/tokens (repo + read:org scopes)."
    ),
    "FIGMA_ACCESS_TOKEN": (
        "Figma MCP server — gives Claude read access to files, components, and design tokens. "
        "Create at figma.com/settings under Personal access tokens."
    ),
    "POSTGRES_CONNECTION_STRING": (
        "Direct PostgreSQL connection for services that query the DB (e.g. postgresql://user:pass@host:5432/db). "
        "Not required for MCP servers — only for local service scripts."
    ),
    "AZURE_DEVOPS_ORG_URL": (
        "Azure DevOps MCP server — your organisation URL (e.g. https://dev.azure.com/your-org). "
        "Pair with AZURE_DEVOPS_TOKEN."
    ),
    "AZURE_DEVOPS_TOKEN": (
        "Azure DevOps MCP server — Personal Access Token for work items, repos, pipelines, and PRs. "
        "Create in Azure DevOps → User Settings → Personal access tokens."
    ),
    "SUPABASE_ACCESS_TOKEN": (
        "Supabase MCP server — gives Claude access to your project's DB, auth, storage, and edge functions. "
        "Create at supabase.com/dashboard/account/tokens."
    ),
    "OBSIDIAN_API_KEY": (
        "Obsidian MCP server — API key from the Local REST API plugin. "
        "Lets Claude read and search your vault. Enable the plugin in Obsidian first."
    ),
    "OBSIDIAN_HOST": (
        "Obsidian MCP server — host where the Local REST API plugin listens (default: 127.0.0.1). "
        "Change only if Obsidian runs on a remote machine."
    ),
    "OBSIDIAN_PORT": (
        "Obsidian MCP server — port for the Local REST API plugin (default: 27123). "
        "Change only if you've set a custom port in the plugin settings."
    ),
    "PROJECTS_PATH": (
        "Base directory for your projects (e.g. C:/projects or ~/projects). "
        "Used by session hooks and helper scripts to resolve project paths."
    ),
    "TEMP_PATH": (
        "Scratch directory for temporary files generated during Claude sessions. "
        "Defaults to the OS temp dir if left empty."
    ),
    "GIT_LINE_ENDINGS": (
        "Sets git core.autocrlf globally. "
        "auto = LF in repo, CRLF on Windows checkout (recommended). "
        "Other values: true, false, input."
    ),
}


@dataclass
class FileStatus:
    rel: Path
    src: Path
    dst: Path
    state: str  # NEW | CHANGED | UNCHANGED


# ─── Update check ──────────────────────────────────────────────────────────────

def check_for_updates() -> dict:
    if not shutil.which("git"):
        return {"status": "no_git"}
    try:
        local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_DIR), timeout=5,
        )
        remote = subprocess.run(
            ["git", "ls-remote", "origin", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_DIR), timeout=10,
        )
        if local.returncode != 0 or remote.returncode != 0 or not remote.stdout.strip():
            return {"status": "error"}
        local_hash = local.stdout.strip()
        remote_hash = remote.stdout.split()[0]
        short = lambda h: h[:8]
        if local_hash == remote_hash:
            return {"status": "up_to_date", "hash": short(local_hash)}
        return {"status": "behind", "local": short(local_hash), "remote": short(remote_hash)}
    except Exception:
        return {"status": "error"}


def do_git_pull() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True, cwd=str(REPO_DIR), timeout=60,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


# ─── Pure helpers ──────────────────────────────────────────────────────────────

def detect_env() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "shell": os.environ.get("SHELL") or os.environ.get("COMSPEC", "?"),
        "git": shutil.which("git") is not None,
        "bash": shutil.which("bash") is not None,
        "claude": shutil.which("claude") is not None,
        "gh": shutil.which("gh") is not None,
        "target_exists": TARGET.exists(),
    }


def find_env_vars(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", path.read_text(encoding="utf-8", errors="ignore"))))


def diff_component(comp: Component) -> list[FileStatus]:
    out: list[FileStatus] = []
    for src_file, rel in comp.list_files():
        dst_file = comp.dst_path / rel if comp.type == "dir" else comp.dst_path
        if not dst_file.exists():
            out.append(FileStatus(rel, src_file, dst_file, "NEW"))
        elif filecmp.cmp(src_file, dst_file, shallow=False):
            out.append(FileStatus(rel, src_file, dst_file, "UNCHANGED"))
        else:
            out.append(FileStatus(rel, src_file, dst_file, "CHANGED"))
    return out


def find_extras(comp: Component) -> list[Path]:
    if comp.type == "file" or not comp.dst_path.exists():
        return []
    src_rels = {rel for _, rel in comp.list_files()}
    iterator = comp.dst_path.rglob("*") if comp.recursive else comp.dst_path.glob(comp.glob)
    return [f.relative_to(comp.dst_path) for f in iterator if f.is_file() and f.relative_to(comp.dst_path) not in src_rels]


def apply_statuses(statuses: list[FileStatus]) -> tuple[int, int]:
    copied = skipped = 0
    for st in statuses:
        if st.state == "UNCHANGED":
            skipped += 1
        else:
            st.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(st.src, st.dst)
            copied += 1
    return copied, skipped


def backup_settings() -> Path | None:
    src = TARGET / "settings.json"
    if not src.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = TARGET / f"settings.json.bak.{ts}"
    shutil.copy2(src, dst)
    return dst


def prune_backups(keep: int = 10) -> None:
    baks = sorted(TARGET.glob("settings.json.bak*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in baks[keep:]:
        old.unlink(missing_ok=True)


def recommended_autocrlf() -> str:
    return "true" if platform.system() == "Windows" else "input"


def apply_git_line_endings(mode: str) -> tuple[bool, str]:
    if mode == "auto":
        resolved = recommended_autocrlf()
    elif mode in ("true", "input", "false"):
        resolved = mode
    else:
        return False, f"Unrecognized GIT_LINE_ENDINGS={mode!r}"
    if not shutil.which("git"):
        return False, "git not on PATH"
    result = subprocess.run(
        ["git", "config", "--global", "core.autocrlf", resolved],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, f"git config --global core.autocrlf {resolved}"
    return False, f"git config failed: {result.stderr.strip()}"


# ─── Tools (GitHub release installers) ─────────────────────────────────────────

def _gh_latest_release(repo: str) -> dict:
    import urllib.request as _ur
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "prompt-lib-installer"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = _ur.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    with _ur.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _gh_pick_asset(release: dict, suffix: str) -> dict | None:
    for a in release.get("assets") or []:
        if a.get("name", "").endswith(suffix):
            return a
    return None


def _download(url: str, dest: Path) -> None:
    import urllib.request as _ur
    headers = {"User-Agent": "prompt-lib-installer", "Accept": "application/octet-stream"}
    req = _ur.Request(url, headers=headers)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ur.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


CDT_REPO = "matt1398/claude-devtools"


def _cdt_windows_exe() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "claude-devtools" / "claude-devtools.exe"


def cdt_status() -> str:
    sysname = platform.system()
    if sysname == "Windows":
        exe = _cdt_windows_exe()
        if not exe.exists():
            return "not installed"
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"(Get-Item '{exe}').VersionInfo.FileVersion"],
            capture_output=True, text=True,
        )
        v = (ps.stdout or "").strip()
        return f"installed {v}" if v else "installed"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(
                ["brew", "list", "--cask", "--versions", "claude-devtools"],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"installed ({r.stdout.strip()})"
        if Path("/Applications/claude-devtools.app").exists():
            return "installed"
        return "not installed"
    if sysname == "Linux":
        for p in ("/usr/bin/claude-devtools", "/opt/claude-devtools/claude-devtools"):
            if Path(p).exists():
                return f"installed ({p})"
        return "not installed"
    return "unsupported platform"


def cdt_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Darwin":
        if not shutil.which("brew"):
            return False, "Homebrew not found — install brew or download from claude-dev.tools"
        r = subprocess.run(["brew", "install", "--cask", "claude-devtools"])
        return r.returncode == 0, "brew install --cask claude-devtools"

    try:
        release = _gh_latest_release(CDT_REPO)
    except Exception as e:
        return False, f"GitHub API failed: {e}"
    tag = release.get("tag_name", "")

    if sysname == "Windows":
        asset = _gh_pick_asset(release, "-x64.exe")
        if not asset:
            return False, "No Windows installer in latest release"
        tmp_root = Path(os.environ.get("TEMP") or Path.home())
        tmp = tmp_root / asset["name"]
        try:
            _download(asset["browser_download_url"], tmp)
        except Exception as e:
            return False, f"Download failed: {e}"
        r = subprocess.run([str(tmp), "/S"])
        if r.returncode != 0:
            return False, f"Installer exit code {r.returncode}"
        return True, f"Installed {tag} from {asset['name']}"

    if sysname == "Linux":
        if shutil.which("dnf"):
            asset, installer = _gh_pick_asset(release, ".rpm"), ["sudo", "dnf", "install", "-y"]
        elif shutil.which("apt-get"):
            asset, installer = _gh_pick_asset(release, ".deb"), ["sudo", "apt-get", "install", "-y"]
        elif shutil.which("pacman"):
            asset, installer = _gh_pick_asset(release, ".pacman"), ["sudo", "pacman", "-U", "--noconfirm"]
        else:
            return False, "No supported package manager (need dnf, apt-get, or pacman)"
        if not asset:
            return False, "No matching Linux package in latest release"
        tmp = Path("/tmp") / asset["name"]
        try:
            _download(asset["browser_download_url"], tmp)
        except Exception as e:
            return False, f"Download failed: {e}"
        r = subprocess.run([*installer, str(tmp)])
        return r.returncode == 0, f"Installed {tag}"

    return False, f"Unsupported platform: {sysname}"


# ─── Claude CLI ────────────────────────────────────────────────────────────────

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


# ─── GitHub CLI ────────────────────────────────────────────────────────────────

def gh_status() -> str:
    if not shutil.which("gh"):
        return "not installed"
    r = subprocess.run(["gh", "--version"], capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()[0] if r.returncode == 0 else ""
    return f"installed {v}" if v else "installed"


def gh_install() -> tuple[bool, str]:
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            r = subprocess.run(["winget", "install", "--id", "GitHub.cli", "-e"], capture_output=True, text=True)
            return r.returncode == 0, "winget install GitHub.cli"
        if shutil.which("scoop"):
            r = subprocess.run(["scoop", "install", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "scoop install gh"
        return False, "Install manually from https://cli.github.com"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(["brew", "install", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "brew install gh"
        return False, "Install Homebrew first or download from https://cli.github.com"
    if sysname == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update", "-y"], capture_output=True)
            r = subprocess.run(["sudo", "apt-get", "install", "-y", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "apt-get install gh"
        if shutil.which("dnf"):
            r = subprocess.run(["sudo", "dnf", "install", "-y", "gh"], capture_output=True, text=True)
            return r.returncode == 0, "dnf install gh"
        return False, "Install manually from https://cli.github.com"
    return False, f"Unsupported platform: {sysname}"


@dataclass
class Tool:
    key: str
    name: str
    description: str
    homepage: str
    repo_url: str
    install: Callable[[], tuple[bool, str]]
    status: Callable[[], str]


TOOLS: list[Tool] = [
    Tool(
        key="claude-cli",
        name="Claude CLI (claude-code)",
        description=(
            "The Claude Code CLI — Anthropic's official terminal interface for Claude. "
            "Installed globally via npm. Required for all Claude Code sessions."
        ),
        homepage="https://claude.ai/code",
        repo_url="https://github.com/anthropics/claude-code",
        install=claude_cli_install,
        status=claude_cli_status,
    ),
    Tool(
        key="gh",
        name="GitHub CLI (gh)",
        description=(
            "GitHub's official CLI for managing repos, PRs, issues, and Actions from the terminal. "
            "Required by skills that create PRs or interact with GitHub."
        ),
        homepage="https://cli.github.com",
        repo_url="https://github.com/cli/cli",
        install=gh_install,
        status=gh_status,
    ),
    Tool(
        key="claude-devtools",
        name="claude-devtools",
        description=(
            "Desktop GUI that visualizes Claude Code session activity by reading "
            "local session logs in ~/.claude/. See every file path, tool call, and "
            "token. Runs locally — no config or API keys."
        ),
        homepage="https://claude-dev.tools/",
        repo_url="https://github.com/matt1398/claude-devtools",
        install=cdt_install,
        status=cdt_status,
    ),
]


# ─── Screens ───────────────────────────────────────────────────────────────────

class UpdatePanel(Widget):
    """Async update checker — compares local HEAD to origin and offers git pull."""

    DEFAULT_CSS = """
    UpdatePanel {
        height: auto;
        margin: 0 2 0 2;
    }
    #update-row {
        height: 3;
        align-vertical: middle;
        padding: 0;
        margin: 0;
    }
    #update-msg {
        width: 1fr;
        padding: 0 1;
        content-align: left middle;
        height: 3;
    }
    #btn-pull { margin: 0; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="update-row"):
            yield Static("[dim]Checking for updates…[/dim]", id="update-msg")
            yield Button("⬆ Pull update", id="btn-pull", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#btn-pull").display = False
        self.run_worker(self._check, thread=True, exclusive=True)

    def _check(self) -> None:
        result = check_for_updates()
        self.app.call_from_thread(self._apply, result)

    def _apply(self, result: dict) -> None:
        msg = self.query_one("#update-msg", Static)
        btn = self.query_one("#btn-pull", Button)
        if result["status"] == "up_to_date":
            msg.update(f"[green]✓ Up to date[/green]  [dim]{result['hash']}[/dim]")
        elif result["status"] == "behind":
            msg.update(
                f"[yellow bold]⬆ Update available[/yellow bold]  "
                f"[dim]{result['local']} → {result['remote']}[/dim]"
            )
            btn.display = True
        elif result["status"] == "no_git":
            msg.update("[dim]git not found — cannot check for updates[/dim]")
        else:
            msg.update("[dim]⚠ Could not reach remote[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pull":
            event.stop()
            self.query_one("#btn-pull").display = False
            self.query_one("#update-msg", Static).update("[yellow]Pulling…[/yellow]")
            self.run_worker(self._pull, thread=True, exclusive=True)

    def _pull(self) -> None:
        ok, output = do_git_pull()
        def _done() -> None:
            msg = self.query_one("#update-msg", Static)
            if ok:
                msg.update("[green]✓ Pulled — restart the wizard to apply changes[/green]")
            else:
                msg.update(f"[red]✗ Pull failed:[/red] [dim]{output[:120]}[/dim]")
                self.query_one("#btn-pull").display = True
        self.app.call_from_thread(_done)


class AppCommandsProvider(SystemCommandsProvider):
    """System commands with Quit pinned to the bottom of the discovery list."""

    async def discover(self) -> Hits:
        commands = list(self.app.get_system_commands(self.screen))
        quit_cmd = next((c for c in commands if c.title == "Quit"), None)
        for cmd in sorted((c for c in commands if c.title != "Quit"), key=lambda c: c.title):
            if cmd.discover:
                yield DiscoveryHit(cmd.title, cmd.callback, help=cmd.help)
        if quit_cmd and quit_cmd.discover:
            yield DiscoveryHit(quit_cmd.title, quit_cmd.callback, help=quit_cmd.help)


class AppHeader(Header):
    def on_mount(self) -> None:
        self.query_one(HeaderIcon).icon = "▼"


class HomeScreen(Screen):
    """Landing screen — banner + horizontal nav."""

    BINDINGS = [
        Binding("r", "go('readme')", "README"),
        Binding("e", "go('env')", "Env"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader(show_clock=True)
        with VerticalScroll(id="home-scroll"):
            yield Static(render_banner(), id="banner", classes="centered")
            yield Static(render_env_summary(), id="env-summary", classes="panel")
            yield UpdatePanel()
            with Horizontal(id="home-nav"):
                yield Button("[E] Env vars", id="btn-env", variant="primary")
            with Vertical(classes="home-section"):
                yield Static("[bold]Global Claude Settings[/bold]", classes="home-section-title")
                with Horizontal(classes="ops-row"):
                    yield Button("[U] Update", id="btn-op-update", variant="default")
                    yield Button("[R] Restore", id="btn-op-restore", variant="default")
            with Vertical(classes="home-section"):
                yield Static("[bold]Local Claude Settings[/bold]", classes="home-section-title")
                with Horizontal(classes="ops-row"):
                    yield Button("[D] Doctor", id="btn-op-doctor", variant="default")
                    yield Button("[L] Local", id="btn-op-local", variant="default")
            with Horizontal(classes="ops-row"):
                yield Button("[M] MCP", id="btn-op-mcp", variant="default")
                yield Button("[T] Tools", id="btn-op-tools", variant="default")
        with Horizontal(id="home-bottom"):
            yield Button("[R] README", id="btn-readme", variant="primary")
            yield Static("", classes="home-spacer")
            yield Button("[Q] Quit", id="btn-quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#btn-readme", Button).focus()

    def action_go(self, name: str) -> None:
        if name == "readme":
            self.app.push_screen(ReadmeScreen())
        elif name == "env":
            self.app.push_screen(EnvScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        op_screens = {
            "btn-op-update":  UpdateScreen,
            "btn-op-mcp":     McpScreen,
            "btn-op-doctor":  DoctorScreen,
            "btn-op-restore": RestoreScreen,
            "btn-op-local":   LocalScreen,
            "btn-op-tools":   ToolsScreen,
        }
        if bid == "btn-readme":
            self.action_go("readme")
        elif bid == "btn-env":
            self.action_go("env")
        elif bid == "btn-quit":
            self.app.exit()
        elif bid in op_screens:
            self.app.push_screen(op_screens[bid]())


class ReadmeScreen(Screen):
    """Render the project README in a scrollable Markdown viewer."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("q", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        readme = next(
            (p for p in [REPO_DIR / "README.md", GLOBAL_DIR / "README.md", SCRIPT_DIR / "README.md"] if p.exists()),
            None,
        )
        if readme:
            yield MarkdownViewer(readme.read_text(encoding="utf-8"), show_table_of_contents=True)
        else:
            yield Static("[yellow]No README.md found.[/yellow]")
        yield Footer()


_PATH_KEYS: frozenset[str] = frozenset({"PROJECTS_PATH", "TEMP_PATH"})


class EnvScreen(Screen):
    """Show env vars (values from system env) and apply via setx / shell rc + git config."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        keys = list(json.loads(ENV_FILE.read_text(encoding="utf-8")).keys()) if ENV_FILE.exists() else []
        self.data: dict[str, str] = {k: os.environ.get(k, "") for k in keys}

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Environment variables ✦[/bold bright_magenta]\n"
                "[dim]Values read from system environment. "
                "Apply (Ctrl+A) sets them via setx (Windows) or shell rc (Unix). "
                "Status icon: ✓ set in current shell, ✗ missing.[/dim]",
                classes="panel",
            )
            for key, val in self.data.items():
                shell_set = bool(os.environ.get(key))
                icon = "[green]✓[/green]" if shell_set else "[red]✗[/red]"
                is_path = key in _PATH_KEYS
                with Horizontal(classes="env-row"):
                    yield Static(f"[bold cyan]{key}[/bold cyan]", classes="env-name")
                    yield Static(icon, classes="env-icon")
                    if is_path:
                        yield Button("Browse…", id=f"browse-{key}", classes="env-browse")
                    yield Input(value=str(val), id=f"in-{key}", placeholder="(empty)", classes="env-value")
                desc = ENV_DESCRIPTIONS.get(key)
                if desc:
                    yield Static(desc, classes="help-text")
            yield Static("")
            with Horizontal(id="env-actions"):
                yield Button("Apply (Ctrl+A)", id="env-apply", variant="success")
                yield Button("Back (Esc)", id="env-back")
            yield Static("", id="env-status")
        yield Footer()

    def _gather(self) -> dict[str, str]:
        out = {}
        for key in self.data.keys():
            inp = self.query_one(f"#in-{key}", Input)
            out[key] = inp.value
        return out

    def _open_browser(self, key: str) -> None:
        raw = self.query_one(f"#in-{key}", Input).value
        start = Path(raw).expanduser() if raw else Path.home()
        if not start.is_dir():
            start = start.parent if start.parent.is_dir() else Path.home()

        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one(f"#in-{key}", Input).value = str(path)

        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def action_apply(self) -> None:
        data = self._gather()
        msgs = []
        non_empty = {k: v for k, v in data.items() if v.strip()}

        if platform.system() == "Windows":
            for k, v in non_empty.items():
                r = subprocess.run(["setx", k, v], capture_output=True, text=True)
                ok = r.returncode == 0
                msgs.append(f"  {'[green]✓[/green]' if ok else '[red]✗[/red]'} setx {k}")
        else:
            export_lines = [f"export {k}={repr(v)}" for k, v in non_empty.items()]
            for profile in ["~/.bashrc", "~/.zshrc", "~/.profile"]:
                update_profile(profile, list(non_empty.keys()), export_lines)
            msgs.append("[green]✓ Updated shell rc files[/green]")

        gle = data.get("GIT_LINE_ENDINGS", "").strip()
        if gle:
            ok, msg = apply_git_line_endings(gle)
            msgs.append(f"  {'[green]✓[/green]' if ok else '[red]✗[/red]'} {msg}")

        msgs.append("\n[bold]→ Restart your terminal for changes to take effect.[/bold]")
        self.query_one("#env-status", Static).update("\n".join(msgs))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "env-apply":
            self.action_apply()
        elif bid == "env-back":
            self.app.pop_screen()
        elif bid.startswith("browse-"):
            self._open_browser(bid.removeprefix("browse-"))


class OperationsScreen(Screen):
    """Sub-menu for the heavier flows."""

    BINDINGS = [
        Binding("u", "go('update')", "Update"),
        Binding("m", "go('mcp')", "MCP"),
        Binding("d", "go('doctor')", "Doctor"),
        Binding("r", "go('restore')", "Restore"),
        Binding("l", "go('local')", "Local"),
        Binding("t", "go('tools')", "Tools"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Operations ✦[/bold bright_magenta]\n"
                "[dim]Pick an action — letter shortcut or click.[/dim]",
                classes="panel",
            )
            with Horizontal(id="ops-nav"):
                yield Button("[U] Update", id="op-update", variant="primary")
                yield Button("[M] MCP", id="op-mcp", variant="primary")
                yield Button("[D] Doctor", id="op-doctor", variant="primary")
                yield Button("[R] Restore", id="op-restore", variant="primary")
                yield Button("[L] Local", id="op-local", variant="primary")
                yield Button("[T] Tools", id="op-tools", variant="primary")
                yield Button("Back (Esc)", id="op-back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#op-update", Button).focus()

    def action_go(self, name: str) -> None:
        target = {
            "update": UpdateScreen,
            "mcp": McpScreen,
            "doctor": DoctorScreen,
            "restore": RestoreScreen,
            "local": LocalScreen,
            "tools": ToolsScreen,
        }.get(name)
        if target:
            self.app.push_screen(target())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "").removeprefix("op-")
        if bid == "back":
            self.app.pop_screen()
        else:
            self.action_go(bid)


class UpdateScreen(Screen):
    """Multi-select components, preview diff, then apply."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Update global settings ✦[/bold bright_magenta]\n"
                f"[dim]Deploy {GLOBAL_DIR} → {TARGET}.[/dim]\n"
                "[dim]Toggle components, then Apply (Ctrl+A).[/dim]",
                classes="panel",
            )
            yield Static("", id="update-summary")
            for c in COMPONENTS:
                files = c.list_files()
                count = f" ({len(files)})" if c.type == "dir" else ""
                missing = "" if c.src_path.exists() else "  [red](missing in repo)[/red]"
                yield Checkbox(
                    f"{c.label}{count}{missing}",
                    value=c.src_path.exists(),
                    id=f"cb-{c.key}",
                    disabled=not c.src_path.exists(),
                )
            yield Static("")
            yield DataTable(id="preview", show_cursor=False)
            yield Static("")
            with Horizontal():
                yield Button("Refresh preview (Ctrl+R)", id="upd-refresh")
                yield Button("Apply (Ctrl+A)", id="upd-apply", variant="success")
                yield Button("Back (Esc)", id="upd-back")
            yield Static("", id="upd-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#preview", DataTable)
        tbl.add_columns("Component", "New", "Changed", "Unchanged", "Affected")
        self._refresh_preview()

    def _selected_components(self) -> list[Component]:
        out = []
        for c in COMPONENTS:
            cb = self.query_one(f"#cb-{c.key}", Checkbox)
            if cb.value and not cb.disabled:
                out.append(c)
        return out

    def _refresh_preview(self) -> None:
        tbl = self.query_one("#preview", DataTable)
        tbl.clear()
        comps = self._selected_components()
        totals = {"new": 0, "changed": 0, "unchanged": 0}
        for c in comps:
            statuses = diff_component(c)
            new = sum(1 for s in statuses if s.state == "NEW")
            chg = sum(1 for s in statuses if s.state == "CHANGED")
            unc = sum(1 for s in statuses if s.state == "UNCHANGED")
            totals["new"] += new
            totals["changed"] += chg
            totals["unchanged"] += unc
            affected = [s.rel for s in statuses if s.state != "UNCHANGED"]
            names = ", ".join(str(p) for p in affected[:3])
            if len(affected) > 3:
                names += f", … +{len(affected) - 3}"
            tbl.add_row(
                c.label,
                str(new) if new else "·",
                str(chg) if chg else "·",
                str(unc) if unc else "·",
                names if names else "[dim]up to date[/dim]",
            )
        self.query_one("#update-summary", Static).update(
            f"[bold]Selected: {len(comps)} components[/bold]   "
            f"[green]NEW {totals['new']}[/green]   "
            f"[yellow]CHANGED {totals['changed']}[/yellow]   "
            f"[dim]UNCHANGED {totals['unchanged']}[/dim]"
        )

    def action_refresh(self) -> None:
        self._refresh_preview()

    def action_apply(self) -> None:
        comps = self._selected_components()
        if not comps:
            self.query_one("#upd-status", Static).update("[yellow]Nothing selected.[/yellow]")
            return
        msgs = []
        if any(c.key == "settings" for c in comps):
            bk = backup_settings()
            if bk:
                msgs.append(f"[dim]Backed up settings.json → {bk.name}[/dim]")
            prune_backups(10)
        TARGET.mkdir(parents=True, exist_ok=True)
        total_copied = total_skipped = 0
        for c in comps:
            statuses = diff_component(c)
            copied, skipped = apply_statuses(statuses)
            total_copied += copied
            total_skipped += skipped
            msgs.append(f"  [green]✓[/green] {c.label}: {copied} copied, {skipped} unchanged")
        msgs.append(f"\n[bold green]✓ Apply complete.[/bold green]  [bold]→ Restart Claude Code.[/bold]")
        self.query_one("#upd-status", Static).update("\n".join(msgs))
        self._refresh_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "upd-refresh":
            self._refresh_preview()
        elif bid == "upd-apply":
            self.action_apply()
        elif bid == "upd-back":
            self.app.pop_screen()


class DoctorScreen(Screen):
    """Drift report — repo vs target."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("ctrl+r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Doctor — drift report ✦[/bold bright_magenta]\n"
                f"[dim]Comparing {GLOBAL_DIR} (repo) against {TARGET} (target).[/dim]\n\n"
                "[bold red]Repo only[/bold red]   In repo, not deployed yet. → Run [bold]Update[/bold].\n"
                "[bold yellow]Differs[/bold yellow]      In both, content mismatch. Repo wins on Update.\n"
                "[bold magenta]Target only[/bold magenta]  In ~/.claude/, not in repo. Stale or unsaved-promotion.",
                classes="panel",
            )
            yield Static("", id="doctor-summary")
            yield DataTable(id="drift", show_cursor=False)
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#drift", DataTable)
        tbl.add_columns("Component", "Repo only", "Differs", "Target only", "Files")
        self._refresh()

    def action_refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        tbl = self.query_one("#drift", DataTable)
        tbl.clear()
        any_issue = False
        for comp in COMPONENTS:
            if not comp.src_path.exists():
                continue
            statuses = diff_component(comp)
            repo_only = [str(s.rel) for s in statuses if s.state == "NEW"]
            differs = [str(s.rel) for s in statuses if s.state == "CHANGED"]
            target_only = [str(p) for p in find_extras(comp)]
            if repo_only or differs or target_only:
                any_issue = True
            parts = []
            for label, files, color in [("repo only", repo_only, "red"), ("differs", differs, "yellow"), ("target only", target_only, "magenta")]:
                if files:
                    shown = ", ".join(files[:3])
                    if len(files) > 3:
                        shown += f", … +{len(files) - 3}"
                    parts.append(f"[{color}]{label}:[/{color}] {shown}")
            files_col = " | ".join(parts) if parts else "[green]✓ in sync[/green]"
            tbl.add_row(
                comp.label,
                str(len(repo_only)) if repo_only else "·",
                str(len(differs)) if differs else "·",
                str(len(target_only)) if target_only else "·",
                files_col,
            )
        msg = "[yellow]⚠ Drift detected.[/yellow] Run Update to align." if any_issue else "[green]✓ Target matches repo.[/green]"
        self.query_one("#doctor-summary", Static).update(msg)


class RestoreScreen(Screen):
    """Pick a settings.json backup and restore it."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Restore settings.json ✦[/bold bright_magenta]\n"
                f"[dim]From {TARGET}[/dim]",
                classes="panel",
            )
            self.baks = sorted(TARGET.glob("settings.json.bak*"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            if not self.baks:
                yield Static("[yellow]No backups found.[/yellow]")
            else:
                opts = []
                for b in self.baks:
                    ts = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    opts.append(Option(f"{b.name}  ({ts}, {b.stat().st_size:,} bytes)", id=str(b)))
                yield OptionList(*opts, id="bak-list")
                yield Static("")
                with Horizontal():
                    yield Button("Restore selected", id="rst-apply", variant="warning")
                    yield Button("Back (Esc)", id="rst-back")
            yield Static("", id="rst-status", classes="panel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "rst-back":
            self.app.pop_screen()
        elif bid == "rst-apply":
            try:
                lst = self.query_one("#bak-list", OptionList)
            except Exception:
                return
            if lst.highlighted is None:
                self.query_one("#rst-status", Static).update("[yellow]Pick a backup first.[/yellow]")
                return
            opt = lst.get_option_at_index(lst.highlighted)
            backup = Path(opt.id)
            cur = TARGET / "settings.json"
            if cur.exists():
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(cur, TARGET / f"settings.json.bak.{ts}.pre-restore")
            shutil.copy2(backup, cur)
            self.query_one("#rst-status", Static).update(
                f"[green]✓ Restored from {backup.name}[/green]\n[bold]→ Restart Claude Code.[/bold]"
            )


class McpScreen(Screen):
    """List, toggle, and edit MCP servers — global or project scope."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+e", "edit", "Open in editor"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings_file: Path = GLOBAL_DIR / "settings.json"
        self.is_global = True

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Manage MCP servers ✦[/bold bright_magenta]",
                classes="panel",
            )
            with Horizontal():
                yield Label("Scope: ")
                yield RadioSet(
                    RadioButton("Global (global/settings.json)", value=True, id="scope-global"),
                    RadioButton("Project — enter path below", id="scope-project"),
                    id="scope",
                )
            with Horizontal():
                yield Label("Project path: ")
                yield Input(value=str(Path.cwd()), id="proj-path", placeholder="(only for project scope)")
            with Horizontal():
                yield Label("Project file: ")
                yield Select(
                    [
                        (".mcp.json", ".mcp.json"),
                        (".claude/settings.json", ".claude/settings.json"),
                        (".claude/settings.local.json", ".claude/settings.local.json"),
                    ],
                    id="proj-file",
                    value=".mcp.json",
                )
                yield Button("Reload", id="mcp-reload")
            yield Static("", id="mcp-target")
            yield DataTable(id="mcp-table", show_cursor=True, cursor_type="row")
            with Horizontal():
                yield Button("Toggle selected (Space)", id="mcp-toggle", variant="primary")
                yield Button("Open file in editor (Ctrl+E)", id="mcp-edit")
                yield Button("Back (Esc)", id="mcp-back")
            yield Static("", id="mcp-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.add_columns("Name", "Status", "Command", "Env vars")
        self._refresh()

    def _resolve_settings_file(self) -> Path:
        if self.is_global:
            return GLOBAL_DIR / "settings.json"
        proj = Path(self.query_one("#proj-path", Input).value).expanduser()
        sub = self.query_one("#proj-file", Select).value
        return proj / sub

    def _load(self) -> dict:
        if self.settings_file.exists():
            try:
                return json.loads(self.settings_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                self.query_one("#mcp-status", Static).update(f"[red]Invalid JSON: {e}[/red]")
                return {}
        return {}

    def _save(self, data: dict) -> None:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not data.get("mcpServersDisabled"):
            data.pop("mcpServersDisabled", None)
        if not data.get("mcpServers"):
            data.pop("mcpServers", None)
        self.settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _refresh(self) -> None:
        self.settings_file = self._resolve_settings_file()
        self.query_one("#mcp-target", Static).update(f"[cyan]Editing:[/cyan] {self.settings_file}")
        data = self._load()
        enabled = data.get("mcpServers") or {}
        disabled = data.get("mcpServersDisabled") or {}
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.clear()
        rows = [(n, c, "enabled") for n, c in enabled.items()] + [(n, c, "disabled") for n, c in disabled.items()]
        rows.sort(key=lambda x: x[0])
        for name, cfg, status in rows:
            cmd = (cfg.get("command", "") + " " + " ".join(cfg.get("args", []))).strip() or "—"
            env_keys = list((cfg.get("env") or {}).keys())
            env_disp = ", ".join(
                f"{k}{'✓' if os.environ.get(k) else '✗'}" for k in env_keys
            ) or "—"
            status_disp = "✓ enabled" if status == "enabled" else "✗ disabled"
            tbl.add_row(name, status_disp, cmd, env_disp, key=f"{status}:{name}")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.is_global = event.pressed.id == "scope-global"
        self._refresh()

    def action_refresh(self) -> None:
        self._refresh()

    def action_edit(self) -> None:
        editor = (
            os.environ.get("VISUAL") or os.environ.get("EDITOR")
            or ("notepad" if platform.system() == "Windows" else "nano")
        )
        with self.app.suspend():
            try:
                subprocess.call([editor, str(self.settings_file)])
            except FileNotFoundError:
                pass
        self._refresh()
        self.query_one("#mcp-status", Static).update(f"[dim]Reloaded after editor close.[/dim]")

    def _toggle_selected(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        if tbl.cursor_row is None or tbl.row_count == 0:
            return
        row_key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        if not row_key:
            return
        status, _, name = row_key.partition(":")
        data = self._load()
        enabled = data.get("mcpServers") or {}
        disabled = data.get("mcpServersDisabled") or {}
        if status == "enabled" and name in enabled:
            disabled[name] = enabled.pop(name)
        elif status == "disabled" and name in disabled:
            enabled[name] = disabled.pop(name)
        data["mcpServers"] = enabled
        data["mcpServersDisabled"] = disabled
        self._save(data)
        msg = f"[green]✓ Toggled {name}[/green]"
        if self.is_global:
            msg += "  [dim](run Update to deploy to ~/.claude/)[/dim]"
        self.query_one("#mcp-status", Static).update(msg)
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mcp-back":
            self.app.pop_screen()
        elif bid == "mcp-reload":
            self._refresh()
        elif bid == "mcp-toggle":
            self._toggle_selected()
        elif bid == "mcp-edit":
            self.action_edit()


class FolderBrowserScreen(ModalScreen):
    """Modal directory picker — navigate the filesystem tree and select a folder."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("backspace", "go_up", "Parent"),
    ]

    def __init__(self, start: Path) -> None:
        super().__init__()
        self._current = start.resolve() if start.is_dir() else start.parent.resolve()
        self._entries: list[Path] = []

    def compose(self) -> ComposeResult:
        with Container(id="browser-dialog"):
            yield Static("", id="browser-path")
            yield OptionList(id="browser-list")
            with Horizontal(id="browser-actions"):
                yield Button("Select  [bold]↵[/bold]", id="br-select", variant="success")
                yield Button("Parent  [bold]⌫[/bold]", id="br-up")
                yield Button("Cancel  [bold]Esc[/bold]", id="br-cancel", variant="error")

    def on_mount(self) -> None:
        self._populate()
        self.query_one("#browser-list", OptionList).focus()

    def _populate(self) -> None:
        lst = self.query_one("#browser-list", OptionList)
        lst.clear_options()
        self.query_one("#browser-path", Static).update(
            f"[bold cyan]  {self._current}[/bold cyan]"
        )
        at_root = self._current.parent == self._current
        if not at_root:
            lst.add_option(Option("  ..", id="__up__"))
        try:
            entries = sorted(
                [d for d in self._current.iterdir() if d.is_dir()],
                key=lambda p: p.name.lower(),
            )
        except PermissionError:
            entries = []
        self._entries = entries
        for i, d in enumerate(entries):
            lst.add_option(Option(f"  {d.name}", id=f"__dir_{i}__"))

    def action_go_up(self) -> None:
        if self._current.parent != self._current:
            self._current = self._current.parent
            self._populate()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id or ""
        if opt_id == "__up__":
            self.action_go_up()
        elif opt_id.startswith("__dir_"):
            idx = int(opt_id[6:-2])
            if 0 <= idx < len(self._entries):
                self._current = self._entries[idx]
                self._populate()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "br-select":
            self.dismiss(self._current)
        elif bid == "br-up":
            self.action_go_up()
        elif bid == "br-cancel":
            self.action_cancel()


class LocalScreen(Screen):
    """Set up .claude/ in another project."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    def __init__(self) -> None:
        super().__init__()
        tpls = sorted((GLOBAL_DIR / "project-templates").glob("*.md")) if (GLOBAL_DIR / "project-templates").exists() else []
        self.template_options = [(p.stem, str(p)) for p in tpls]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Local project setup ✦[/bold bright_magenta]\n"
                "[dim]Pick a project folder and the actions to take.[/dim]",
                classes="panel",
            )
            with Horizontal():
                yield Label("Project path: ")
                yield Button("Browse…", id="loc-browse")
                yield Input(value=str(Path.cwd()), id="loc-path")
            yield Checkbox("Create .claude/ scaffolding (skills/, hooks/, settings.local.json)", value=True, id="loc-scaffold")
            yield Static(
                "Creates .claude/skills/, .claude/hooks/, and settings.local.json with an empty permissions stub.\n"
                "Claude Code discovers project-local agents and skills from these dirs at session start (docs/architecture.md).\n"
                "[yellow]⚑ TODO: Edit .claude/settings.local.json → add allow[] entries for commands this project needs "
                "(e.g. npm, pytest, dotnet). Run Initialize env vars from the home screen first if MCP servers are needed.[/yellow]\n"
                "Test: ls .claude/ → skills/, hooks/, settings.local.json all present.",
                classes="help-text",
            )
            yield Checkbox("Apply CLAUDE.md project template", value=False, id="loc-template")
            yield Static(
                "Copies a starter CLAUDE.md from global/project-templates/ into the project root.\n"
                "Sets project conventions and stack hints that Claude reads at every session start (docs/rules-output-styles.md).\n"
                "Test: open a new Claude Code session in the project — the SessionStart hook detects CLAUDE.md and invokes @load-project.\n"
                "Review and customise the generated CLAUDE.md before committing it.",
                classes="help-text",
            )
            if self.template_options:
                yield Select(self.template_options, id="loc-tpl-select", prompt="Pick template…")
            yield Checkbox("Apply git repo-init template (hooks + .editorconfig + .gitattributes)", value=False, id="loc-git")
            yield Static(
                "Copies global/git/.editorconfig and .gitattributes to the project root, and hook scripts to .git/hooks/.\n"
                "Requires git init to have been run in the project first.\n"
                "[yellow]⚑ TODO (Unix): run chmod +x .git/hooks/* after apply — Windows copies do not preserve execute bit.[/yellow]\n"
                "Test: ls .git/hooks/ → hook files present. Open a commit to confirm hooks fire.",
                classes="help-text",
            )
            yield Static("")
            yield DataTable(id="loc-preview", show_cursor=False)
            yield Static("")
            with Horizontal():
                yield Button("Refresh preview", id="loc-refresh")
                yield Button("Apply (Ctrl+A)", id="loc-apply", variant="success")
                yield Button("Back (Esc)", id="loc-back")
            yield Static("", id="loc-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.add_columns("Action", "Path", "State")
        self._refresh()

    def _project(self) -> Path:
        return Path(self.query_one("#loc-path", Input).value).expanduser()

    def _selected(self) -> dict:
        return {
            "scaffold": self.query_one("#loc-scaffold", Checkbox).value,
            "template": self.query_one("#loc-template", Checkbox).value,
            "git": self.query_one("#loc-git", Checkbox).value,
        }

    def _template_path(self) -> Path | None:
        if not self.template_options:
            return None
        try:
            sel = self.query_one("#loc-tpl-select", Select)
        except Exception:
            return None
        if not isinstance(sel.value, str):
            return None
        return Path(sel.value)

    def _open_browser(self) -> None:
        raw = self.query_one("#loc-path", Input).value
        start = Path(raw).expanduser()
        if not start.is_dir():
            start = Path.cwd()
        def _cb(path: Path | None) -> None:
            if path is not None:
                self.query_one("#loc-path", Input).value = str(path)
                self._refresh()
        self.app.push_screen(FolderBrowserScreen(start), _cb)

    def _refresh(self) -> None:
        tbl = self.query_one("#loc-preview", DataTable)
        tbl.clear()
        project = self._project()
        sel = self._selected()
        tpl = self._template_path() if sel["template"] else None

        if not project.exists() or not project.is_dir():
            tbl.add_row("[red]Path not a directory[/red]", str(project), "[red]ERROR[/red]")
            return

        if sel["scaffold"]:
            for sub in [".claude", ".claude/skills", ".claude/hooks"]:
                p = project / sub
                state = "[dim]exists (kept)[/dim]" if p.exists() else "[green]NEW[/green]"
                tbl.add_row("scaffold", sub + "/", state)
            sl = project / ".claude" / "settings.local.json"
            tbl.add_row("scaffold", ".claude/settings.local.json", "[dim]exists (kept)[/dim]" if sl.exists() else "[green]NEW[/green]")

        if sel["template"]:
            if tpl:
                target = project / "CLAUDE.md"
                state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if target.exists() else "[green]NEW[/green]"
                tbl.add_row("template", f"CLAUDE.md  (from {tpl.stem})", state)
            else:
                tbl.add_row("template", "—", "[yellow]Pick a template above[/yellow]")

        if sel["git"]:
            git_src = GLOBAL_DIR / "git"
            git_dir = project / ".git"
            if not git_dir.exists():
                tbl.add_row("git_init", ".git/", "[yellow]will run git init[/yellow]")
            if not git_src.exists():
                tbl.add_row("git_init", "global/git/ in repo", "[red]MISSING[/red]")
            else:
                hooks_src = git_src / "hooks"
                if hooks_src.exists():
                    for f in sorted(hooks_src.iterdir()):
                        if f.is_file():
                            target = git_dir / "hooks" / f.name
                            state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if git_dir.exists() and target.exists() else "[green]NEW[/green]"
                            tbl.add_row("git_init", f".git/hooks/{f.name}", state)
                for f in sorted(git_src.iterdir()):
                    if f.is_file():
                        target = project / f.name
                        state = "[yellow]EXISTS — would OVERWRITE[/yellow]" if target.exists() else "[green]NEW[/green]"
                        tbl.add_row("git_init", f.name, state)

    def action_apply(self) -> None:
        project = self._project()
        if not project.is_dir():
            self.query_one("#loc-status", Static).update(f"[red]Not a directory:[/red] {project}")
            return
        sel = self._selected()
        msgs = []

        if sel["scaffold"]:
            (project / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
            (project / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
            sl = project / ".claude" / "settings.local.json"
            if not sl.exists():
                sl.write_text('{\n  "permissions": {\n    "allow": []\n  }\n}\n', encoding="utf-8")
            msgs.append(
                "[green]✓ Created .claude/ scaffold[/green]\n"
                "  Verify: ls .claude/ → skills/, hooks/, settings.local.json\n"
                "  [yellow]⚑ TODO: edit .claude/settings.local.json — add allow[] entries for this project's commands.[/yellow]"
            )

        if sel["template"]:
            tpl = self._template_path()
            if tpl:
                shutil.copy2(tpl, project / "CLAUDE.md")
                msgs.append(
                    f"[green]✓ Wrote CLAUDE.md from {tpl.stem}[/green]\n"
                    "  Verify: open a new Claude Code session here — SessionStart hook should invoke @load-project.\n"
                    "  Review CLAUDE.md and customise stack conventions before committing."
                )
            else:
                msgs.append("[yellow]Skipped template — none picked[/yellow]")

        if sel["git"]:
            git_src = GLOBAL_DIR / "git"
            git_dir = project / ".git"
            if not git_dir.exists():
                if not shutil.which("git"):
                    msgs.append("[red]✗ git not found on PATH — cannot run git init[/red]")
                else:
                    r = subprocess.run(["git", "init", str(project)], capture_output=True, text=True)
                    if r.returncode == 0:
                        msgs.append("[green]✓ git init[/green]")
                    else:
                        msgs.append(f"[red]✗ git init failed:[/red] {r.stderr.strip()}")
            if git_dir.exists() and git_src.exists():
                hooks_src = git_src / "hooks"
                if hooks_src.exists():
                    hd = git_dir / "hooks"
                    hd.mkdir(parents=True, exist_ok=True)
                    for f in hooks_src.iterdir():
                        if f.is_file():
                            shutil.copy2(f, hd / f.name)
                for f in git_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, project / f.name)
                msgs.append(
                    "[green]✓ Applied git repo-init template[/green]\n"
                    "  Verify: ls .git/hooks/ → hook scripts present.\n"
                    "  [yellow]⚑ TODO (Unix only): chmod +x .git/hooks/* — execute bit not preserved on Windows copy.[/yellow]"
                )
            elif not git_src.exists():
                msgs.append("[yellow]Skipped git_init — template missing in repo[/yellow]")

        self.query_one("#loc-status", Static).update("\n".join(msgs))
        self._refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "loc-back":
            self.app.pop_screen()
        elif bid == "loc-browse":
            self._open_browser()
        elif bid == "loc-refresh":
            self._refresh()
        elif bid == "loc-apply":
            self.action_apply()


class ToolsScreen(Screen):
    """Install / update optional companion tools."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ Tools ✦[/bold bright_magenta]\n"
                "[dim]Optional companion tools for Claude Code. "
                "Install runs in the terminal — UI returns when done.[/dim]",
                classes="panel",
            )
            for tool in TOOLS:
                with Vertical(classes="panel"):
                    yield Static(f"[bold cyan]{tool.name}[/bold cyan]")
                    yield Static(tool.description)
                    yield Static(
                        f"[dim]Home:[/dim] [blue]{tool.homepage}[/blue]\n"
                        f"[dim]GitHub:[/dim] [blue]{tool.repo_url}[/blue]"
                    )
                    yield Static("", id=f"tool-status-{tool.key}")
                    with Horizontal():
                        yield Button(
                            "Install / Update",
                            id=f"tool-install-{tool.key}",
                            variant="success",
                        )
            yield Static("", id="tools-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        for tool in TOOLS:
            try:
                state = tool.status()
            except Exception as e:
                state = f"status check failed: {e}"
            color = "green" if state.startswith("installed") else "yellow"
            self.query_one(f"#tool-status-{tool.key}", Static).update(
                f"[bold]Status:[/bold] [{color}]{state}[/{color}]"
            )

    def action_refresh(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("tool-install-"):
            return
        key = bid.removeprefix("tool-install-")
        tool = next((t for t in TOOLS if t.key == key), None)
        if not tool:
            return
        self.query_one("#tools-status", Static).update(
            f"[yellow]Installing {tool.name}…[/yellow]  "
            f"[dim](terminal output below — UI resumes when installer exits)[/dim]"
        )
        with self.app.suspend():
            try:
                ok, msg = tool.install()
            except Exception as e:
                ok, msg = False, f"Unhandled error: {e}"
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        self.query_one("#tools-status", Static).update(f"{mark} {tool.name}: {msg}")
        self._refresh()


# ─── App ───────────────────────────────────────────────────────────────────────

class HextravagantApp(App):
    """HEXTRAVAGANT — Claude Code Setup Wizard."""

    CSS = """
    Screen { background: $background; }

    .centered { content-align: center middle; }

    .panel {
        padding: 1 2;
        margin: 1 2;
        background: $panel;
        border: round $accent;
    }

    #banner {
        height: auto;
        padding: 1 2;
        content-align: center middle;
    }

    #env-summary, #update-summary, #doctor-summary, #mcp-target {
        padding: 1 2;
        margin: 0 2;
        background: $boost;
        border: round $primary;
    }

    /* Every Horizontal needs explicit height or buttons collapse. */
    Horizontal {
        height: auto;
        align-vertical: middle;
        padding: 0 1;
        margin: 1 2;
    }

    #home-bottom {
        height: 5;
        align-vertical: middle;
        padding: 0 2;
        margin: 0;
    }
    .home-spacer { width: 1fr; }

    .home-section {
        border: round $accent;
        margin: 1 2;
        padding: 0 1 1 1;
        height: auto;
    }
    .home-section-title {
        color: $accent;
        padding: 0 1;
        height: 2;
        content-align: left middle;
    }

    .ops-row {
        height: 5;
        align: center middle;
        margin: 0 1;
        padding: 0;
    }
    .ops-row Button { width: 1fr; }

    #home-nav, #ops-nav {
        height: 5;
        align: center middle;
    }

    Button {
        margin: 0 1;
        min-width: 18;
        height: 3;
    }

    DataTable { height: auto; max-height: 25; margin: 0 2; }

    Input { margin: 0 1; height: 3; }

    /* Compact env-var rows: name | icon | input on one line */
    .env-row {
        height: 3;
        margin: 0 2;
        padding: 0;
        align-vertical: middle;
    }
    .env-name {
        width: 32;
        padding: 1 1 0 1;
        content-align: left middle;
    }
    .env-icon {
        width: 4;
        padding: 1 0 0 0;
        content-align: center middle;
    }
    .env-value { width: 1fr; }
    .env-browse { min-width: 10; width: 10; margin: 0; }

    Checkbox { margin: 0 2; height: auto; }

    .help-text {
        color: $text-muted;
        padding: 0 0 1 4;
        margin: 0 2;
        height: auto;
    }

    OptionList { max-height: 20; margin: 0 2; }

    RadioSet { margin: 0 1; height: auto; }

    Label { padding: 1 1 0 1; }

    MarkdownViewer { background: $background; }

    Footer { background: $primary-darken-1; }

    /* Folder browser modal */
    FolderBrowserScreen {
        align: center middle;
        background: $background 70%;
    }
    #browser-dialog {
        background: $panel;
        border: double $accent;
        padding: 1 2;
        width: 72;
        height: 28;
    }
    #browser-path {
        height: 3;
        padding: 0 1;
        background: $boost;
        border: round $primary;
        margin: 0 0 1 0;
        content-align: left middle;
    }
    #browser-list {
        height: 1fr;
        margin: 0;
    }
    #browser-actions {
        height: 3;
        margin: 1 0 0 0;
        padding: 0;
        align-horizontal: center;
    }
    #browser-actions Button { min-width: 16; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("left", "focus_previous", show=False),
        Binding("right", "focus_next", show=False),
    ]

    COMMANDS = {AppCommandsProvider}

    def on_mount(self) -> None:
        self.title = "HEXTRAVAGANT"
        self.sub_title = "Claude Code Setup Wizard"
        self.push_screen(HomeScreen())


def main() -> None:
    HextravagantApp().run()


if __name__ == "__main__":
    main()
