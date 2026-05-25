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

IS_FROZEN = getattr(sys, "frozen", False)


def _missing_textual() -> None:
    msg = (
        "This wizard requires the `textual` package.\n"
        "Install with one of:\n"
        "  python -m pip install textual\n"
        "  uv pip install textual\n"
    )
    if IS_FROZEN:
        msg += "\nIf you see this from a frozen build, it was built incorrectly - rebuild with `python setup/build/build_exe.py`."
    sys.stderr.write(msg + "\n")
    sys.exit(2)


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
    if IS_FROZEN:
        _missing_textual()
    print("First run — installing textual...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "textual"])
    except Exception:
        _missing_textual()
    import importlib
    import site

    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()
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


# ─── Paths ─────────────────────────────────────────────────────────────────────
#
# Two layouts are supported:
#   - Source: this file lives at <repo>/setup/settings-configurator-ui.py, with
#     siblings <repo>/global/ and <repo>/setup/env/.
#   - Frozen exe (PyInstaller --onefile): bundled resources are extracted into
#     sys._MEIPASS; the exe itself sits anywhere on disk and is not a git repo.

def _resource_root() -> Path:
    """Directory containing bundled `global/` and `env/` trees."""
    if IS_FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent  # repo root


def _detect_repo_dir() -> Path | None:
    """Return the repo working tree if we have one; else None (frozen + no repo)."""
    if IS_FROZEN:
        candidate = Path(sys.executable).resolve().parent
        for parent in (candidate, *candidate.parents):
            if (parent / ".git").exists():
                return parent
        return None
    return Path(__file__).resolve().parent.parent


SCRIPT_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = _resource_root()
REPO_DIR: Path | None = _detect_repo_dir()
GLOBAL_DIR = RESOURCE_ROOT / "global"
ENV_DIR = RESOURCE_ROOT / "setup" / "env" if IS_FROZEN else SCRIPT_DIR / "env"
ENV_FILE = ENV_DIR / "setup.env.example.json"
MCP_TEMPLATES_FILE = RESOURCE_ROOT / "setup" / "mcp-templates.json" if IS_FROZEN else SCRIPT_DIR / "mcp-templates.json"
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


_PLUGIN_ONLY_FILES = frozenset({".mcp.json", "hooks/hooks.json"})


def _is_plugin_only(rel_path: Path) -> bool:
    """Skip files that Claude Code loads only when `global/` is installed as a plugin."""
    posix = rel_path.as_posix()
    if posix in _PLUGIN_ONLY_FILES:
        return True
    parts = rel_path.parts
    return bool(parts) and parts[0] == ".claude-plugin"


def translate_for_os(filename: str, text: str) -> str:
    """Rewrite OS-specific tokens in a config file before it is deployed.

    The repo's settings.json is authored Windows-canonical ($USERPROFILE). On
    POSIX shells that variable is empty, so hook/statusline command paths break.
    Swap it for $HOME, which resolves correctly on Linux, macOS, and git-bash.
    """
    if filename != "settings.json" or platform.system() == "Windows":
        return text
    return text.replace("$USERPROFILE", "$HOME")


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
            if _os_should_skip(self.src_path.name) or _is_plugin_only(Path(self.src)):
                return []
            return [(self.src_path, Path(self.src).name)]
        out: list[tuple[Path, Path]] = []
        iterator = self.src_path.rglob("*") if self.recursive else self.src_path.glob(self.glob)
        for f in iterator:
            if not f.is_file() or _os_should_skip(f.name):
                continue
            rel = f.relative_to(self.src_path)
            if _is_plugin_only(Path(self.src) / rel):
                continue
            out.append((f, rel))
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
    if REPO_DIR is None:
        return {"status": "no_repo"}
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
    if REPO_DIR is None:
        return False, "no git checkout available (running from a frozen build)"
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


def _effective_settings_text(src: Path) -> str:
    """Return settings.json content stripped of dead `mcpServers` / `mcpServersDisabled`,
    with OS-specific tokens translated for the deploy target.

    Why: Claude Code does NOT read MCP server definitions from settings.json — those
    blocks are silently ignored. The canonical interface is `claude mcp add` which
    writes to `~/.claude.json`. Stripping these fields keeps the deployed file honest
    so future readers don't think the config is active. See global/skills/add-mcp.md.
    Additionally, the repo authors paths with $USERPROFILE (Windows) — on POSIX
    shells we swap to $HOME via translate_for_os so hook commands resolve.
    """
    data = json.loads(src.read_text(encoding="utf-8"))
    data.pop("mcpServers", None)
    data.pop("mcpServersDisabled", None)
    text = json.dumps(data, indent=2) + "\n"
    return translate_for_os(src.name, text)


def _is_settings_json(src_file: Path) -> bool:
    return src_file.name == "settings.json" and src_file.parent == GLOBAL_DIR


# ─── MCP server helpers (claude mcp add/list/remove) ───────────────────────────
# Claude Code stores MCP servers in ~/.claude.json (NOT settings.json). The CLI
# `claude mcp add/remove/list` is the only supported interface. See add-mcp skill.

_WINDOWS_CMD_WRAPPED = frozenset({"pnpm", "npx", "bunx"})


def _load_mcp_templates() -> dict:
    if not MCP_TEMPLATES_FILE.exists():
        return {}
    try:
        return json.loads(MCP_TEMPLATES_FILE.read_text(encoding="utf-8")).get("templates", {})
    except Exception:
        return {}


def _claude_dot_json() -> dict:
    p = Path.home() / ".claude.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run_claude_cli(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a `claude` CLI command with MSYS path conversion disabled (Git Bash safety)."""
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    try:
        r = subprocess.run(["claude", *args], capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "claude CLI not found in PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def _claude_mcp_list() -> list[dict]:
    """Parse `claude mcp list` output. Returns [{name, command_line, connected, status_text}].

    Line format: `<name>: <command> - <status>` — names may contain `:` (plugin:foo:bar),
    so we split on `: ` (colon + space) to find the name/command boundary.
    """
    rc, out, _ = _run_claude_cli(["mcp", "list"], timeout=60)
    if rc != 0:
        return []
    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line or " - " not in line or ": " not in line:
            continue
        head, _, status = line.rpartition(" - ")
        name, _, cmdline = head.partition(": ")
        results.append({
            "name": name.strip(),
            "command_line": cmdline.strip(),
            "connected": "Connected" in status,
            "status_text": status.strip(),
        })
    return results


def enumerate_mcp_servers() -> dict[str, dict]:
    """Aggregate every known MCP server across scopes into one view.

    Returns: { name: { 'scopes': [str], 'active': bool, 'command_line': str,
                       'env_required': [str], 'is_plugin': bool, 'definitions': {scope: cfg} } }

    Scopes: 'plugin' | 'user' | 'local' | 'project' | 'template'
    'template' means defined in mcp-templates.json but not yet registered.
    """
    aggregated: dict[str, dict] = {}

    def _ensure(name: str) -> dict:
        return aggregated.setdefault(name, {
            "scopes": [], "active": False, "command_line": "",
            "env_required": [], "is_plugin": name.startswith("plugin:"),
            "definitions": {},
        })

    cj = _claude_dot_json()
    for name, cfg in (cj.get("mcpServers") or {}).items():
        e = _ensure(name)
        e["scopes"].append("user")
        e["definitions"]["user"] = cfg

    for proj_path, proj_data in (cj.get("projects") or {}).items():
        for name, cfg in (proj_data.get("mcpServers") or {}).items():
            e = _ensure(name)
            e["scopes"].append("local")
            e["definitions"].setdefault("local", []).append({"path": proj_path, "def": cfg})

    cwd_mcp = Path.cwd() / ".mcp.json"
    if cwd_mcp.exists():
        try:
            d = json.loads(cwd_mcp.read_text(encoding="utf-8"))
            entries = d.get("mcpServers") or d
            for name, cfg in entries.items():
                e = _ensure(name)
                e["scopes"].append("project")
                e["definitions"]["project"] = cfg
        except Exception:
            pass

    for entry in _claude_mcp_list():
        name = entry["name"]
        e = _ensure(name)
        e["active"] = entry["connected"]
        e["command_line"] = entry["command_line"]
        if e["is_plugin"] and "plugin" not in e["scopes"]:
            e["scopes"].insert(0, "plugin")

    for name, tmpl in _load_mcp_templates().items():
        e = _ensure(name)
        e["env_required"] = list(tmpl.get("env_required") or [])
        e["definitions"]["template"] = tmpl
        if not e["scopes"]:
            e["scopes"].append("template")
        if not e["command_line"]:
            e["command_line"] = " ".join([tmpl.get("command", "")] + list(tmpl.get("args") or []))

    return aggregated


def claude_mcp_add_from_template(name: str, template: dict) -> tuple[bool, str]:
    """Register a server via `claude mcp add -s user`, wrapping pnpm/npx/bunx on Windows."""
    cmd = template.get("command", "")
    args = list(template.get("args") or [])
    transport = template.get("transport", "stdio")

    if platform.system() == "Windows" and cmd in _WINDOWS_CMD_WRAPPED:
        joined = " ".join([cmd] + args)
        subcmd, subargs = "cmd", ["/s", "/c", joined]
    else:
        subcmd, subargs = cmd, args

    full = ["mcp", "add", "-s", "user"]
    if transport != "stdio":
        full += ["--transport", transport]
    for var in template.get("env_required") or []:
        val = os.environ.get(var, "")
        if not val:
            return False, f"Missing env var: {var} (set it in your shell first)"
        full += ["-e", f"{var}={val}"]
    full += [name, "--", subcmd, *subargs]

    rc, out, err = _run_claude_cli(full)
    if rc == 0:
        return True, (out or "Added").strip().splitlines()[0]
    return False, (err or out or "unknown error").strip()


def claude_mcp_remove(name: str, scope: str) -> tuple[bool, str]:
    rc, out, err = _run_claude_cli(["mcp", "remove", "-s", scope, name])
    if rc == 0:
        return True, (out or "Removed").strip().splitlines()[0]
    return False, (err or out or "unknown error").strip()


def diff_component(comp: Component) -> list[FileStatus]:
    out: list[FileStatus] = []
    for src_file, rel in comp.list_files():
        dst_file = comp.dst_path / rel if comp.type == "dir" else comp.dst_path
        if not dst_file.exists():
            out.append(FileStatus(rel, src_file, dst_file, "NEW"))
        elif _is_settings_json(src_file):
            same = dst_file.read_text(encoding="utf-8") == _effective_settings_text(src_file)
            out.append(FileStatus(rel, src_file, dst_file, "UNCHANGED" if same else "CHANGED"))
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
            if _is_settings_json(st.src):
                st.dst.write_text(_effective_settings_text(st.src), encoding="utf-8")
                shutil.copystat(st.src, st.dst)
            else:
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


# ─── uv (Astral Python tool manager) ───────────────────────────────────────────

def uv_install() -> tuple[bool, str]:
    """Install `uv` using the OS-native installer. Returns (ok, message)."""
    sysname = platform.system()
    if sysname == "Windows":
        if shutil.which("winget"):
            r = subprocess.run(
                ["winget", "install", "--id", "astral-sh.uv", "-e", "--silent",
                 "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True,
            )
            return r.returncode == 0, "winget install astral-sh.uv"
        return False, "Install uv manually from https://docs.astral.sh/uv/"
    if sysname == "Darwin":
        if shutil.which("brew"):
            r = subprocess.run(["brew", "install", "uv"], capture_output=True, text=True)
            return r.returncode == 0, "brew install uv"
        return False, "Install Homebrew first or see https://docs.astral.sh/uv/"
    if sysname == "Linux":
        r = subprocess.run(
            ["bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
            capture_output=True, text=True,
        )
        return r.returncode == 0, "astral uv installer (curl)"
    return False, f"Unsupported platform: {sysname}"


# ─── Specify CLI (GitHub Spec Kit) ─────────────────────────────────────────────

SPECIFY_SOURCE = "git+https://github.com/github/spec-kit.git"


def specify_status() -> str:
    if not shutil.which("specify"):
        return "not installed"
    r = subprocess.run(["specify", "--version"], capture_output=True, text=True)
    v = (r.stdout or r.stderr or "").strip().splitlines()[0] if r.returncode == 0 else ""
    return f"installed {v}" if v else "installed"


def specify_install() -> tuple[bool, str]:
    """Install or upgrade `specify` via `uv tool install`. Auto-installs uv if missing."""
    if not shutil.which("uv"):
        ok, msg = uv_install()
        if not ok:
            return False, f"uv missing — could not auto-install ({msg})"
        if not shutil.which("uv"):
            return False, "uv installed but not on PATH yet — open a new terminal and re-run"

    if shutil.which("specify"):
        r = subprocess.run(
            ["uv", "tool", "upgrade", "specify-cli"],
            capture_output=True, text=True,
        )
        out = (r.stdout or r.stderr or "").strip()
        return r.returncode == 0, f"uv tool upgrade specify-cli — {out or 'ok'}"

    r = subprocess.run(
        ["uv", "tool", "install", "specify-cli", "--from", SPECIFY_SOURCE],
        capture_output=True, text=True,
    )
    out = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, out or "uv tool install specify-cli"


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


def gh_fetch_token() -> tuple[bool, str, str]:
    """Get GitHub token via gh CLI. Returns (success, token, message).

    Uses `gh auth token` as the primary check — if it returns a token the user
    is authenticated regardless of what `gh auth status` reports (status can
    return non-zero even when a valid token exists due to scope/keychain quirks).
    """
    if not shutil.which("gh"):
        return False, "", "gh CLI not found — install GitHub CLI first"
    token_r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    t = token_r.stdout.strip()
    if token_r.returncode == 0 and t:
        return True, t, "Token fetched from gh CLI"
    return False, "", "Not logged in — click Login with GitHub, authenticate, then click Fetch via gh."


# GitHub CLI's public client_id (visible in gh source: internal/authflow/flow.go).
# Device flow does not require a client secret. Override via env var if you've
# registered your own OAuth App.
_GITHUB_CLIENT_ID = os.environ.get("PROMPT_LIB_GH_CLIENT_ID", "178c6fc778ccc68e1d6a")


def gh_device_init(scopes: list[str]) -> dict | None:
    """Start OAuth Device Authorization Grant. Returns response dict or None on failure."""
    import urllib.parse, urllib.request
    body = urllib.parse.urlencode({
        "client_id": _GITHUB_CLIENT_ID,
        "scope": " ".join(scopes),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://github.com/login/device/code",
        data=body,
        headers={"Accept": "application/json", "User-Agent": "prompt-lib-wizard"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def gh_device_poll(
    device_code: str,
    interval: int,
    deadline: float,
    cancelled: Callable[[], bool],
) -> tuple[bool, str, str]:
    """Poll for the access token until success, denial, expiry, cancel, or deadline.

    Returns (ok, token, message). `cancelled()` is checked between sleeps so the UI can abort.
    """
    import time, urllib.parse, urllib.request
    cur_interval = max(1, interval)
    while time.monotonic() < deadline:
        if cancelled():
            return False, "", "cancelled"
        time.sleep(cur_interval)
        if cancelled():
            return False, "", "cancelled"
        body = urllib.parse.urlencode({
            "client_id": _GITHUB_CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=body,
            headers={"Accept": "application/json", "User-Agent": "prompt-lib-wizard"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return False, "", f"network error: {e}"
        if "access_token" in data:
            return True, data["access_token"], "authorized"
        err = data.get("error", "")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            cur_interval += 5
            continue
        if err == "expired_token":
            return False, "", "code expired — try again"
        if err == "access_denied":
            return False, "", "access denied"
        return False, "", f"oauth error: {err or 'unknown'}"
    return False, "", "timed out"


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
        key="specify-cli",
        name="Specify CLI (GitHub Spec Kit)",
        description=(
            "Spec-driven development CLI from GitHub. Installs via `uv tool install` "
            "from the upstream git repo (will auto-install `uv` if missing). Provides "
            "`specify init` for scaffolding .specify/ workflows in any project."
        ),
        homepage="https://github.com/github/spec-kit",
        repo_url="https://github.com/github/spec-kit",
        install=specify_install,
        status=specify_status,
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
        candidates = [GLOBAL_DIR / "README.md", RESOURCE_ROOT / "README.md", SCRIPT_DIR / "README.md"]
        if REPO_DIR is not None:
            candidates.insert(0, REPO_DIR / "README.md")
        readme = next((p for p in candidates if p.exists()), None)
        if readme:
            yield MarkdownViewer(readme.read_text(encoding="utf-8"), show_table_of_contents=True)
        else:
            yield Static("[yellow]No README.md found.[/yellow]")
        yield Footer()


_PATH_KEYS: frozenset[str] = frozenset({"PROJECTS_PATH", "TEMP_PATH"})
_GH_TOKEN_KEYS: frozenset[str] = frozenset({"GITHUB_PERSONAL_ACCESS_TOKEN"})


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
                    if key in _GH_TOKEN_KEYS:
                        yield Button("Fetch via gh", id=f"gh-fetch-{key}", classes="env-browse")
                        b = Button("Login with GitHub", id=f"gh-login-{key}", classes="env-browse")
                        b.display = False
                        yield b
                    yield Input(value=str(val), id=f"in-{key}", placeholder="(empty)", classes="env-value")
                desc = ENV_DESCRIPTIONS.get(key)
                if desc:
                    yield Static(desc, classes="help-text")
                if key in _GH_TOKEN_KEYS:
                    yield Static("", id=f"gh-status-{key}", classes="help-text")
            yield Static("")
            with Horizontal(id="env-actions"):
                yield Button("Apply (Ctrl+A)", id="env-apply", variant="success")
                yield Button("Back (Esc)", id="env-back")
            yield Static("", id="env-status")
        yield Footer()

    def on_mount(self) -> None:
        for key in _GH_TOKEN_KEYS:
            if key in self.data:
                self.run_worker(
                    lambda k=key: self._check_gh_auth(k),
                    thread=True, exclusive=False,
                )

    def _check_gh_auth(self, key: str) -> None:
        logged_in = False
        if not shutil.which("gh"):
            label = "[dim]gh CLI not installed — cannot fetch token[/dim]"
        else:
            # Use `gh auth token` as the source of truth — `gh auth status` can return
            # non-zero even when a valid token exists (scope/keychain quirks on Windows).
            token_r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
            if token_r.returncode == 0 and token_r.stdout.strip():
                logged_in = True
                # Also pull account info from auth status for display (best-effort)
                status_r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
                info = (status_r.stdout or status_r.stderr or "").strip().splitlines()[0] if (status_r.stdout or status_r.stderr).strip() else ""
                label = f"[green]✓ gh: logged in[/green] [dim]{info}[/dim]"
            else:
                label = "[yellow]⚠ gh: not logged in — click Login with GitHub to authenticate[/yellow]"

        def _apply() -> None:
            try:
                self.query_one(f"#gh-status-{key}", Static).update(label)
                self.query_one(f"#gh-login-{key}", Button).display = not logged_in
            except Exception:
                pass

        self.app.call_from_thread(_apply)

    def _on_gh_token(self, key: str, token: str | None) -> None:
        """Callback when GhDeviceFlowScreen dismisses. Populates input on success."""
        status_widget = self.query_one("#env-status", Static)
        if not token:
            status_widget.update("[yellow]Login cancelled[/yellow]")
            return
        self.query_one(f"#in-{key}", Input).value = token
        try:
            self.query_one(f"#gh-status-{key}", Static).update("[green]✓ gh: logged in (via wizard)[/green]")
            self.query_one(f"#gh-login-{key}", Button).display = False
        except Exception:
            pass
        status_widget.update("[green]✓ Logged in — Apply (Ctrl+A) to persist[/green]")

    def _gather(self) -> dict[str, str]:
        out = {}
        for key in self.data.keys():
            inp = self.query_one(f"#in-{key}", Input)
            out[key] = inp.value
        return out

    def _fetch_gh_token(self, key: str) -> None:
        status_widget = self.query_one("#env-status", Static)
        status_widget.update("[dim]Contacting gh CLI…[/dim]")

        def _do() -> None:
            ok, token, msg = gh_fetch_token()

            def _apply() -> None:
                if ok:
                    self.query_one(f"#in-{key}", Input).value = token
                    status_widget.update(f"[green]✓ {msg}[/green]")
                else:
                    status_widget.update(f"[yellow]{msg}[/yellow]")

            self.app.call_from_thread(_apply)

        self.run_worker(_do, thread=True, exclusive=False)

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
        elif bid.startswith("gh-fetch-"):
            self._fetch_gh_token(bid.removeprefix("gh-fetch-"))
        elif bid.startswith("gh-login-"):
            key = bid.removeprefix("gh-login-")
            self.query_one("#env-status", Static).update("[dim]Starting GitHub device flow…[/dim]")

            def _start(k=key) -> None:
                device = gh_device_init(["repo", "read:org"])

                def _push() -> None:
                    if device is None:
                        self.query_one("#env-status", Static).update(
                            "[red]Could not reach github.com — check your connection[/red]"
                        )
                        return
                    self.app.push_screen(
                        GhDeviceFlowScreen(device),
                        lambda token: self._on_gh_token(k, token),
                    )

                self.app.call_from_thread(_push)

            self.run_worker(_start, thread=True, exclusive=False)


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
    """Unified MCP view across all scopes (plugin/user/local/project/template).

    Live status from `claude mcp list`. Toggle enables/disables via `claude mcp add/remove`.
    Settings.json `mcpServers` is dead — Claude Code does not read it. See add-mcp skill.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("space", "toggle", "Toggle"),
    ]

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with VerticalScroll():
            yield Static(
                "[bold bright_magenta]✦ MCP servers ✦[/bold bright_magenta]\n"
                "[dim]Live status from `claude mcp list`. Toggle = `claude mcp add` (from template) or `claude mcp remove`.[/dim]\n"
                "[dim]Scopes: plugin (marketplace) · user (~/.claude.json, all projects) · local (this project only) · "
                "project (.mcp.json) · template (defined here, not registered).[/dim]",
                classes="panel",
            )
            yield DataTable(id="mcp-table", show_cursor=True, cursor_type="row", zebra_stripes=True)
            with Horizontal():
                yield Button("Toggle (Space)", id="mcp-toggle", variant="primary")
                yield Button("Refresh (Ctrl+R)", id="mcp-refresh")
                yield Button("Back (Esc)", id="mcp-back")
            yield Static("", id="mcp-status", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.add_columns("Name", "Scope(s)", "Status", "Env", "Command")
        self._refresh()

    def _refresh(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        tbl.clear()
        try:
            aggregated = enumerate_mcp_servers()
        except Exception as e:
            self.query_one("#mcp-status", Static).update(f"[red]Error enumerating: {e}[/red]")
            return
        for name in sorted(aggregated.keys()):
            info = aggregated[name]
            scopes_disp = _render_scopes(info["scopes"])
            if info["is_plugin"]:
                status_disp = "[green]✓ plugin[/green]" if info["active"] else "[red]✗ plugin[/red]"
            elif info["active"]:
                status_disp = "[green]✓ connected[/green]"
            elif info["scopes"] == ["template"]:
                status_disp = "[dim]○ available[/dim]"
            else:
                status_disp = "[yellow]✗ registered, not connected[/yellow]"
            env_disp = "—"
            if info["env_required"]:
                env_disp = " ".join(
                    f"{k}[{'green' if os.environ.get(k) else 'red'}]{'✓' if os.environ.get(k) else '✗'}[/]"
                    for k in info["env_required"]
                )
            cmd_disp = (info["command_line"] or "—")[:80]
            tbl.add_row(name, scopes_disp, status_disp, env_disp, cmd_disp, key=name)
        self.query_one("#mcp-status", Static).update(
            f"[dim]{tbl.row_count} servers shown. Space toggles. Plugin servers managed via /plugin.[/dim]"
        )

    def action_refresh(self) -> None:
        self._refresh()

    def action_toggle(self) -> None:
        self._toggle_selected()

    def _toggle_selected(self) -> None:
        tbl = self.query_one("#mcp-table", DataTable)
        status_label = self.query_one("#mcp-status", Static)
        if tbl.cursor_row is None or tbl.row_count == 0:
            return
        row_key = tbl.coordinate_to_cell_key((tbl.cursor_row, 0)).row_key.value
        if not row_key:
            return
        name = row_key
        info = enumerate_mcp_servers().get(name)
        if not info:
            status_label.update(f"[red]Not found: {name}[/red]")
            return
        if info["is_plugin"]:
            status_label.update("[yellow]Plugin servers are managed via /plugin in Claude Code, not here.[/yellow]")
            return
        active_scopes = [s for s in info["scopes"] if s in ("user", "local")]
        if active_scopes:
            scope = active_scopes[0]
            ok, msg = claude_mcp_remove(name, scope)
            status_label.update(
                f"[{'green' if ok else 'red'}]{'✓ removed' if ok else '✗ remove failed'} {name} ({scope}): {msg}[/]"
            )
        else:
            tmpl = info["definitions"].get("template")
            if not tmpl:
                status_label.update(f"[red]No template for {name} — add manually via `claude mcp add`[/red]")
                return
            ok, msg = claude_mcp_add_from_template(name, tmpl)
            status_label.update(
                f"[{'green' if ok else 'red'}]{'✓ added' if ok else '✗ add failed'} {name} (user): {msg}[/]"
            )
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "mcp-back":
            self.app.pop_screen()
        elif bid == "mcp-refresh":
            self._refresh()
        elif bid == "mcp-toggle":
            self._toggle_selected()


_SCOPE_COLOURS = {
    "plugin":   "magenta",
    "user":     "cyan",
    "local":    "blue",
    "project":  "yellow",
    "template": "dim",
}


def _render_scopes(scopes: list[str]) -> str:
    if not scopes:
        return "—"
    out = []
    for s in scopes:
        c = _SCOPE_COLOURS.get(s, "white")
        out.append(f"[{c}]{s}[/{c}]")
    return " ".join(out)


class GhDeviceFlowScreen(ModalScreen):
    """Modal that drives a GitHub OAuth Device Authorization flow inside the wizard.

    Dismisses with the access token on success, or None on cancel/error/timeout.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    GhDeviceFlowScreen { align: center middle; }
    #gh-dialog {
        width: 70; height: auto; padding: 1 2; border: round #FF55A5;
        background: $panel;
    }
    #gh-code {
        content-align: center middle; padding: 1 0;
        text-style: bold; color: #FFB6C1;
    }
    #gh-url, #gh-instructions, #gh-status-line { content-align: center middle; padding: 0 0; }
    #gh-actions { align: center middle; padding-top: 1; height: 3; }
    #gh-actions Button { margin: 0 1; }
    """

    def __init__(self, device: dict) -> None:
        super().__init__()
        self._device = device
        self._cancelled = False

    def compose(self) -> ComposeResult:
        with Container(id="gh-dialog"):
            yield Static("[bold bright_magenta]Login with GitHub[/bold bright_magenta]", id="gh-instructions")
            yield Static("\nEnter this code in your browser:\n", id="gh-instructions")
            code = self._device.get("user_code", "????-????")
            yield Static(f"╔══════════════╗\n║  [bold]{code}[/bold]  ║\n╚══════════════╝", id="gh-code")
            url = self._device.get("verification_uri", "https://github.com/login/device")
            yield Static(f"\n[dim]Browser opened to[/dim] [cyan]{url}[/cyan]", id="gh-url")
            yield Static("\n[dim]Waiting for authorization…[/dim]", id="gh-status-line")
            with Horizontal(id="gh-actions"):
                yield Button("Cancel (Esc)", id="gh-cancel", variant="error")

    def on_mount(self) -> None:
        import webbrowser
        try:
            webbrowser.open(self._device.get("verification_uri", "https://github.com/login/device"))
        except Exception:
            pass
        self.run_worker(self._poll, thread=True, exclusive=True)

    def _poll(self) -> None:
        import time
        interval = int(self._device.get("interval", 5))
        expires_in = int(self._device.get("expires_in", 900))
        deadline = time.monotonic() + expires_in
        device_code = self._device.get("device_code", "")
        start = time.monotonic()

        def _tick() -> None:
            elapsed = int(time.monotonic() - start)
            try:
                self.query_one("#gh-status-line", Static).update(
                    f"[dim]Waiting for authorization… {elapsed}s[/dim]"
                )
            except Exception:
                pass

        self.app.call_from_thread(_tick)

        ok, token, msg = gh_device_poll(
            device_code, interval, deadline, lambda: self._cancelled,
        )

        def _finish() -> None:
            if ok:
                self.dismiss(token)
            else:
                try:
                    self.query_one("#gh-status-line", Static).update(f"[red]✗ {msg}[/red]")
                except Exception:
                    pass
                self.dismiss(None)

        self.app.call_from_thread(_finish)

    def action_cancel(self) -> None:
        self._cancelled = True
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gh-cancel":
            self.action_cancel()


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
            yield Checkbox("Initialize Spec Kit (specify init --here --integration claude)", value=False, id="loc-speckit")
            yield Static(
                "Runs `specify init --here --integration claude` in the project to scaffold the Spec Kit workflow "
                "(.specify/, slash commands like /speckit-specify, /speckit-plan, /speckit-tasks).\n"
                "Requires the `specify` CLI — install it from the Tools screen (or run `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`).\n"
                "If the target directory already contains .specify/, this passes `--force` to merge.\n"
                "Test: ls .specify/ → templates, scripts, memory all present. Open Claude Code → /speckit-specify should be listed.",
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
            "speckit": self.query_one("#loc-speckit", Checkbox).value,
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

        if sel["speckit"]:
            if not shutil.which("specify"):
                tbl.add_row("speckit", "specify CLI", "[red]not installed — see Tools screen[/red]")
            else:
                specify_dir = project / ".specify"
                if specify_dir.exists():
                    tbl.add_row("speckit", ".specify/", "[yellow]EXISTS — will run with --force[/yellow]")
                else:
                    tbl.add_row("speckit", ".specify/", "[green]NEW (specify init --here --integration claude)[/green]")

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

        if sel["speckit"]:
            if not shutil.which("specify"):
                msgs.append(
                    "[red]✗ specify CLI not on PATH[/red] — install it from the Tools screen "
                    "(or `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`), "
                    "then re-run."
                )
            else:
                cmd = [
                    "specify", "init", "--here",
                    "--integration", "claude",
                    "--ignore-agent-tools",
                ]
                if (project / ".specify").exists():
                    cmd.append("--force")
                with self.app.suspend():
                    r = subprocess.run(cmd, cwd=str(project))
                if r.returncode == 0:
                    msgs.append(
                        f"[green]✓ Spec Kit initialized[/green]  [dim]({' '.join(cmd)})[/dim]\n"
                        "  Verify: ls .specify/ → templates/, scripts/, memory/ present.\n"
                        "  In Claude Code, /speckit-specify, /speckit-plan, /speckit-tasks should be available."
                    )
                else:
                    msgs.append(f"[red]✗ specify init failed (exit {r.returncode})[/red]")

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
