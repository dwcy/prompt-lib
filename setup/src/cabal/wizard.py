# -*- coding: utf-8 -*-
"""wizard.py — CABAL Claude Code Setup Wizard (Textual TUI) — backward-compat facade.

This module is a thin re-export surface. The implementation lives in:

  - cabal._paths              paths + frozen/wheel/source resolution
  - cabal.os_filters          OS-conditional file filters
  - cabal.banner              honeycomb banner + HexBanner widget
  - cabal.env_summary         plain-text env summary block + version formatters
  - cabal.settings_helpers    settings.json strip/translate helpers
  - cabal.components          Component + COMPONENTS + ENV_DESCRIPTIONS + FileStatus
  - cabal.env_detect          host environment probing (detect_env, find_env_vars)
  - cabal.mcp_ops             `claude mcp` CLI wrappers + enumerate_mcp_servers
  - cabal.diff_apply          deploy diff/apply/backup
  - cabal.git_config          core.autocrlf application
  - cabal.updates             source-checkout update detection + git pull
  - cabal.gh_release          GitHub Releases asset fetch/download helpers
  - cabal.installers.*        per-tool installers
  - cabal.tools               Tool + TOOLS + ENV_INSTALLERS registries
  - cabal.widgets.*           reusable widgets (EnvPanel, UpdatePanel)
  - cabal.app_widgets         AppHeader + AppCommandsProvider (used by every screen)
  - cabal.views.*           one Textual screen per module
  - cabal.app                 CabalApp + main() + run() entry points

Run modes:
  - Installed:        cabal
  - Dev (checkout):   python setup/settings-configurator-ui.py
  - Standalone exe:   ./cabal[.exe]

Every name below is a re-export. See `specs/005-cabal-tools-polish/contracts/
public-api.contract.md` for the contracted import surface.
"""

from __future__ import annotations

# ─── Paths ─────────────────────────────────────────────────────────────────────
from cabal._paths import (
    IS_FROZEN,
    IS_INSTALLED,
    SCRIPT_DIR,
    RESOURCE_ROOT,
    REPO_DIR,
    GLOBAL_DIR,
    ENV_DIR,
    ENV_FILE,
    MCP_TEMPLATES_FILE,
    TARGET,
    _resource_root,
    _detect_repo_dir,
)

# ─── OS filters + banner + env summary + components ────────────────────────────
from cabal.os_filters import _os_should_skip, _is_plugin_only, translate_for_os
from cabal.banner import (
    GRID_HEIGHT,
    LOGO_LINES,
    LOGO_MAX_WIDTH,
    LOGO_GUTTER,
    LOGO_GRADIENT,
    MASCOT_GRADIENT,
    render_banner,
    HexBanner,
)
from cabal.env_summary import (
    _short_docker_version,
    _short_podman_version,
    _short_terraform_version,
    _short_az_version,
    _short_gcloud_version,
    _short_aws_version,
    _version_field,
    _presence_field,
    render_env_summary,
)
from cabal.components import Component, COMPONENTS, ENV_DESCRIPTIONS, FileStatus
from cabal.settings_helpers import _effective_settings_text, _is_settings_json

# ─── Env detection + MCP + diff/apply + git/updates/gh-release ─────────────────
from cabal.env_detect import (
    _probe_version,
    _detect_pkg_manager,
    _git_user_name,
    _kubectl_version,
    _dotnet_sdks,
    _has_rider,
    _has_visual_studio,
    _ollama_models,
    _gh_login,
    detect_env,
    find_env_vars,
)
from cabal.mcp_ops import (
    _load_mcp_templates,
    _claude_dot_json,
    _run_claude_cli,
    _claude_mcp_list,
    enumerate_mcp_servers,
    claude_mcp_add_from_template,
    claude_mcp_remove,
)
from cabal.diff_apply import (
    diff_component,
    find_extras,
    apply_statuses,
    backup_settings,
    prune_backups,
)
from cabal.git_config import recommended_autocrlf, apply_git_line_endings
from cabal.updates import check_for_updates, do_git_pull
from cabal.gh_release import _gh_latest_release, _gh_pick_asset, _download

# ─── Installers + tools ───────────────────────────────────────────────────────
from cabal.installers._common import _run_install, _npm_global_install
from cabal.installers.cdt import _cdt_windows_exe, cdt_status, cdt_install, CDT_REPO
from cabal.installers.uv import uv_install
from cabal.installers.specify import specify_status, specify_install, SPECIFY_SOURCE
from cabal.installers.claude_cli import claude_cli_status, claude_cli_install
from cabal.installers.gh import (
    gh_status,
    gh_fetch_token,
    gh_device_init,
    gh_device_poll,
    gh_install,
)
from cabal.installers.runtimes import (
    node_install,
    npm_install,
    pnpm_install,
    bun_install,
    python_install,
    dotnet_install,
)
from cabal.installers.containers import docker_install, podman_install, kubectl_install
from cabal.installers.cloud import (
    terraform_install,
    az_install,
    gcloud_install,
    aws_install,
)
from cabal.installers.vcs import git_install
from cabal.installers.ai_clis import (
    gemini_install,
    codex_install,
    opencode_install,
    grok_install,
    copilot_install,
    antigravity_install,
    ollama_install,
    vllm_install,
)
from cabal.installers.editors import cursor_install, windsurf_install, vscode_install
from cabal.tools import (
    Tool,
    TOOLS,
    WINGET_IDS,
    VERSION_FLOORS,
    ENV_INSTALLERS,
    ENV_TOOL_GROUPS,
    _probe_key,
    _parse_major_minor,
    _below_floor,
    _outdated_packages,
    _installer_for,
)

# ─── Widgets + screens + app ───────────────────────────────────────────────────
from cabal.widgets.env_panel import EnvPanel
from cabal.widgets.update_panel import UpdatePanel
from cabal.app_widgets import AppCommandsProvider, AppHeader
from cabal.views.git_config import GitConfigScreen
from cabal.views.github_repos import GitHubReposScreen
from cabal.views.global_env import GlobalEnvScreen
from cabal.views.home import HomeScreen
from cabal.views.readme import ReadmeScreen
from cabal.views.env import EnvScreen
from cabal.views.operations import OperationsScreen
from cabal.views.update import UpdateScreen
from cabal.views.restore import RestoreScreen
from cabal.views.mcp import McpScreen
from cabal.mcp_view_logic import render_scopes as _render_scopes
from cabal.views.gh_device import GhDeviceFlowScreen
from cabal.views.folder_browser import FolderBrowserScreen
from cabal.views.local import LocalScreen
from cabal.views.tools import ToolsScreen
from cabal.app import CabalApp, main, run


__all__ = [
    "IS_FROZEN",
    "IS_INSTALLED",
    "SCRIPT_DIR",
    "RESOURCE_ROOT",
    "REPO_DIR",
    "GLOBAL_DIR",
    "ENV_DIR",
    "ENV_FILE",
    "MCP_TEMPLATES_FILE",
    "TARGET",
    "GRID_HEIGHT",
    "LOGO_LINES",
    "LOGO_MAX_WIDTH",
    "LOGO_GUTTER",
    "LOGO_GRADIENT",
    "MASCOT_GRADIENT",
    "render_banner",
    "HexBanner",
    "render_env_summary",
    "translate_for_os",
    "Component",
    "COMPONENTS",
    "ENV_DESCRIPTIONS",
    "FileStatus",
    "detect_env",
    "find_env_vars",
    "diff_component",
    "find_extras",
    "apply_statuses",
    "backup_settings",
    "prune_backups",
    "recommended_autocrlf",
    "apply_git_line_endings",
    "check_for_updates",
    "do_git_pull",
    "enumerate_mcp_servers",
    "claude_mcp_add_from_template",
    "claude_mcp_remove",
    "Tool",
    "TOOLS",
    "CabalApp",
    "main",
    "run",
]
