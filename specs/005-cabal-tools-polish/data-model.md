# Phase 1 — Data Model (Module Ownership Map)

**Feature**: 005-cabal-tools-polish
**Date**: 2026-05-28

There are no domain entities in this refactor. The "data model" here is the **module → symbol** ownership map: which file in the new package owns which top-level name from the current `setup/src/cabal/wizard.py`.

Source line numbers are anchored to `wizard.py` as it exists on branch `005-cabal-tools-polish` HEAD (commit `7b4bb18`).

## Module → symbol map

### `cabal/_paths.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `IS_FROZEN` | 32 | Module-level constant. |
| `_resource_root` | 72–82 | Mutates module-level `IS_INSTALLED`. |
| `IS_INSTALLED` | 69 | Mutated by `_resource_root`. |
| `_detect_repo_dir` | 85–96 | |
| `SCRIPT_DIR` | 99 | |
| `RESOURCE_ROOT` | 100 | |
| `REPO_DIR` | 101 | |
| `GLOBAL_DIR` | 102 | Re-exported by facade. |
| `ENV_DIR` | 103 | |
| `ENV_FILE` | 104 | |
| `MCP_TEMPLATES_FILE` | 105 | |
| `TARGET` | 106 | |

### `cabal/banner.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `GRID_HEIGHT`, `_TILE_WIDTH`, `LOGO_LINES`, `LOGO_MAX_WIDTH`, `LOGO_GUTTER`, `_MIN_TILES`, `LOGO_GRADIENT`, `MASCOT_GRADIENT` | 111–128 | Module constants. |
| `render_banner` | 131–177 | |
| `HexBanner` | 180–190 | Static widget. |

### `cabal/env_summary.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_short_docker_version` | 193–199 | |
| `_short_podman_version` | 201–207 | |
| `_short_terraform_version` | 209–217 | |
| `_short_az_version` | 219–225 | |
| `_short_gcloud_version` | 227–233 | |
| `_short_aws_version` | 235–242 | |
| `_version_field` | 244–247 | |
| `_presence_field` | 249–252 | |
| `render_env_summary` | 254–282 | |

### `cabal/os_filters.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_os_should_skip` | 284–301 | |
| `_is_plugin_only` | 303–310 | |
| `translate_for_os` | 312–322 | |

### `cabal/components.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `Component` (dataclass + methods) | 325–358 | Depends on `_paths.GLOBAL_DIR`, `_paths.TARGET`, `os_filters._os_should_skip`, `os_filters._is_plugin_only`. |
| `COMPONENTS` | 361–374 | Re-exported by facade. |
| `ENV_DESCRIPTIONS` | 376–426 | |
| `FileStatus` (dataclass) | 429–434 | |

### `cabal/updates.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `check_for_updates` | 439–497 | Uses `REPO_DIR`. |
| `do_git_pull` | 499–512 | Uses `REPO_DIR`. (Note: keeps living with `check_for_updates` since both share `REPO_DIR` and the "is this a checkout?" branching logic.) |

### `cabal/env_detect.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_probe_version` | 514–533 | Pure subprocess wrapper. |
| `_detect_pkg_manager` | 535–551 | |
| `_git_user_name` | 553–565 | |
| `_kubectl_version` | 567–586 | |
| `_dotnet_sdks` | 588–609 | |
| `_has_rider` | 611–614 | |
| `_has_visual_studio` | 616–633 | |
| `_ollama_models` | 635–655 | |
| `_gh_login` | 657–676 | |
| `detect_env` | 678–720 | Re-exported by facade. |
| `find_env_vars` | 722–725 | Re-exported by facade. |

### `cabal/settings_helpers.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_effective_settings_text` | 728–744 | |
| `_is_settings_json` | 746–755 | |

### `cabal/mcp_ops.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_load_mcp_templates` | 757–764 | |
| `_claude_dot_json` | 766–774 | |
| `_run_claude_cli` | 776–788 | |
| `_claude_mcp_list` | 790–813 | |
| `enumerate_mcp_servers` | 815–875 | |
| `claude_mcp_add_from_template` | 877–903 | |
| `claude_mcp_remove` | 905–910 | |

### `cabal/diff_apply.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `diff_component` | 912–926 | Re-exported by facade. |
| `find_extras` | 928–934 | |
| `apply_statuses` | 936–950 | |
| `backup_settings` | 952–960 | |
| `prune_backups` | 962–966 | |

### `cabal/git_config.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `recommended_autocrlf` | 968–970 | |
| `apply_git_line_endings` | 972–990 | |

### `cabal/gh_release.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_gh_latest_release` | 992–1001 | |
| `_gh_pick_asset` | 1003–1008 | |
| `_download` | 1010–1020 | |

### `cabal/installers/_common.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_run_install` | 1327–1343 | |
| `_npm_global_install` | 1617–1621 | |

### `cabal/installers/claude_cli.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `claude_cli_status`, `claude_cli_install` | 1177–1192 | |

### `cabal/installers/cdt.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_cdt_windows_exe` | 1022–1025 | |
| `cdt_status` | 1027–1056 | |
| `cdt_install` | 1058–1109 | |

### `cabal/installers/uv.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `uv_install` | 1111–1140 | |

### `cabal/installers/specify.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `specify_status`, `specify_install` | 1142–1175 | |

### `cabal/installers/gh.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `gh_status` | 1194–1200 | |
| `gh_fetch_token` | 1202–1222 | |
| `gh_device_init` | 1224–1241 | |
| `gh_device_poll` | 1243–1290 | |
| `gh_install` | 1292–1325 | |

### `cabal/installers/runtimes.py`

| Symbol | Source lines |
|---|---|
| `node_install` | 1345–1367 |
| `npm_install` | 1369–1372 |
| `pnpm_install` | 1374–1393 |
| `bun_install` | 1395–1412 |
| `python_install` | 1414–1436 |
| `dotnet_install` | 1438–1457 |

### `cabal/installers/containers.py`

| Symbol | Source lines |
|---|---|
| `docker_install` | 1459–1473 |
| `podman_install` | 1475–1494 |
| `kubectl_install` | 1496–1515 |

### `cabal/installers/cloud.py`

| Symbol | Source lines |
|---|---|
| `terraform_install` | 1517–1537 |
| `az_install` | 1539–1556 |
| `gcloud_install` | 1558–1573 |
| `aws_install` | 1575–1592 |

### `cabal/installers/vcs.py`

| Symbol | Source lines |
|---|---|
| `git_install` | 1594–1615 |

### `cabal/installers/ai_clis.py`

| Symbol | Source lines |
|---|---|
| `gemini_install` | 1623–1625 |
| `codex_install` | 1627–1629 |
| `opencode_install` | 1631–1633 |
| `grok_install` | 1635–1638 |
| `copilot_install` | 1666–1671 |
| `antigravity_install` | 1673–1676 |
| `ollama_install` | 1678–1691 |

### `cabal/installers/editors.py`

| Symbol | Source lines |
|---|---|
| `cursor_install` | 1640–1651 |
| `windsurf_install` | 1653–1664 |
| `vscode_install` | 1693–1735 |

### `cabal/tools.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `_probe_key` | 1737–1772 | |
| `_parse_major_minor` | 1774–1783 | |
| `_below_floor` | 1785–1802 | |
| `_outdated_packages` | 1804–1863 | |
| `_installer_for` | 1865–1870 | Imports every `cabal.installers.*` module — anchors them for PyInstaller. |
| `Tool` (dataclass) | 1873–1881 | |
| `TOOLS` | 1884–1935 | |

### `cabal/widgets/env_panel.py`

| Symbol | Source lines |
|---|---|
| `EnvPanel` | 1940–2206 |

### `cabal/widgets/update_panel.py`

| Symbol | Source lines |
|---|---|
| `UpdatePanel` | 2207–2287 |

### `cabal/views/git_config.py`

| Symbol | Source lines |
|---|---|
| `GitConfigScreen` | 2288–2399 |

### `cabal/views/github_repos.py`

| Symbol | Source lines |
|---|---|
| `GitHubReposScreen` | 2400–2511 |

### `cabal/views/global_env.py`

| Symbol | Source lines |
|---|---|
| `GlobalEnvScreen` | 2512–2577 |

### `cabal/views/home.py`

| Symbol | Source lines |
|---|---|
| `AppCommandsProvider` | 2578–2618 |
| `AppHeader` | 2619–2625 |
| `HomeScreen` | 2626–2705 |

*(Note: `AppCommandsProvider` and `AppHeader` move to `cabal/app.py` instead — they belong with `CabalApp`, not `HomeScreen`. The line range above shows where they currently sit; the destination is `app.py`. `HomeScreen` itself stays at `screens/home.py`.)*

### `cabal/views/readme.py`

| Symbol | Source lines |
|---|---|
| `ReadmeScreen` | 2706–2727 |

### `cabal/views/env.py`

| Symbol | Source lines |
|---|---|
| `EnvScreen` | 2728–2919 |

### `cabal/views/operations.py`

| Symbol | Source lines |
|---|---|
| `OperationsScreen` | 2920–2973 |

### `cabal/views/update.py`

| Symbol | Source lines |
|---|---|
| `UpdateScreen` | 2974–3095 |

### Standalone Doctor screen retired

The standalone `DoctorScreen` and `cabal/views/doctor.py` are no longer part
of the active TUI. Drift is surfaced through home-screen markers and the update
preview flow.

### `cabal/views/restore.py`

| Symbol | Source lines |
|---|---|
| `RestoreScreen` | 3156–3208 |

### `cabal/views/mcp.py`

| Symbol | Source lines |
|---|---|
| `_render_scopes` | 3350–3358 |
| `McpScreen` | 3209–3349 |

### `cabal/views/gh_device.py`

| Symbol | Source lines |
|---|---|
| `GhDeviceFlowScreen` | 3360–3451 |

### `cabal/views/folder_browser.py`

| Symbol | Source lines |
|---|---|
| `FolderBrowserScreen` | 3452–3727 |

### `cabal/views/local.py`

| Symbol | Source lines |
|---|---|
| `LocalScreen` | 3728–4058 |

### `cabal/views/tools.py`

| Symbol | Source lines |
|---|---|
| `ToolsScreen` | 4059–4325 |

### `cabal/app.py`

| Symbol | Source lines | Notes |
|---|---|---|
| `AppCommandsProvider` | 2578–2618 | Moves here from line 2578. |
| `AppHeader` | 2619–2625 | Moves here from line 2619. |
| `CabalApp` (incl. inline `CSS`, `BINDINGS`, `COMMANDS`, `on_mount`) | 4326–4489 | |
| `main` | 4492–4493 | Same logic. |
| `run` | 4496–4498 | Same logic. |

### `cabal/wizard.py` (facade after refactor)

A single `__all__` plus re-exports. Names listed in `contracts/public-api.contract.md` MUST all appear. Expected size: < 200 LOC. Example shape:

```python
"""wizard.py — backward-compatible facade. See cabal.<submodule> for implementation."""
from cabal._paths import (
    IS_FROZEN, IS_INSTALLED, SCRIPT_DIR, RESOURCE_ROOT, REPO_DIR,
    GLOBAL_DIR, ENV_DIR, ENV_FILE, MCP_TEMPLATES_FILE, TARGET,
)
from cabal.components import Component, COMPONENTS, ENV_DESCRIPTIONS, FileStatus
from cabal.env_detect import detect_env, find_env_vars
from cabal.diff_apply import diff_component, apply_statuses, backup_settings, find_extras, prune_backups
from cabal.app import run, main, CabalApp
# ... (full list — see public-api.contract.md)

__all__ = [...]
```

## Invariants

- **I-1**: For every symbol listed in `contracts/public-api.contract.md`, the post-refactor codebase satisfies `import cabal.wizard; getattr(cabal.wizard, name)` without `AttributeError`.
- **I-2**: For every symbol re-exported by the facade, exactly one canonical home exists in `cabal.<submodule>`. No symbol is duplicated across files.
- **I-3**: `cabal/wizard.py` contains **no** function or class definitions (other than the module-level `__all__`). Everything is imported from a submodule.
- **I-4**: `cabal/app.py` imports every screen at module top, so PyInstaller's static analyzer follows the graph (R6).

---

# Part B — Domain Entities

Added 2026-05-28 (spec extension). These are in-memory dataclasses used by the Init Project + Project MCP + Claude Stats Panel features. None are persisted as a database; they live for the duration of the wizard session. The only on-disk artifact is `<project>/.mcp.json` and the contents of `<project>/`.

All new dataclasses live in `cabal/init_project_service.py` unless otherwise noted.

## Entity — `GitHubTemplateRef`

Represents one of the user's GitHub template repositories.

| Field | Type | Notes |
|---|---|---|
| `owner` | `str` | GitHub login of the owner. |
| `name` | `str` | Repo name. |
| `description` | `str \| None` | Short description from `gh repo list`. May be empty. |
| `default_branch` | `str` | e.g. `main`, `master`. Pulled from `defaultBranchRef.name`. |
| `url` | `str` | HTML URL (for display only). |
| `is_template` | `bool` | Always `True` for entries shown in the picker; the filter `isTemplate == true` happens before construction. |

**Validation**: `name` must be non-empty; the constructor refuses repos missing `defaultBranchRef` (defensive — `gh` returns `None` for fork-of-empty-repo cases).

## Entity — `LocalTemplateRef`

Represents one of the bundled `global/project-templates/*.md` templates.

| Field | Type | Notes |
|---|---|---|
| `stem` | `str` | Filename without `.md` — one of `python`, `dotnet`, `frontend`, `monorepo`, `unity`, `other`. |
| `path` | `pathlib.Path` | Absolute path to the `.md` file. |
| `gitignore_preset_name` | `str \| None` | Matches `stem` against `GITIGNORE_BY_TEMPLATE` keys; `None` if no preset. |

## Entity — `InjectableFile`

One file staged for injection into the new project.

| Field | Type | Notes |
|---|---|---|
| `source_path` | `pathlib.Path` | Absolute path on disk (under the temp extract dir for GH templates, or under `global/` for local templates). |
| `dest_relpath` | `pathlib.PurePosixPath` | Destination path relative to `<project>/`. POSIX-style for cross-platform consistency. |
| `size_bytes` | `int` | Cached `source_path.stat().st_size`. |
| `selected` | `bool` | UI checkbox state. Default `True`. |
| `status` | `Literal["NEW", "OVERWRITE", "SKIP"]` | Computed against the (currently empty) `<project>/` — always `NEW` for v1 since Apply refuses non-empty target dirs (FR-13). Kept as a field for future use. |
| `origin` | `Literal["github", "local-template", "scaffold"]` | Where the file came from — drives display group in the table. |

**Validation**: `dest_relpath` MUST NOT contain `..` segments and MUST NOT be absolute (R-5/R14). Constructor raises `ValueError` if so.

## Entity — `ProjectMcpEntry`

One MCP server toggled into the new project's `.mcp.json`.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Server name (e.g. `context7`, `playwright`). |
| `command` | `str` | Executable (e.g. `npx`, `python`). |
| `args` | `list[str]` | argv tail. |
| `env` | `dict[str, str]` | Env vars to set when launching. Values from `os.environ` at the moment the user toggled the row. |

**Serialised shape** (in `<project>/.mcp.json`):

```json
{
  "mcpServers": {
    "<name>": {
      "command": "<command>",
      "args": ["..."],
      "env": {"KEY": "value"}
    }
  }
}
```

## Entity — `ProjectInitPlan`

Top-level dataclass capturing the user's choices on `InitProjectScreen` immediately before Apply.

| Field | Type | Notes |
|---|---|---|
| `parent_dir` | `pathlib.Path` | From `FolderBrowserScreen`. |
| `project_name` | `str` | Validated against `^[A-Za-z0-9._-]{1,64}$` + Windows-reserved-name denylist (R3/R12). |
| `template_source` | `Literal["github", "local"]` | |
| `template_ref` | `GitHubTemplateRef \| LocalTemplateRef` | |
| `injectable_files` | `list[InjectableFile]` | Every file the user might write, including ones with `selected=False`. |
| `mcp_entries` | `list[ProjectMcpEntry]` | Toggled-on project-scope MCP rows. May be empty. |
| `invoke_claude` | `bool` | Default `True`. False when user explicitly opts out (advanced toggle, off by default UI but spec'd for completeness). |

**Derived field**: `target_dir` (computed property) = `parent_dir / project_name`. Validated on Apply (FR-13: refuse if exists & non-empty).

**State transition**:

```
                          (folder picked + name entered)
[empty]  ─────────────────────────────────────────►  [template source picked]
                                                          │
                                              (gh repo OR local template picked)
                                                          ▼
                                                   [files staged]
                                                          │
                                                 (review / uncheck rows)
                                                          ▼
                                                  [MCP picked (optional)]
                                                          │
                                                 (Apply button pressed)
                                                          ▼
                       (mkdir target_dir; write selected files; write .mcp.json if any entries; invoke claude -p)
                                                          ▼
                                                   [applied / failed]
```

## Entity — `ClaudeAccountStatus`

In-memory snapshot of the user's Claude account, shown in the `ClaudeStatsPanel` (Part B addendum, US11, FR-16). Lives in `cabal/widgets/claude_stats_panel.py`.

| Field | Type | Notes |
|---|---|---|
| `account_type` | `Literal["Pro", "Max 5x", "Max 20x", "Team", "Enterprise", "API", "unknown"]` | Parsed from `claude -p "/status"` output. |
| `email` | `str \| None` | From the same `/status` output OR from `~/.claude.json["oauthAccount"]["emailAddress"]`. |
| `signed_in` | `bool` | True if `email` is non-None and `claude /status` did not print "not signed in". |
| `five_hour_used_pct` | `int \| None` | 0..100; `None` if not parsed. |
| `weekly_cap_used_pct` | `int \| None` | 0..100; `None` if not parsed. |
| `active_model` | `str \| None` | e.g. `claude-opus-4-7`. |
| `token_present` | `bool` | Derived from `~/.claude.json` having an `oauthAccount` dict — never the value. |
| `raw_status_output` | `str \| None` | Fallback display when parsing fails (R18 / R-9). |
| `error` | `str \| None` | Populated when `claude` not on PATH or invocation failed. |

**Forbidden fields** (must NOT exist on this dataclass): `oauth_token`, `api_key`, `refresh_token`, any literal credential string.

**Refresh policy**: on `on_mount` and on user-triggered refresh only. Never polled.

## Cross-entity invariants (Part B)

- **I-5**: Every `InjectableFile` written by Apply MUST resolve to a path strictly under `<ProjectInitPlan.target_dir>`. The implementation MUST do `Path(target).resolve().relative_to(target_dir.resolve())` and refuse on `ValueError` — defence-in-depth against a template with `..` that slipped past the early check.
- **I-6**: `ProjectInitPlan.target_dir` MUST NOT exist OR MUST be empty before Apply succeeds (FR-13).
- **I-7**: `ProjectMcpEntry.env` MUST NOT contain the literal substring of any value (i.e., we copy values from `os.environ` at toggle time and serialise them verbatim — we do NOT redact them). This is consistent with how `claude_mcp_add_from_template` already passes `-e KEY=VALUE` to `claude mcp add`. *(This is for `.mcp.json` only — distinct from I-8 below.)*
- **I-8**: `ClaudeAccountStatus` MUST NOT carry any field whose value is a literal token or API key. The panel renders presence as `✓ token present` / `✗ no token`, never the value.
- **I-9**: After Apply, `<target_dir>/.gitignore` MUST contain exactly one `.mcp.json` line (FR-17). This holds even when the user opted out of every MCP toggle — the file is gitignored unconditionally because the wizard COULD write secrets to it on a later run, and we want the rule expressed before that happens.
