# -*- coding: utf-8 -*-
"""Tool + installer registries — single anchor for every installer module.

`cabal.tools` imports every `cabal.installers.*` module by name. This serves
two purposes:

1. PyInstaller's static analyzer follows the import edges, so every installer
   is bundled into the frozen exe even though screens reach for installers
   lazily via `_installer_for(key)`.
2. Maintainers have one place to add a new installer — drop a file under
   `cabal/installers/`, then append one row to `ENV_INSTALLERS` and (for
   featured tools) one entry to `TOOLS`.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Callable

from cabal.env_detect import (
    _kubectl_version,
    _probe_version,
    _has_rider,
    _has_visual_studio,
)
from cabal.installers.ai_clis import (
    antigravity_install,
    codex_install,
    copilot_install,
    gemini_install,
    grok_install,
    ollama_install,
    opencode_install,
    vllm_install,
)
from cabal.installers.cdt import cdt_install, cdt_status
from cabal.installers.claude_cli import claude_cli_install, claude_cli_status
from cabal.installers.cloud import (
    aws_install,
    az_install,
    gcloud_install,
    terraform_install,
)
from cabal.installers.databases import (
    neon_install,
    postgres_install,
    sqlcmd_install,
    supabase_install,
)
from cabal.installers.containers import (
    docker_install,
    kubectl_install,
    openshift_install,
    podman_install,
)
from cabal.installers.editors import cursor_install, vscode_install, windsurf_install
from cabal.installers.gh import gh_install, gh_status
from cabal.installers.headroom import headroom_install, headroom_status
from cabal.installers.mcp_bus import mcp_bus_install, mcp_bus_status
from cabal.installers.runtimes import (
    bun_install,
    dotnet_install,
    node_install,
    npm_install,
    pnpm_install,
    python_install,
)
from cabal.installers.skills import skills_install, skills_status
from cabal.installers.specify import specify_install, specify_status
from cabal.installers.vcs import git_install
from cabal.installers.vercel_plugin import vercel_plugin_install, vercel_plugin_status

# Maps env keys → winget package IDs (mirrors the install fns above). Used to spot
# upgrade availability via `winget upgrade`. macOS/Linux outdated-checks are best-effort
# and currently no-op (return empty set), so those platforms always render "Latest".
WINGET_IDS: dict[str, str] = {
    "git": "Git.Git",
    "python": "Python.Python.3.13",
    "dotnet": "Microsoft.DotNet.SDK.9",
    "node": "OpenJS.NodeJS.LTS",
    "pnpm": "pnpm.pnpm",
    "bun": "Oven-sh.Bun",
    "docker": "Docker.DockerDesktop",
    "podman": "RedHat.Podman",
    "kubectl": "Kubernetes.kubectl",
    "oc": "RedHat.OpenShift-Client",
    "terraform": "Hashicorp.Terraform",
    "az": "Microsoft.AzureCLI",
    "gcloud": "Google.CloudSDK",
    "aws": "Amazon.AWSCLI",
    "cursor": "Anysphere.Cursor",
    "windsurf": "Codeium.Windsurf",
    "ollama": "Ollama.Ollama",
    "vscode": "Microsoft.VisualStudioCode",
    "gh": "GitHub.cli",
    "sqlcmd": "Microsoft.Sqlcmd",
}


def _probe_key(key: str) -> object:
    """Detect a single env key in isolation — same value detect_env() would put there.
    Used to populate ToolsScreen one group at a time so fast groups render before slow ones.
    """
    if key == "python":
        return platform.python_version()
    if key == "dotnet":
        return _probe_version("dotnet", "--version")
    if key == "node":
        return _probe_version("node", "--version")
    if key == "npm":
        return _probe_version("npm", "--version")
    if key == "pnpm":
        return _probe_version("pnpm", "--version")
    if key == "bun":
        return _probe_version("bun", "--version")
    if key == "docker":
        return _probe_version("docker", "--version")
    if key == "podman":
        return _probe_version("podman", "--version")
    if key == "kubectl":
        return _kubectl_version()
    if key == "oc":
        return _probe_version("oc", "version", "--client")
    if key == "terraform":
        return _probe_version("terraform", "--version")
    if key == "az":
        return _probe_version("az", "--version")
    if key == "gcloud":
        return _probe_version("gcloud", "--version")
    if key == "aws":
        return _probe_version("aws", "--version")
    if key == "rider":
        return _has_rider()
    if key == "visualstudio":
        return _has_visual_studio()
    if key == "copilot":
        return (
            shutil.which("copilot") is not None
            or shutil.which("gh-copilot") is not None
        )
    if key == "vscode":
        return shutil.which("code") is not None
    if key == "vercel-plugin":
        return vercel_plugin_status() == "installed"
    if key == "vllm":
        return _probe_version("vllm", "--version") or (shutil.which("vllm") is not None)
    return shutil.which(key) is not None


def _tool_unavailable_reason(key: str) -> str | None:
    """Return why a tool is visible but intentionally not installable here."""
    if key == "vllm" and platform.system() != "Linux":
        return "Linux only - use WSL2 or a Linux Docker host for vLLM."
    return None


# Minimum major.minor we consider "current" for keys where our install target is a
# specific versioned package. The winget upgrade check can't catch these because
# the user's older version is a *different* package ID — e.g. Python.Python.3.11
# vs Python.Python.3.13. If the detected version is below the floor, we flag the
# key as outdated even if winget says nothing.
VERSION_FLOORS: dict[str, tuple[int, int]] = {
    "python": (3, 13),
    "dotnet": (9, 0),
    "node": (22, 0),  # current LTS line
}


def _parse_major_minor(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    # Strip leading 'v' (e.g. node prints 'v22.16.0') and split on the first dot.
    cleaned = raw.strip().lstrip("vV")
    parts = cleaned.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return None


def _parse_semver(raw: str | None) -> tuple[int, int, int] | None:
    """Parse 'x.y.z' (optionally prefixed with 'v' or trailed by extra text) into a tuple."""
    if not raw:
        return None
    head = raw.strip().lstrip("vV").split()[0]
    head = head.split("-")[0].split("+")[0]
    parts = head.split(".")[:3]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def _npm_latest_version(package: str, timeout: float = 5.0) -> str | None:
    """Fetch the latest published version of an npm package via the public registry."""
    url = f"https://registry.npmjs.org/{package}/latest"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.load(resp)
    except Exception:
        return None
    v = payload.get("version")
    return v if isinstance(v, str) and v else None


CLAUDE_CLI_PACKAGE = "@anthropic-ai/claude-code"
SKILLS_PACKAGE = "skills"


def _npm_cli_outdated(command: str, package: str) -> bool:
    """True if local `<command> --version` is older than `package`'s latest on npm."""
    if not shutil.which(command):
        return False
    try:
        r = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode != 0:
        return False
    local = _parse_semver((r.stdout or r.stderr).strip())
    latest = _parse_semver(_npm_latest_version(package) or "")
    return local is not None and latest is not None and local < latest


def _claude_cli_outdated() -> bool:
    """True if local `claude --version` is older than the latest @anthropic-ai/claude-code on npm."""
    return _npm_cli_outdated("claude", CLAUDE_CLI_PACKAGE)


def _below_floor(key: str, env_value: object) -> bool:
    """Return True if the detected version of `key` is older than our install target."""
    floor = VERSION_FLOORS.get(key)
    if floor is None:
        return False
    if key == "python":
        cur = _parse_major_minor(platform.python_version())
    elif key == "dotnet":
        # dotnet_sdks gives the highest installed major.minor — fall back to CLI version.
        cur = None
        if isinstance(env_value, list) and env_value:
            cur = _parse_major_minor(env_value[-1])
    elif key == "node":
        cur = _parse_major_minor(env_value if isinstance(env_value, str) else None)
    else:
        cur = None
    return cur is not None and cur < floor


def _outdated_packages() -> set[str]:
    """Env keys whose package has an upgrade available.

    Winget covers most CLIs on Windows; the Claude CLI ships via npm, so it
    needs a separate check against the npm registry to surface the Update
    button on the Tools view.
    """
    result: set[str] = set()
    if platform.system() == "Windows" and shutil.which("winget"):
        try:
            r = subprocess.run(
                [
                    "winget",
                    "upgrade",
                    "--include-unknown",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            r = None
        if r is not None and r.returncode == 0:
            text = r.stdout or ""
            result.update(key for key, wid in WINGET_IDS.items() if wid in text)
    if _claude_cli_outdated():
        result.add("claude")
    if _npm_cli_outdated("skills", SKILLS_PACKAGE):
        result.add("skills")
    return result


# Maps env-panel keys to (install fn, button label). Order here determines button order.
ENV_INSTALLERS: list[tuple[str, str, Callable[[], tuple[bool, str]]]] = [
    ("git", "Git", git_install),
    ("python", "Python", python_install),
    ("dotnet", ".NET SDK", dotnet_install),
    ("node", "Node", node_install),
    ("npm", "npm", npm_install),
    ("pnpm", "pnpm", pnpm_install),
    ("bun", "bun", bun_install),
    ("docker", "Docker", docker_install),
    ("podman", "Podman", podman_install),
    ("kubectl", "kubectl", kubectl_install),
    ("oc", "OpenShift CLI", openshift_install),
    ("terraform", "Terraform", terraform_install),
    ("az", "Azure CLI", az_install),
    ("gcloud", "Google Cloud", gcloud_install),
    ("aws", "AWS CLI", aws_install),
    ("claude", "Claude CLI", claude_cli_install),
    ("gemini", "Gemini CLI", gemini_install),
    ("codex", "Codex CLI", codex_install),
    ("opencode", "OpenCode", opencode_install),
    ("grok", "Grok", grok_install),
    ("headroom", "Headroom", headroom_install),
    ("mcp-bus", "MCP Bus", mcp_bus_install),
    ("skills", "Vercel Skills CLI", skills_install),
    ("vercel-plugin", "Vercel Plugin", vercel_plugin_install),
    ("cursor", "Cursor", cursor_install),
    ("windsurf", "Windsurf", windsurf_install),
    ("copilot", "Copilot", copilot_install),
    ("antigravity", "Antigravity", antigravity_install),
    ("vscode", "VS Code", vscode_install),
    ("ollama", "Ollama", ollama_install),
    ("vllm", "vLLM", vllm_install),
    ("gh", "GitHub", gh_install),
    ("sqlcmd", "MSSQL", sqlcmd_install),
    ("psql", "Postgres", postgres_install),
    ("supabase", "Supabase", supabase_install),
    ("neonctl", "Neon", neon_install),
]


# Groups used by ToolsScreen — order = display order, keys reference ENV_INSTALLERS.
ENV_TOOL_GROUPS: list[tuple[str, list[str]]] = [
    ("System & VCS", ["git", "gh"]),
    ("Runtimes", ["python", "dotnet", "node"]),
    ("Package Managers", ["npm", "pnpm", "bun"]),
    (
        "Container & Cloud",
        ["docker", "podman", "kubectl", "oc", "terraform", "az", "gcloud", "aws"],
    ),
    ("Databases", ["sqlcmd", "psql", "supabase", "neonctl"]),
    (
        "AI CLIs",
        [
            "claude",
            "gemini",
            "codex",
            "opencode",
            "grok",
            "copilot",
            "skills",
            "vercel-plugin",
        ],
    ),
    ("MCP", ["headroom", "mcp-bus"]),
    ("Local AI", ["ollama", "vllm"]),
    ("AI Editors", ["cursor", "windsurf", "antigravity", "vscode"]),
]


def _installer_for(key: str) -> tuple[str, Callable[[], tuple[bool, str]]] | None:
    """Return (label, install_fn) for the given env-installer key, or None."""
    for k, label, fn in ENV_INSTALLERS:
        if k == key:
            return label, fn
    return None


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
        key="skills",
        name="Skills CLI (vercel-labs/skills)",
        description=(
            "Vercel's open agent skills tool. Installs and manages reusable agent "
            "skills across 40+ AI agents including Claude Code. Installed globally "
            "via npm; use `skills add <owner>/<skill>` to pull skills into a project."
        ),
        homepage="https://www.skills.sh",
        repo_url="https://github.com/vercel-labs/skills",
        install=skills_install,
        status=skills_status,
    ),
    Tool(
        key="vercel-plugin",
        name="Vercel Claude Plugin (vercel/vercel-plugin)",
        description=(
            "Vercel's official Claude Code plugin — skills for every major Vercel "
            "product, specialized agents, and Vercel conventions. Registers the "
            "vercel marketplace and installs vercel-plugin via `claude plugin`."
        ),
        homepage="https://vercel.com",
        repo_url="https://github.com/vercel/vercel-plugin",
        install=vercel_plugin_install,
        status=vercel_plugin_status,
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
    Tool(
        key="headroom",
        name="Headroom (context compression)",
        description=(
            "Compresses tool outputs, logs, RAG chunks, and files before they reach "
            "the LLM, and exposes on-demand compress/retrieve/stats MCP tools — "
            "compression is manual and opt-in. On Windows the first install builds "
            "from source and auto-provisions Rust + VS Build Tools."
        ),
        homepage="https://headroom-docs.vercel.app/docs",
        repo_url="https://github.com/chopratejas/headroom",
        install=headroom_install,
        status=headroom_status,
    ),
    Tool(
        key="mcp-bus",
        name="MCP Bus (agent message bus)",
        description=(
            "Local message bus + shared key-value memory + agent registry for "
            "inter-agent communication; used by /orchestrate subagents. "
            "Localhost-only, no auth. Repo-local MCP service (spec 007)."
        ),
        homepage="https://github.com/dwcy/prompt-lib/tree/main/services/mcp-bus",
        repo_url="https://github.com/dwcy/prompt-lib/tree/main/services/mcp-bus",
        install=mcp_bus_install,
        status=mcp_bus_status,
    ),
]
