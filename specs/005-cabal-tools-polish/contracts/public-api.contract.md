# Contract: `cabal.wizard` Public API Surface

**Feature**: 005-cabal-tools-polish
**Surface**: Python import surface — names that MUST remain importable as `cabal.wizard.<name>` after the refactor.
**Authoritative callers**: `setup/tools/_smoketest.py`, `setup/src/cabal/__main__.py`, `setup/settings-configurator-ui.py`, `setup/build/cabal.spec`, `setup/build/README.md`, `setup/build/build_exe.py`.

## Conformance scope

Every name in the **Grandfathered** table below MUST resolve via `cabal.wizard.<name>` after the refactor. The contract test at `tests/contract/test_wizard_public_api.py` asserts this and runs before any extraction commit lands (per Constitution Gate 3).

Names in the **Internal (not contracted)** table are private to the current implementation. The refactor MAY relocate them without back-compat re-exports, since no caller outside `wizard.py` reaches for them.

## Grandfathered (MUST re-export)

| Name | Used by | Kind |
|---|---|---|
| `GLOBAL_DIR` | `_smoketest.py` | `Path` constant |
| `COMPONENTS` | `_smoketest.py` | `list[Component]` |
| `Component` | `_smoketest.py` (via `m.COMPONENTS`) | dataclass |
| `FileStatus` | indirect via `diff_component` return | dataclass |
| `detect_env` | `_smoketest.py` | function |
| `find_env_vars` | `_smoketest.py` | function |
| `diff_component` | `_smoketest.py` | function |
| `run` | `__main__.py` | function (entry point) |
| `main` | (entry point parity) | function |

PyInstaller spec lists `cabal.wizard` as a `hiddenimport`. Whatever the facade re-exports is what the analyzer sees. The Grandfathered table is the contract floor; the facade MAY re-export more (and the refactor does, for ergonomic continuity).

## Recommended re-exports (preserved for ergonomic continuity)

These names are not provably called from outside `wizard.py` today, but the facade re-exports them anyway because (a) they were globally visible in the old single file and (b) the cost of a single import line is negligible. Any external script that depended on them (without our knowledge) continues to work.

```text
# from cabal._paths
IS_FROZEN, IS_INSTALLED, SCRIPT_DIR, RESOURCE_ROOT, REPO_DIR,
ENV_DIR, ENV_FILE, MCP_TEMPLATES_FILE, TARGET

# from cabal.banner
GRID_HEIGHT, LOGO_LINES, LOGO_MAX_WIDTH, LOGO_GUTTER,
LOGO_GRADIENT, MASCOT_GRADIENT, render_banner, HexBanner

# from cabal.env_summary
render_env_summary

# from cabal.components
ENV_DESCRIPTIONS

# from cabal.os_filters
translate_for_os

# from cabal.env_detect
detect_env, find_env_vars

# from cabal.diff_apply
diff_component, find_extras, apply_statuses, backup_settings, prune_backups

# from cabal.git_config
recommended_autocrlf, apply_git_line_endings

# from cabal.updates
check_for_updates, do_git_pull

# from cabal.mcp_ops
enumerate_mcp_servers, claude_mcp_add_from_template, claude_mcp_remove

# from cabal.tools
Tool, TOOLS

# from cabal.app
CabalApp, main, run
```

## Internal (not contracted)

These are implementation details. The refactor moves them to their natural module home and does **not** re-export them through the facade.

```text
_resource_root, _detect_repo_dir, _short_docker_version, _short_podman_version,
_short_terraform_version, _short_az_version, _short_gcloud_version,
_short_aws_version, _version_field, _presence_field, _os_should_skip,
_is_plugin_only, _effective_settings_text, _is_settings_json,
_load_mcp_templates, _claude_dot_json, _run_claude_cli, _claude_mcp_list,
_probe_version, _detect_pkg_manager, _git_user_name, _kubectl_version,
_dotnet_sdks, _has_rider, _has_visual_studio, _ollama_models, _gh_login,
_gh_latest_release, _gh_pick_asset, _download, _cdt_windows_exe, cdt_status,
cdt_install, uv_install, specify_status, specify_install, claude_cli_status,
claude_cli_install, gh_status, gh_fetch_token, gh_device_init, gh_device_poll,
gh_install, _run_install, node_install, npm_install, pnpm_install, bun_install,
python_install, dotnet_install, docker_install, podman_install, kubectl_install,
terraform_install, az_install, gcloud_install, aws_install, git_install,
_npm_global_install, gemini_install, codex_install, opencode_install, grok_install,
cursor_install, windsurf_install, copilot_install, antigravity_install,
ollama_install, vscode_install, _probe_key, _parse_major_minor, _below_floor,
_outdated_packages, _installer_for, EnvPanel, UpdatePanel,
GitConfigScreen, GitHubReposScreen, GlobalEnvScreen, AppCommandsProvider,
AppHeader, HomeScreen, ReadmeScreen, EnvScreen, OperationsScreen, UpdateScreen,
DoctorScreen, RestoreScreen, McpScreen, _render_scopes, GhDeviceFlowScreen,
FolderBrowserScreen, LocalScreen, ToolsScreen
```

The refactor MAY break callers of any name in this list. If any name in this list turns out to have a real external caller, it gets promoted to **Recommended re-exports** in the same PR.

## Contract test (Phase 2 — `/speckit-tasks` will schedule writing it)

`tests/contract/test_wizard_public_api.py` must:

1. `import cabal.wizard` succeeds without error.
2. For every name in **Grandfathered**: `getattr(cabal.wizard, name)` returns a non-None object.
3. For every callable name in **Grandfathered**: `inspect.signature(getattr(cabal.wizard, name))` does not raise.
4. For every name in **Grandfathered**: `inspect.getmodule(getattr(cabal.wizard, name)).__name__.startswith("cabal.")` — the symbol's true home is inside this package.

The test runs against the source tree (`sys.path.insert(0, str(REPO_ROOT / "setup" / "src"))`) so a wheel install is not required.

## Negative contract

The following MUST NOT be true after the refactor:

- `cabal.wizard` contains any function or class **definition** (only re-exports + `__all__`).
- Importing `cabal.wizard` triggers a side effect that mutates `~/.claude/` or touches the network. (No regression from current behavior; today, `wizard.py` is import-safe.)
- Any module in the new package has a circular import with `cabal.wizard`. (Cycles can hide if a submodule re-imports the facade — forbidden.)
