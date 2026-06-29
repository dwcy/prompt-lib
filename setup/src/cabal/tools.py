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
    _has_copilot_cli,
    _has_huggingface_cli,
    _has_lm_studio,
    _opencode_status,
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
    hermes_agent_install,
    huggingface_install,
    lm_studio_install,
    ollama_install,
    opencode_install,
    vllm_install,
)
from cabal.installers.cdt import cdt_install, cdt_status
from cabal.installers.claude_cli import claude_cli_install, claude_cli_status
from cabal.installers.cloud import (
    aws_install,
    azure_sql_local_install,
    azurite_install,
    az_install,
    cosmos_db_emulator_install,
    gcloud_install,
    terraform_install,
)
from cabal.installers.databases import (
    container_database_status,
    dbeaver_install,
    duckdb_install,
    mariadb_install,
    neon_install,
    postgres_install,
    qdrant_install,
    redis_install,
    sqlite_install,
    ssms_install,
    sqlcmd_install,
    supabase_install,
    turso_libsql_install,
    weaviate_install,
    milvus_install,
)
from cabal.installers.containers import (
    docker_install,
    kubectl_install,
    openshift_install,
    podman_install,
)
from cabal.installers.devtools import hugo_install, postman_install, uvicorn_install
from cabal.installers.editors import (
    cursor_install,
    rider_install,
    visualstudio_install,
    vscode_install,
    windsurf_install,
    zed_install,
)
from cabal.installers.gh import gh_install, gh_status
from cabal.installers.headroom import headroom_install
from cabal.installers.mcp_bus import mcp_bus_install
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
from cabal.installers.uv import uv_install
from cabal.installers.vcs import git_install
from cabal.installers.vercel_plugin import vercel_plugin_install, vercel_plugin_status
from cabal.tool_catalog import (
    InstallChannel,
    SourceStatus,
    all_tool_definitions,
    category_groups,
    get_tool_definition,
)

# Maps env keys → winget package IDs (mirrors the install fns above). Used to spot
# upgrade availability via `winget upgrade`. macOS/Linux outdated-checks are best-effort
# and currently no-op (return empty set), so those platforms always render "Latest".
WINGET_IDS: dict[str, str] = {
    "git": "Git.Git",
    "python": "Python.Python.3.14",
    "dotnet": "Microsoft.DotNet.SDK.9",
    "node": "OpenJS.NodeJS.LTS",
    "pnpm": "pnpm.pnpm",
    "bun": "Oven-sh.Bun",
    "uv": "astral-sh.uv",
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
    "lm-studio": "LMStudio.LMStudio",
    "zed": "Zed.Zed",
    "rider": "JetBrains.Rider",
    "visualstudio": "Microsoft.VisualStudio.2022.Community",
    "ssms": "Microsoft.SQLServerManagementStudio",
    "dbeaver": "dbeaver.dbeaver",
    "postman": "Postman.Postman",
    "hugo": "Hugo.Hugo.Extended",
    "copilot": "GitHub.Copilot",
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
    if key == "uv":
        return _probe_version("uv", "--version")
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
    if key == "huggingface":
        return _probe_version("hf", "version") or _has_huggingface_cli()
    if key == "lm-studio":
        return _has_lm_studio()
    if key == "opencode":
        return _opencode_status()
    if key == "hermes-agent":
        return False
    if key == "zed":
        return shutil.which("zed") is not None
    if key == "rider":
        return _has_rider()
    if key == "visualstudio":
        return _has_visual_studio()
    if key == "ssms":
        if platform.system() != "Windows":
            return False
        return shutil.which("ssms") is not None or shutil.which("Ssms") is not None
    if key == "dbeaver":
        return shutil.which("dbeaver") is not None
    if key == "sqlite":
        return _probe_version("sqlite3", "--version")
    if key == "duckdb":
        return _probe_version("duckdb", "--version")
    if key in {
        "redis",
        "mariadb",
        "turso-libsql",
        "qdrant",
        "weaviate",
        "milvus",
        "azure-sql-local",
        "azurite",
    }:
        return container_database_status(key)
    if key == "cosmos-db-emulator":
        return (
            platform.system() == "Windows"
            and shutil.which("Microsoft.Azure.Cosmos.Emulator") is not None
        )
    if key == "postman":
        return shutil.which("postman") is not None
    if key == "hugo":
        return _probe_version("hugo", "version")
    if key == "uvicorn":
        return _probe_version("uvicorn", "--version")
    if key == "copilot":
        return _has_copilot_cli()
    if key == "vscode":
        return shutil.which("code") is not None
    if key == "vercel-plugin":
        return vercel_plugin_status() == "installed"
    if key == "claude-devtools":
        # Desktop GUI — not a PATH binary; cdt_status() stats install locations.
        return cdt_status().startswith("installed")
    if key == "vllm":
        return _probe_version("vllm", "--version") or (shutil.which("vllm") is not None)
    return shutil.which(key) is not None


def _tool_unavailable_reason(key: str) -> str | None:
    """Return why a tool is visible but intentionally not installable here."""
    if key == "vllm" and platform.system() != "Linux":
        return "Linux only - use WSL2 or a Linux Docker host for vLLM."
    definition = get_tool_definition(key)
    if definition is not None:
        if not definition.supports_current_platform:
            platforms = ", ".join(definition.platforms)
            return f"Supported on {platforms}; current platform is {platform.system()}."
        if definition.source_status == SourceStatus.MANUAL_REQUIRED:
            return (
                "Source confirmation required before automated install can be enabled."
            )
        if definition.source_status == SourceStatus.UNAVAILABLE:
            return "Source link unavailable; install automation is disabled."
        if not definition.automation_enabled and definition.install_channel in {
            InstallChannel.MANUAL,
            InstallChannel.NONE,
        }:
            return "Manual setup required; use Read more for official guidance."
    return None


# Minimum major.minor we consider "current" for keys where our install target is a
# specific versioned package. The winget upgrade check can't catch these because
# the user's older version is a *different* package ID — e.g. Python.Python.3.13
# vs Python.Python.3.14. If the detected version is below the floor, we flag the
# key as outdated even if winget says nothing.
VERSION_FLOORS: dict[str, tuple[int, int]] = {
    "python": (3, 14),
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
COPILOT_CLI_PACKAGE = "@github/copilot"
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
    if _npm_cli_outdated("copilot", COPILOT_CLI_PACKAGE):
        result.add("copilot")
    return result


# Maps catalog installer keys to callables. Labels and grouping come from
# cabal.tool_catalog so descriptions/source metadata stay in one place.
INSTALLER_FUNCTIONS: dict[str, Callable[[], tuple[bool, str]]] = {
    "git": git_install,
    "python": python_install,
    "dotnet": dotnet_install,
    "node": node_install,
    "npm": npm_install,
    "pnpm": pnpm_install,
    "bun": bun_install,
    "uv": uv_install,
    "docker": docker_install,
    "podman": podman_install,
    "kubectl": kubectl_install,
    "oc": openshift_install,
    "terraform": terraform_install,
    "az": az_install,
    "gcloud": gcloud_install,
    "aws": aws_install,
    "claude": claude_cli_install,
    "gemini": gemini_install,
    "huggingface": huggingface_install,
    "codex": codex_install,
    "opencode": opencode_install,
    "grok": grok_install,
    "headroom": headroom_install,
    "mcp-bus": mcp_bus_install,
    "skills": skills_install,
    "vercel-plugin": vercel_plugin_install,
    "cursor": cursor_install,
    "windsurf": windsurf_install,
    "copilot": copilot_install,
    "antigravity": antigravity_install,
    "vscode": vscode_install,
    "ollama": ollama_install,
    "vllm": vllm_install,
    "gh": gh_install,
    "sqlcmd": sqlcmd_install,
    "psql": postgres_install,
    "supabase": supabase_install,
    "neonctl": neon_install,
    "lm-studio": lm_studio_install,
    "hermes-agent": hermes_agent_install,
    "zed": zed_install,
    "rider": rider_install,
    "visualstudio": visualstudio_install,
    "ssms": ssms_install,
    "dbeaver": dbeaver_install,
    "postman": postman_install,
    "hugo": hugo_install,
    "uvicorn": uvicorn_install,
    "specify": specify_install,
    "claude-devtools": cdt_install,
    "sqlite": sqlite_install,
    "duckdb": duckdb_install,
    "redis": redis_install,
    "mariadb": mariadb_install,
    "turso-libsql": turso_libsql_install,
    "qdrant": qdrant_install,
    "weaviate": weaviate_install,
    "milvus": milvus_install,
    "azure-sql-local": azure_sql_local_install,
    "cosmos-db-emulator": cosmos_db_emulator_install,
    "azurite": azurite_install,
}


ENV_INSTALLERS: list[tuple[str, str, Callable[[], tuple[bool, str]]]] = [
    (tool.key, tool.label, INSTALLER_FUNCTIONS[tool.key])
    for tool in all_tool_definitions()
    if tool.key in INSTALLER_FUNCTIONS
]


ENV_TOOL_GROUPS: list[tuple[str, list[str]]] = category_groups()


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
]
