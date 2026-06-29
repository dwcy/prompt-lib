# -*- coding: utf-8 -*-
"""Metadata catalog for Cabal Tools rows.

The installer registry lives in ``cabal.tools`` because it needs callable
installer functions. This module owns stable row metadata so tests and the
Textual view can enforce descriptions, source links, categories, platform
support, version providers, and backup policies without duplicating strings.
"""

from __future__ import annotations

import platform
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class SourceStatus(StrEnum):
    VERIFIED = "verified"
    MANUAL_REQUIRED = "manual_required"
    UNAVAILABLE = "unavailable"


class InstallChannel(StrEnum):
    PACKAGE = "package"
    DESKTOP_APP = "desktop_app"
    CONTAINER_SERVICE = "container_service"
    EMBEDDED_ENGINE = "embedded_engine"
    MANUAL = "manual"
    NONE = "none"


class PlatformSupport(StrEnum):
    ALL = "all"
    WINDOWS = "Windows"
    DARWIN = "Darwin"
    LINUX = "Linux"


@dataclass(frozen=True)
class ToolCategory:
    name: str
    slug: str
    keys: tuple[str, ...]
    sort_mode: str = "declared"


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    label: str
    category: str
    description: str
    source_url: str | None
    source_label: str = "Read more"
    source_status: SourceStatus = SourceStatus.VERIFIED
    install_channel: InstallChannel = InstallChannel.PACKAGE
    status_probe: str | None = None
    installer: str | None = None
    platforms: tuple[str, ...] = (PlatformSupport.ALL.value,)
    version_provider: str | None = None
    backup_policy: str | None = None
    badges: tuple[str, ...] = ()
    secret_policy: str = "redact"

    @property
    def automation_enabled(self) -> bool:
        return (
            self.source_status == SourceStatus.VERIFIED
            and self.install_channel not in {InstallChannel.MANUAL, InstallChannel.NONE}
            and self.installer is not None
        )

    @property
    def supports_current_platform(self) -> bool:
        return supports_platform(self.platforms)


SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"\b[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:Bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
)


def redact_secret_text(text: object) -> str:
    """Return text with token-shaped values replaced by a stable marker."""
    value = "" if text is None else str(text)
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[redacted]", value)
    return value


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _is_progress_glyph(ch: str) -> bool:
    code = ord(ch)
    return (
        0x2800 <= code <= 0x28FF  # braille spinner frames
        or 0x2580 <= code <= 0x259F  # block-element progress bars
        or ch in "|/-\\"  # ascii spinners
    )


def clean_console_output(text: object) -> str:
    """Strip CLI progress/spinner noise from captured installer output.

    Installers (npm/pnpm/winget) render progress with carriage-return overwrites
    and spinner glyphs; a naive splitlines() turns every frame into its own row.
    Keep only the final segment per line, drop ANSI codes, and remove rows that
    are nothing but spinner/progress glyphs.
    """
    if not text:
        return ""
    value = _ANSI_RE.sub("", str(text))
    cleaned: list[str] = []
    for raw_line in value.split("\n"):
        segment = raw_line.split("\r")[-1].rstrip()
        if not segment:
            continue
        stripped = segment.strip()
        if stripped and all(_is_progress_glyph(ch) or ch.isspace() for ch in stripped):
            continue
        cleaned.append(segment)
    return "\n".join(cleaned)


def supports_platform(platforms: Iterable[str]) -> bool:
    values = tuple(platforms)
    return PlatformSupport.ALL.value in values or platform.system() in values


def _t(
    key: str,
    label: str,
    category: str,
    description: str,
    source_url: str | None,
    *,
    source_status: SourceStatus = SourceStatus.VERIFIED,
    install_channel: InstallChannel = InstallChannel.PACKAGE,
    status_probe: str | None = None,
    installer: str | None = None,
    platforms: tuple[str, ...] = (PlatformSupport.ALL.value,),
    version_provider: str | None = None,
    backup_policy: str | None = None,
    badges: tuple[str, ...] = (),
    source_label: str = "Read more",
) -> ToolDefinition:
    return ToolDefinition(
        key=key,
        label=label,
        category=category,
        description=description,
        source_url=source_url,
        source_label=source_label,
        source_status=source_status,
        install_channel=install_channel,
        status_probe=status_probe or key,
        installer=installer or key,
        platforms=platforms,
        version_provider=version_provider,
        backup_policy=backup_policy,
        badges=badges,
    )


TOOL_CATEGORIES: tuple[ToolCategory, ...] = (
    ToolCategory("System & VCS", "system-vcs", ("git", "gh")),
    ToolCategory("Runtimes", "runtimes", ("python", "dotnet", "node")),
    ToolCategory("Package Managers", "package-managers", ("npm", "pnpm", "bun", "uv")),
    ToolCategory(
        "Container & Cloud",
        "container-cloud",
        ("docker", "podman", "kubectl", "oc", "terraform", "az", "gcloud", "aws"),
    ),
    ToolCategory(
        "Databases",
        "databases",
        (
            "psql",
            "sqlcmd",
            "supabase",
            "neonctl",
            "turso-libsql",
            "sqlite",
            "duckdb",
            "redis",
            "mariadb",
            "qdrant",
            "weaviate",
            "milvus",
        ),
    ),
    ToolCategory("Database Clients", "database-clients", ("ssms", "dbeaver")),
    ToolCategory(
        "Azure Local Tools",
        "azure-local-tools",
        ("azure-sql-local", "cosmos-db-emulator", "azurite"),
    ),
    ToolCategory(
        "AI CLIs",
        "ai-clis",
        (
            "claude",
            "gemini",
            "huggingface",
            "codex",
            "grok",
            "copilot",
            "skills",
            "vercel-plugin",
        ),
    ),
    ToolCategory("MCP", "mcp", ("headroom", "mcp-bus")),
    ToolCategory(
        "Local AI",
        "local-ai",
        ("ollama", "vllm", "lm-studio", "opencode", "hermes-agent"),
    ),
    ToolCategory(
        "AI Editors / IDEs",
        "ai-editors-ides",
        ("cursor", "windsurf", "antigravity", "vscode", "zed", "rider", "visualstudio"),
    ),
    ToolCategory(
        "Developer Tools",
        "developer-tools",
        ("postman", "hugo", "uvicorn", "specify", "claude-devtools"),
    ),
)


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    _t(
        "git",
        "Git",
        "System & VCS",
        "Distributed version control used by nearly every project workflow.",
        "https://git-scm.com/",
    ),
    _t(
        "gh",
        "GitHub CLI",
        "System & VCS",
        "Official GitHub command-line client for repos, issues, pull requests, and auth.",
        "https://cli.github.com/",
    ),
    _t(
        "python",
        "Python",
        "Runtimes",
        "Python runtime used by Cabal, tests, scripts, and many agent tools.",
        "https://www.python.org/downloads/",
        version_provider="python",
        backup_policy="python",
    ),
    _t(
        "dotnet",
        ".NET SDK",
        "Runtimes",
        ".NET SDK for building and running C# and related projects.",
        "https://dotnet.microsoft.com/download",
        version_provider="dotnet",
        backup_policy="dotnet",
    ),
    _t(
        "node",
        "Node",
        "Runtimes",
        "JavaScript runtime required by npm-based CLIs and web tooling.",
        "https://nodejs.org/",
        version_provider="node",
        backup_policy="node",
    ),
    _t(
        "npm",
        "npm",
        "Package Managers",
        "Node package manager used to install global JavaScript CLIs.",
        "https://www.npmjs.com/",
        version_provider="npm",
        backup_policy="npm",
    ),
    _t(
        "pnpm",
        "pnpm",
        "Package Managers",
        "Fast disk-efficient package manager for Node projects.",
        "https://pnpm.io/",
        version_provider="pnpm",
        backup_policy="pnpm",
    ),
    _t(
        "bun",
        "bun",
        "Package Managers",
        "Fast JavaScript runtime, test runner, bundler, and package manager.",
        "https://bun.sh/",
        version_provider="bun",
        backup_policy="bun",
    ),
    _t(
        "uv",
        "uv",
        "Package Managers",
        "Fast Python package manager, project manager, and tool runner recommended for Python CLIs.",
        "https://docs.astral.sh/uv/",
        badges=("recommended",),
    ),
    _t(
        "docker",
        "Docker",
        "Container & Cloud",
        "Container runtime used for local database and service installs.",
        "https://www.docker.com/products/docker-desktop/",
    ),
    _t(
        "podman",
        "Podman",
        "Container & Cloud",
        "Daemonless container engine alternative used for local service installs.",
        "https://podman.io/",
    ),
    _t(
        "kubectl",
        "kubectl",
        "Container & Cloud",
        "Kubernetes CLI for managing clusters and local kube contexts.",
        "https://kubernetes.io/docs/tasks/tools/",
    ),
    _t(
        "oc",
        "OpenShift CLI",
        "Container & Cloud",
        "OpenShift command-line client for cluster administration and app workflows.",
        "https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html",
    ),
    _t(
        "terraform",
        "Terraform",
        "Container & Cloud",
        "HashiCorp infrastructure-as-code CLI for provisioning cloud resources.",
        "https://developer.hashicorp.com/terraform/install",
    ),
    _t(
        "az",
        "Azure CLI",
        "Container & Cloud",
        "Microsoft Azure command-line client for cloud and local emulator workflows.",
        "https://learn.microsoft.com/cli/azure/install-azure-cli",
    ),
    _t(
        "gcloud",
        "Google Cloud",
        "Container & Cloud",
        "Google Cloud SDK CLI for managing GCP projects and services.",
        "https://cloud.google.com/sdk/docs/install",
    ),
    _t(
        "aws",
        "AWS CLI",
        "Container & Cloud",
        "Amazon Web Services CLI for managing AWS accounts and resources.",
        "https://aws.amazon.com/cli/",
    ),
    _t(
        "psql",
        "Postgres CLI",
        "Databases",
        "PostgreSQL client tools for connecting to local or remote Postgres databases.",
        "https://www.postgresql.org/docs/current/app-psql.html",
    ),
    _t(
        "sqlcmd",
        "sqlcmd",
        "Databases",
        "Microsoft SQL Server command-line client for SQL Server and Azure SQL.",
        "https://learn.microsoft.com/sql/tools/sqlcmd/sqlcmd-utility",
    ),
    _t(
        "supabase",
        "Supabase CLI",
        "Databases",
        "Supabase CLI for local stacks and project management.",
        "https://supabase.com/docs/guides/cli",
    ),
    _t(
        "neonctl",
        "Neon CLI",
        "Databases",
        "Neon serverless Postgres CLI for managing Neon projects.",
        "https://neon.tech/docs/reference/cli",
    ),
    _t(
        "turso-libsql",
        "Turso/libSQL",
        "Databases",
        "Local libSQL service compatible with Turso-style SQLite workflows.",
        "https://docs.turso.tech/",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "sqlite",
        "SQLite",
        "Databases",
        "Embedded file-oriented SQL database with a local CLI utility.",
        "https://sqlite.org/",
        install_channel=InstallChannel.EMBEDDED_ENGINE,
    ),
    _t(
        "duckdb",
        "DuckDB",
        "Databases",
        "Embedded analytical SQL engine for local files and data science workflows.",
        "https://duckdb.org/",
        install_channel=InstallChannel.EMBEDDED_ENGINE,
    ),
    _t(
        "redis",
        "Redis",
        "Databases",
        "In-memory data platform and cache, installed locally as a container service.",
        "https://hub.docker.com/_/redis",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "mariadb",
        "MariaDB",
        "Databases",
        "Open-source relational database installed locally as a container service.",
        "https://hub.docker.com/_/mariadb",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "qdrant",
        "Qdrant",
        "Databases",
        "Vector database for AI retrieval workloads, installed as a local container service.",
        "https://qdrant.tech/documentation/quickstart/",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "weaviate",
        "Weaviate",
        "Databases",
        "AI-native vector database with local Docker deployment guidance.",
        "https://docs.weaviate.io/deploy/installation-guides/docker-installation",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "milvus",
        "Milvus",
        "Databases",
        "Open-source vector database for embeddings and similarity search.",
        "https://milvus.io/docs/install_standalone-docker.md",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "ssms",
        "SQL Server Management Studio",
        "Database Clients",
        "Microsoft desktop client for SQL Server and Azure SQL administration.",
        "https://learn.microsoft.com/ssms/install/install",
        install_channel=InstallChannel.DESKTOP_APP,
        platforms=(PlatformSupport.WINDOWS.value,),
    ),
    _t(
        "dbeaver",
        "DBeaver",
        "Database Clients",
        "Cross-platform database client for SQL, NoSQL, and cloud databases.",
        "https://dbeaver.io/download/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "azure-sql-local",
        "Azure SQL Local",
        "Azure Local Tools",
        "Local Azure SQL development option for testing SQL Server-compatible apps.",
        "https://learn.microsoft.com/azure/azure-sql/database/local-dev-experience-overview",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "cosmos-db-emulator",
        "Cosmos DB Emulator",
        "Azure Local Tools",
        "Microsoft emulator for developing and testing Azure Cosmos DB apps locally.",
        "https://learn.microsoft.com/azure/cosmos-db/emulator",
        install_channel=InstallChannel.DESKTOP_APP,
        platforms=(PlatformSupport.WINDOWS.value,),
    ),
    _t(
        "azurite",
        "Azurite",
        "Azure Local Tools",
        "Local Azure Storage emulator for Blob, Queue, and Table development.",
        "https://learn.microsoft.com/azure/storage/common/storage-use-azurite",
        install_channel=InstallChannel.CONTAINER_SERVICE,
    ),
    _t(
        "claude",
        "Claude CLI",
        "AI CLIs",
        "Anthropic Claude Code CLI for agentic coding sessions.",
        "https://docs.anthropic.com/en/docs/claude-code/overview",
    ),
    _t(
        "gemini",
        "Gemini CLI",
        "AI CLIs",
        "Google Gemini command-line interface for AI-assisted development.",
        "https://github.com/google-gemini/gemini-cli",
    ),
    _t(
        "huggingface",
        "Hugging Face CLI",
        "AI CLIs",
        "Official `hf` CLI for Hugging Face Hub auth, uploads, downloads, repos, cache, and skills.",
        "https://huggingface.co/docs/huggingface_hub/en/guides/cli",
    ),
    _t(
        "codex",
        "Codex CLI",
        "AI CLIs",
        "OpenAI Codex command-line interface for local coding workflows.",
        "https://github.com/openai/codex",
    ),
    _t(
        "grok",
        "Grok CLI",
        "AI CLIs",
        "xAI/Grok-related CLI entry for terminal AI workflows.",
        "https://github.com/superagent-ai/vibekit/tree/main/clients/grok-cli",
    ),
    _t(
        "copilot",
        "GitHub Copilot CLI",
        "AI CLIs",
        "Official GitHub Copilot agentic command-line assistant for coding workflows.",
        "https://github.com/github/copilot-cli",
    ),
    _t(
        "skills",
        "Vercel Skills CLI",
        "AI CLIs",
        "Agent skills CLI for installing reusable skills across AI agents.",
        "https://www.skills.sh/",
    ),
    _t(
        "vercel-plugin",
        "Vercel Plugin",
        "AI CLIs",
        "Vercel Claude Code plugin with Vercel-specific skills and agents.",
        "https://github.com/vercel/vercel-plugin",
    ),
    _t(
        "headroom",
        "Headroom",
        "MCP",
        "Context-compression layer - on-demand compress/retrieve/stats MCP tools that shrink tool outputs/logs before they reach the model (manual, opt-in). Windows install builds from source.",
        "https://github.com/chopratejas/headroom",
        source_status=SourceStatus.VERIFIED,
    ),
    _t(
        "mcp-bus",
        "MCP Bus",
        "MCP",
        "Local agent message bus + shared key-value memory + registry (11 tools) for inter-agent comms; used by /orchestrate subagents. Repo-local MCP service (spec 007).",
        "https://github.com/dwcy/prompt-lib/tree/main/services/mcp-bus",
        source_status=SourceStatus.VERIFIED,
    ),
    _t(
        "ollama",
        "Ollama",
        "Local AI",
        "Local model runner for downloading and serving open models on your machine.",
        "https://ollama.com/",
    ),
    _t(
        "vllm",
        "vLLM",
        "Local AI",
        "High-throughput OpenAI-compatible inference server for Linux GPU hosts.",
        "https://docs.vllm.ai/",
        platforms=(PlatformSupport.LINUX.value,),
    ),
    _t(
        "lm-studio",
        "LM Studio",
        "Local AI",
        "Desktop app and local server for running private local language models.",
        "https://lmstudio.ai/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "opencode",
        "OpenCode",
        "Local AI",
        "AI coding agent available as terminal CLI and desktop app signals.",
        "https://opencode.ai/docs",
    ),
    _t(
        "hermes-agent",
        "Hermes Agent",
        "Local AI",
        "Requested agent entry; install is disabled until an official upstream is confirmed.",
        None,
        source_status=SourceStatus.MANUAL_REQUIRED,
        install_channel=InstallChannel.MANUAL,
        installer=None,
    ),
    _t(
        "cursor",
        "Cursor",
        "AI Editors / IDEs",
        "AI-first code editor based on VS Code.",
        "https://cursor.com/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "windsurf",
        "Windsurf",
        "AI Editors / IDEs",
        "AI-native editor from Codeium/Windsurf for agentic coding workflows.",
        "https://windsurf.com/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "antigravity",
        "Antigravity",
        "AI Editors / IDEs",
        "Google Antigravity agentic development environment.",
        "https://antigravity.google/",
        install_channel=InstallChannel.MANUAL,
    ),
    _t(
        "vscode",
        "VS Code",
        "AI Editors / IDEs",
        "Microsoft Visual Studio Code editor and extension platform.",
        "https://code.visualstudio.com/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "zed",
        "Zed",
        "AI Editors / IDEs",
        "Fast collaborative code editor with AI workflows and native app installers.",
        "https://zed.dev/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "rider",
        "Rider",
        "AI Editors / IDEs",
        "JetBrains Rider IDE for .NET and game development.",
        "https://www.jetbrains.com/rider/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "visualstudio",
        "Visual Studio",
        "AI Editors / IDEs",
        "Microsoft Visual Studio IDE for .NET, C++, desktop, and cloud development.",
        "https://visualstudio.microsoft.com/",
        install_channel=InstallChannel.DESKTOP_APP,
        platforms=(PlatformSupport.WINDOWS.value,),
    ),
    _t(
        "postman",
        "Postman",
        "Developer Tools",
        "API client and collaboration tool for testing HTTP APIs.",
        "https://www.postman.com/downloads/",
        install_channel=InstallChannel.DESKTOP_APP,
    ),
    _t(
        "hugo",
        "Hugo",
        "Developer Tools",
        "Fast static-site generator written in Go.",
        "https://gohugo.io/installation/",
    ),
    _t(
        "uvicorn",
        "Uvicorn",
        "Developer Tools",
        "ASGI web server used to run FastAPI and other Python async apps.",
        "https://www.uvicorn.org/",
    ),
    _t(
        "specify",
        "Specify CLI",
        "Developer Tools",
        "GitHub Spec Kit CLI - `specify init` scaffolds spec-driven `.specify/` workflows. Installed via uv tool from the upstream git repo.",
        "https://github.com/github/spec-kit",
        source_status=SourceStatus.VERIFIED,
    ),
    _t(
        "claude-devtools",
        "claude-devtools",
        "Developer Tools",
        "Desktop GUI that visualizes Claude Code session activity from local ~/.claude logs (file paths, tool calls, tokens). Runs locally, no API keys.",
        "https://github.com/matt1398/claude-devtools",
        source_status=SourceStatus.VERIFIED,
        install_channel=InstallChannel.DESKTOP_APP,
    ),
)


CATALOG_BY_KEY: dict[str, ToolDefinition] = {
    tool.key: tool for tool in TOOL_DEFINITIONS
}


def all_tool_definitions() -> tuple[ToolDefinition, ...]:
    return TOOL_DEFINITIONS


def get_tool_definition(key: str) -> ToolDefinition | None:
    return CATALOG_BY_KEY.get(key)


def category_groups() -> list[tuple[str, list[str]]]:
    return [(category.name, list(category.keys)) for category in TOOL_CATEGORIES]


def category_slug(name: str) -> str:
    for category in TOOL_CATEGORIES:
        if category.name == name:
            return category.slug
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def validate_catalog() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    category_keys = [key for category in TOOL_CATEGORIES for key in category.keys]
    for key in category_keys:
        if key in seen:
            errors.append(f"duplicate category key: {key}")
        seen.add(key)
        if key not in CATALOG_BY_KEY:
            errors.append(f"missing ToolDefinition for {key}")

    for tool in TOOL_DEFINITIONS:
        if tool.key not in category_keys:
            errors.append(f"{tool.key} is not listed in any ToolCategory")
        if not tool.label.strip():
            errors.append(f"{tool.key} has empty label")
        if not tool.description.strip():
            errors.append(f"{tool.key} has empty description")
        if tool.source_status == SourceStatus.VERIFIED and not tool.source_url:
            errors.append(f"{tool.key} verified source lacks source_url")
        if tool.source_status != SourceStatus.VERIFIED and tool.automation_enabled:
            errors.append(f"{tool.key} enables automation without verified source")
        if redact_secret_text(tool.description) != tool.description:
            errors.append(f"{tool.key} description contains secret-shaped text")
        if tool.source_url and redact_secret_text(tool.source_url) != tool.source_url:
            errors.append(f"{tool.key} source_url contains secret-shaped text")
    return errors
