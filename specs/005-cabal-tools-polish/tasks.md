---

description: "Task list for 005-cabal-tools-polish — Refactor cabal/wizard.py into Maintainable Modules"
---

# Tasks: Refactor `cabal/wizard.py` into Maintainable Modules

**Input**: Design documents from `/specs/005-cabal-tools-polish/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.contract.md, quickstart.md

**Tests**: One **mandatory** contract test (`tests/contract/test_wizard_public_api.py`) per Constitution Gate 3 — asserts the public-api floor holds before and after every extraction. No additional unit tests are in scope for this refactor.

**Organization**: Tasks are grouped by user story so each can be implemented and validated independently. Per Gate 6, all extraction tasks run **sequentially** on `005-cabal-tools-polish` — they edit the same source file (`setup/src/cabal/wizard.py`) and would collide if dispatched in parallel.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1 — installer maintenance, US2 — screen maintenance, US3 — smoketest parity, US4 — console-script parity, US5 — PyInstaller parity)
- **Owner**: Named subagent from `.specify/memory/agents.md`
- **Parallel: yes**: NEVER used in this feature — every extraction edits `wizard.py`. See `plan.md` Parallel Execution Map.

## Phase status convention

Every Phase heading carries `**Status**: ⬜🟡✅ (M/N — T###–T###)`. Rewrite the Status line whenever a checkbox changes.

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: 🟡 In progress (2/3 — T001–T003)
**Purpose**: Create the test directory, capture a smoketest baseline, and confirm the current `wizard.py` is byte-identical to the integration branch tip before any extraction begins.

- [X] T001 Create directory `tests/contract/` with an empty `__init__.py` placeholder file at repo root — Owner: main
- [X] T002 Capture pre-refactor smoketest baseline by running `python setup/tools/_smoketest.py > tests/contract/_baseline_smoketest.txt 2>&1` (one-shot capture; the resulting file is committed for diffing in later phases) — Owner: main
- [ ] T003 [P] Verify `python -m cabal` boots the TUI to HomeScreen and quits cleanly on the maintainer's machine; record the result in the PR description — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (3/3 — T004–T006)
**Purpose**: Write the public-API contract test against the current monolithic `wizard.py` and watch it pass. This locks in the import-surface floor. Every subsequent extraction phase re-runs this test before moving on.

**⚠️ CRITICAL**: T005 MUST pass against the current monolithic `wizard.py` before T007 starts. No extraction begins until the floor is green.

- [X] T004 [US3] Write `tests/contract/test_wizard_public_api.py` per `specs/005-cabal-tools-polish/contracts/public-api.contract.md` — asserts every Grandfathered name resolves via `getattr(cabal.wizard, name)`, has a real Python module home under `cabal.`, and (for callables) yields a non-raising `inspect.signature`. Test inserts `setup/src` on `sys.path` so a wheel install is not required — Owner: @python-tester
- [X] T005 [US3] Run `python -m pytest tests/contract/test_wizard_public_api.py -v` against the current `wizard.py` and confirm PASS. If any name fails to resolve today, fix the contract list in `contracts/public-api.contract.md` (not the code) before continuing — Owner: @python-tester
- [X] T006 [US3] Document in the PR body that the contract test will be re-run after every extraction; record the baseline pass output as evidence — Owner: main

**Checkpoint**: Foundation ready — every Grandfathered name has a passing assertion; safe to start moving code.

---

## Phase 3: Leaf Layer Extractions (Path / OS / Banner / Format helpers)

**Status**: ✅ Complete (5/5 — T007–T011)
**Goal**: Move modules with **zero internal `cabal` dependencies** out of `wizard.py`. After each task, `wizard.py` re-imports from the new module and re-exports the names so the contract test stays green.

**Independent test**: `python -m pytest tests/contract/test_wizard_public_api.py` PASSES after every task in this phase. Run the smoketest after the last task and diff against `tests/contract/_baseline_smoketest.txt` — diff must be empty.

- [X] T007 [US3] Extract `IS_FROZEN`, `IS_INSTALLED`, `_resource_root`, `_detect_repo_dir`, `SCRIPT_DIR`, `RESOURCE_ROOT`, `REPO_DIR`, `GLOBAL_DIR`, `ENV_DIR`, `ENV_FILE`, `MCP_TEMPLATES_FILE`, `TARGET` from `setup/src/cabal/wizard.py` (current lines 32, 69, 72–106) → new file `setup/src/cabal/_paths.py`. Update `wizard.py` to re-import every moved name. Re-run T005 — must pass — Owner: @python-architect
- [X] T008 [US3] Extract `_os_should_skip`, `_is_plugin_only`, `translate_for_os` (current lines 284–322) → new file `setup/src/cabal/os_filters.py`. `wizard.py` re-imports. Re-run T005 — Owner: @python-architect
- [X] T009 [US3] Extract banner constants (`GRID_HEIGHT`, `_TILE_WIDTH`, `LOGO_LINES`, `LOGO_MAX_WIDTH`, `LOGO_GUTTER`, `_MIN_TILES`, `LOGO_GRADIENT`, `MASCOT_GRADIENT`), `render_banner`, `HexBanner` (current lines 111–190) → new file `setup/src/cabal/banner.py`. `wizard.py` re-imports. Re-run T005 — Owner: @python-architect
- [X] T010 [US3] Extract `_short_docker_version`, `_short_podman_version`, `_short_terraform_version`, `_short_az_version`, `_short_gcloud_version`, `_short_aws_version`, `_version_field`, `_presence_field`, `render_env_summary` (current lines 193–282) → new file `setup/src/cabal/env_summary.py`. `wizard.py` re-imports `render_env_summary`. Re-run T005 — Owner: @python-architect
- [X] T011 [US3] Extract `_effective_settings_text`, `_is_settings_json` (current lines 728–755) → new file `setup/src/cabal/settings_helpers.py`. `wizard.py` keeps these as internal — no facade re-export needed. Re-run T005 — Owner: @python-architect

**Checkpoint**: 5 leaf modules extracted, contract test green, smoketest diff empty.

---

## Phase 4: Mid Layer Extractions (Components / Env detection / MCP / Diff-apply / Git / Updates / GH-release)

**Status**: ✅ Complete (7/7 — T012–T018)
**Goal**: Move modules that depend on Phase 3 leaves but no Textual widgets/screens. These are the pure-logic modules that screens consume.

**Independent test**: contract test green after each task; smoketest diff empty after T018.

- [X] T012 [US3] Extract `Component` (dataclass with `list_files` method), `COMPONENTS` list, `ENV_DESCRIPTIONS` table, `FileStatus` dataclass (current lines 325–434) → new file `setup/src/cabal/components.py`. Imports `GLOBAL_DIR`, `TARGET` from `cabal._paths`; imports `_os_should_skip`, `_is_plugin_only` from `cabal.os_filters`. `wizard.py` re-imports the names. Re-run T005 — Owner: @python-architect
- [X] T013 [US3] Extract `_probe_version`, `_detect_pkg_manager`, `_git_user_name`, `_kubectl_version`, `_dotnet_sdks`, `_has_rider`, `_has_visual_studio`, `_ollama_models`, `_gh_login`, `detect_env`, `find_env_vars` (current lines 514–725) → new file `setup/src/cabal/env_detect.py`. `wizard.py` re-imports `detect_env` and `find_env_vars`. Re-run T005 — Owner: @python-architect
- [X] T014 [US3] Extract `_load_mcp_templates`, `_claude_dot_json`, `_run_claude_cli`, `_claude_mcp_list`, `enumerate_mcp_servers`, `claude_mcp_add_from_template`, `claude_mcp_remove` (current lines 757–910) → new file `setup/src/cabal/mcp_ops.py`. Imports `MCP_TEMPLATES_FILE` from `cabal._paths`. `wizard.py` re-imports the three public functions. Re-run T005 — Owner: @python-architect
- [X] T015 [US3] Extract `diff_component`, `find_extras`, `apply_statuses`, `backup_settings`, `prune_backups` (current lines 912–966) → new file `setup/src/cabal/diff_apply.py`. Imports from `cabal._paths`, `cabal.components`, `cabal.os_filters`, `cabal.settings_helpers`. `wizard.py` re-imports every name. Re-run T005 — Owner: @python-architect
- [X] T016 [US3] Extract `recommended_autocrlf`, `apply_git_line_endings` (current lines 968–990) → new file `setup/src/cabal/git_config.py`. `wizard.py` re-imports both. Re-run T005 — Owner: @python-architect
- [X] T017 [US3] Extract `check_for_updates`, `do_git_pull` (current lines 439–512) → new file `setup/src/cabal/updates.py`. Imports `REPO_DIR` from `cabal._paths`. `wizard.py` re-imports both. Re-run T005 — Owner: @python-architect
- [X] T018 [US3] Extract `_gh_latest_release`, `_gh_pick_asset`, `_download` (current lines 992–1020) → new file `setup/src/cabal/gh_release.py`. `wizard.py` keeps these as internal (no facade re-export). Re-run T005 — Owner: @python-architect

**Checkpoint**: All non-installer / non-UI logic lives in dedicated modules. Smoketest diff empty.

---

## Phase 5: User Story 1 — Installer Modularization 🎯 MVP

**Status**: ✅ Complete (13/13 — T019–T031)
**Goal**: Maintainers can add a new tool installer by creating one focused module under `cabal.installers.*` and registering it.

**Independent test**: After T031, opening `setup/src/cabal/installers/` shows one file per logical group; `tools.py` imports every group; the contract test passes; `python -m cabal` Tools screen still lists every existing installer with the same status icons.

- [X] T019 [US1] Create `setup/src/cabal/installers/__init__.py` as an empty package marker — Owner: main
- [X] T020 [US1] Extract `_run_install` (current lines 1327–1343) and `_npm_global_install` (current lines 1617–1621) → new file `setup/src/cabal/installers/_common.py`. `wizard.py` keeps these as internal. Re-run T005 — Owner: @python-architect
- [X] T021 [US1] Extract `claude_cli_status`, `claude_cli_install` (current lines 1177–1192) → new file `setup/src/cabal/installers/claude_cli.py`. Re-run T005 — Owner: @python-architect
- [X] T022 [US1] Extract `_cdt_windows_exe`, `cdt_status`, `cdt_install` (current lines 1022–1109) → new file `setup/src/cabal/installers/cdt.py`. Imports `_gh_latest_release`, `_gh_pick_asset`, `_download` from `cabal.gh_release`. Re-run T005 — Owner: @python-architect
- [X] T023 [US1] Extract `uv_install` (current lines 1111–1140) → new file `setup/src/cabal/installers/uv.py`. Re-run T005 — Owner: @python-architect
- [X] T024 [US1] Extract `specify_status`, `specify_install` (current lines 1142–1175) → new file `setup/src/cabal/installers/specify.py`. Imports `uv_install` from `cabal.installers.uv`. Re-run T005 — Owner: @python-architect
- [X] T025 [US1] Extract `gh_status`, `gh_fetch_token`, `gh_device_init`, `gh_device_poll`, `gh_install` (current lines 1194–1325) → new file `setup/src/cabal/installers/gh.py`. Re-run T005 — Owner: @python-architect
- [X] T026 [US1] Extract `node_install`, `npm_install`, `pnpm_install`, `bun_install`, `python_install`, `dotnet_install` (current lines 1345–1457) → new file `setup/src/cabal/installers/runtimes.py`. Imports `_run_install` from `cabal.installers._common`. Re-run T005 — Owner: @python-architect
- [X] T027 [US1] Extract `docker_install`, `podman_install`, `kubectl_install` (current lines 1459–1515) → new file `setup/src/cabal/installers/containers.py`. Re-run T005 — Owner: @python-architect
- [X] T028 [US1] Extract `terraform_install`, `az_install`, `gcloud_install`, `aws_install` (current lines 1517–1592) → new file `setup/src/cabal/installers/cloud.py`. Re-run T005 — Owner: @python-architect
- [X] T029 [US1] Extract `git_install` (current lines 1594–1615) → new file `setup/src/cabal/installers/vcs.py`. Re-run T005 — Owner: @python-architect
- [X] T030 [US1] Extract `gemini_install`, `codex_install`, `opencode_install`, `grok_install`, `copilot_install`, `antigravity_install`, `ollama_install` (current lines 1623–1638 + 1666–1691) → new file `setup/src/cabal/installers/ai_clis.py`. Imports `_npm_global_install` from `cabal.installers._common`. Re-run T005 — Owner: @python-architect
- [X] T031 [US1] Extract `cursor_install`, `windsurf_install`, `vscode_install` (current lines 1640–1664 + 1693–1735) → new file `setup/src/cabal/installers/editors.py`. Re-run T005. Then extract `_probe_key`, `_parse_major_minor`, `_below_floor`, `_outdated_packages`, `_installer_for`, `Tool` dataclass, `TOOLS` list (current lines 1737–1935) → new file `setup/src/cabal/tools.py`. `tools.py` imports every installer module by name so PyInstaller's analyzer follows the graph. `wizard.py` re-imports `Tool` and `TOOLS` (Recommended re-export). Re-run T005 — Owner: @python-architect

**Checkpoint**: All 24 installer functions live in domain-grouped files. `cabal.tools` is the single anchor that pulls every installer module. Maintainers can add `installers/<new_tool>.py` and append one row to `TOOLS`.

---

## Phase 6: User Story 2 — Widget + Screen Modularization

**Status**: ✅ Complete (18/18 — T032–T049)
**Goal**: Maintainers can add a new Textual screen by creating one file under `cabal.views.*` and importing it from `cabal.app`.

**Independent test**: After T049, every screen file lives at `setup/src/cabal/views/<name>.py`; widgets at `setup/src/cabal/widgets/<name>.py`; `cabal.app` imports every screen at module top so PyInstaller's analyzer follows the graph. Manual TUI smoke test: every existing screen still opens.

**Cross-screen import rule** (per research.md R5): if a screen pushes a sibling screen, the import lives **inside the action handler**, not at module top.

- [X] T032 [US2] Create `setup/src/cabal/widgets/__init__.py` and `setup/src/cabal/views/__init__.py` as empty package markers — Owner: main
- [X] T033 [US2] Extract `UpdatePanel` (current lines 2207–2287) → new file `setup/src/cabal/widgets/update_panel.py`. Imports `check_for_updates`, `do_git_pull` from `cabal.updates`. Re-run T005 — Owner: @python-architect
- [X] T034 [US2] Extract `EnvPanel` (current lines 1940–2206) → new file `setup/src/cabal/widgets/env_panel.py`. Imports `UpdatePanel` from `cabal.widgets.update_panel`; `detect_env` from `cabal.env_detect`; `_installer_for`, `_outdated_packages`, `TOOLS` from `cabal.tools`. Re-run T005 — Owner: @python-architect
- [X] T035 [US2] Extract `ReadmeScreen` (current lines 2706–2727) → new file `setup/src/cabal/views/readme.py`. Re-run T005 — Owner: @python-architect
- [X] T036 [US2] Extract `OperationsScreen` (current lines 2920–2973) → new file `setup/src/cabal/views/operations.py`. Lazy-imports sibling screens inside `action_*` handlers per R5. Re-run T005 — Owner: @python-architect
- [X] T037 [US2] Retire the standalone `DoctorScreen`; drift is now surfaced through home-screen markers and update-preview flows, so no `cabal/views/doctor.py` module remains — Owner: @python-architect
- [X] T038 [US2] Extract `RestoreScreen` (current lines 3156–3208) → new file `setup/src/cabal/views/restore.py`. Imports `backup_settings`, `prune_backups` from `cabal.diff_apply`. Re-run T005 — Owner: @python-architect
- [X] T039 [US2] Extract `_render_scopes` helper and `McpScreen` (current lines 3209–3358) → new file `setup/src/cabal/views/mcp.py`. Imports `enumerate_mcp_servers`, `claude_mcp_add_from_template`, `claude_mcp_remove` from `cabal.mcp_ops`. Re-run T005 — Owner: @python-architect
- [X] T040 [US2] Extract `GhDeviceFlowScreen` (current lines 3360–3451) → new file `setup/src/cabal/views/gh_device.py`. Imports `gh_device_init`, `gh_device_poll` from `cabal.installers.gh`. Re-run T005 — Owner: @python-architect
- [X] T041 [US2] Extract `FolderBrowserScreen` (current lines 3452–3727) → new file `setup/src/cabal/views/folder_browser.py`. Re-run T005 — Owner: @python-architect
- [X] T042 [US2] Extract `GitConfigScreen` (current lines 2288–2399) → new file `setup/src/cabal/views/git_config.py`. Imports `recommended_autocrlf`, `apply_git_line_endings` from `cabal.git_config`. Re-run T005 — Owner: @python-architect
- [X] T043 [US2] Extract `GitHubReposScreen` (current lines 2400–2511) → new file `setup/src/cabal/views/github_repos.py`. Imports `gh_fetch_token` from `cabal.installers.gh`. Lazy-imports `GhDeviceFlowScreen` inside its action handler. Re-run T005 — Owner: @python-architect
- [X] T044 [US2] Extract `GlobalEnvScreen` (current lines 2512–2577) → new file `setup/src/cabal/views/global_env.py`. Re-run T005 — Owner: @python-architect
- [X] T045 [US2] Extract `EnvScreen` (current lines 2728–2919) → new file `setup/src/cabal/views/env.py`. Imports `find_env_vars`, `ENV_DESCRIPTIONS`, `GlobalEnvScreen`, `GitConfigScreen`, `FolderBrowserScreen` (lazy where needed). Re-run T005 — Owner: @python-architect
- [X] T046 [US2] Extract `UpdateScreen` (current lines 2974–3095) → new file `setup/src/cabal/views/update.py`. Imports `diff_component`, `apply_statuses`, `find_extras`, `backup_settings` from `cabal.diff_apply`; `COMPONENTS` from `cabal.components`. Re-run T005 — Owner: @python-architect
- [X] T047 [US2] Extract `ToolsScreen` (current lines 4059–4325) → new file `setup/src/cabal/views/tools.py`. Imports `TOOLS`, `_installer_for` from `cabal.tools`; `detect_env` from `cabal.env_detect`. Re-run T005 — Owner: @python-architect
- [X] T048 [US2] Extract `LocalScreen` (current lines 3728–4058) → new file `setup/src/cabal/views/local.py`. Imports `Component`, `COMPONENTS`, `diff_component`, `apply_statuses` and lazy-imports `FolderBrowserScreen`. Re-run T005 — Owner: @python-architect
- [X] T049 [US2] Extract `HomeScreen` (current lines 2626–2705) → new file `setup/src/cabal/views/home.py`. Lazy-imports `OperationsScreen`, `ReadmeScreen`, `EnvScreen` inside its action handlers. Re-run T005 — Owner: @python-architect

**Checkpoint**: All 15 screens + 2 widgets live in dedicated files. Manual TUI walk: every screen opens. Contract test green.

---

## Phase 7: App & Facade

**Status**: ✅ Complete (3/3 — T050–T052)
**Goal**: Move the application root and convert `wizard.py` into a thin re-export facade.

- [X] T050 [US4][US5] Extract `AppCommandsProvider` (current lines 2578–2618), `AppHeader` (current lines 2619–2625), `CabalApp` with its inline CSS / BINDINGS / COMMANDS / `on_mount` (current lines 4326–4489), `main` (current lines 4492–4493), `run` (current lines 4496–4498) → new file `setup/src/cabal/app.py`. `app.py` imports every active screen at module top (per R6) so PyInstaller's static analyzer follows the graph: `from cabal.views.home import HomeScreen` and the same for `ReadmeScreen`, `EnvScreen`, `GitConfigScreen`, `GitHubReposScreen`, `GlobalEnvScreen`, `OperationsScreen`, `UpdateScreen`, `RestoreScreen`, `McpScreen`, `GhDeviceFlowScreen`, `FolderBrowserScreen`, `LocalScreen`, `ToolsScreen`. The CSS blob stays inline (per research.md R2). Re-run T005 — Owner: @python-architect
- [X] T051 [US3][US4][US5] Convert `setup/src/cabal/wizard.py` into a facade < 200 LOC: keep only the module docstring, a `from cabal.<submodule> import <names>` block for every Grandfathered + Recommended name in `contracts/public-api.contract.md`, and a single `__all__` list naming every re-exported symbol. Verify with `wc -l setup/src/cabal/wizard.py` (< 200). Verify with a grep that `wizard.py` contains **no** `def ` and **no** `class ` top-level definitions (Invariant I-3). Re-run T005 — Owner: @python-architect
- [X] T052 [US3] Re-run smoketest and confirm empty diff: `python setup/tools/_smoketest.py > /tmp/cabal_smoketest_after.txt 2>&1; diff tests/contract/_baseline_smoketest.txt /tmp/cabal_smoketest_after.txt`. If non-empty, revert HEAD and diagnose — Owner: main

**Checkpoint**: `wizard.py` is now a facade; the smoketest output is byte-identical to baseline; the contract test passes.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Status**: 🟡 In progress (6/8 — T053–T060)
**Purpose**: Build-tooling parity, documentation refresh, and verification.

- [X] T053 [P][US5] Update `setup/build/cabal.spec` `hiddenimports` list from `["cabal", "cabal.wizard"]` to include every new top-level submodule for belt-and-suspenders coverage: `"cabal._paths"`, `"cabal.banner"`, `"cabal.env_summary"`, `"cabal.os_filters"`, `"cabal.components"`, `"cabal.env_detect"`, `"cabal.settings_helpers"`, `"cabal.mcp_ops"`, `"cabal.diff_apply"`, `"cabal.git_config"`, `"cabal.updates"`, `"cabal.gh_release"`, `"cabal.tools"`, `"cabal.app"`, plus every `"cabal.installers.<name>"`, `"cabal.widgets.<name>"`, `"cabal.views.<name>"` — Owner: main
- [X] T054 [P] Search `setup/build/README.md` for references to symbol lines/locations in `wizard.py` and update them to point at the new module homes (or generalise to "see the relevant submodule under `setup/src/cabal/`"). Do **not** rewrite the README from scratch — preserve every paragraph not touching wizard internals — Owner: main
- [X] T055 [P][US3] Re-run `python -m pytest tests/contract/test_wizard_public_api.py -v` one final time on a clean checkout. Confirm PASS. Record the output in the PR — Owner: @python-tester
- [ ] T056 [US4] Manually launch `python -m cabal` on Windows and walk every active screen (Home → README, Init env, Update, Restore, MCP, Local, Tools, Git config, GitHub device flow). Confirm no Textual error appears and every screen closes back to Home — Owner: main
- [ ] T057 [US5] Run `python setup/build/build_exe.py`. Confirm the produced binary at `setup/build/dist/cabal[.exe]` exists, is non-empty, and boots to the HomeScreen identically to `python -m cabal`. Quit cleanly — Owner: main
- [X] T058 Verify module-size budget: `find setup/src/cabal -name "*.py" -exec wc -l {} \; | sort -nr | head -20` shows no file exceeds 500 LOC without a justification comment at the top (FR-2 + SC-2). `setup/src/cabal/wizard.py` < 200 LOC (SC-1). Add a justification comment at the top of any module that exceeds 500 LOC — Owner: @python-architect
- [X] T059 Run `@code-plan-verifier` against the branch with the plan + this tasks file as the agreed plan. Expect verdict PASS or PASS WITH WARNINGS. If FAIL: fix the called-out items in new commits, then re-run — Owner: @code-plan-verifier
- [X] T060 Update CLAUDE.md (already done by `/speckit-plan`) so the SPECKIT block points at this feature; add a one-line entry to the "Previously shipped" list when the refactor merges to main — Owner: main

**Checkpoint**: All success criteria (SC-1 through SC-6) met. Branch ready to merge.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no deps; start immediately.
- **Phase 2 (Foundational contract test)**: needs Phase 1. **BLOCKS every extraction.** The contract test MUST pass against current code before T007.
- **Phase 3 (leaves)**: needs Phase 2. Sequential — every task edits `wizard.py`.
- **Phase 4 (mid layer)**: needs Phase 3. Sequential.
- **Phase 5 (US1 — installers)**: needs Phase 4. Sequential.
- **Phase 6 (US2 — widgets + screens)**: needs Phase 5 (widgets reach into `cabal.tools`). Sequential.
- **Phase 7 (app + facade)**: needs Phase 6 (`app.py` imports every screen). Sequential.
- **Phase 8 (polish)**: needs Phase 7. T053–T055 can run in parallel `[P]`; T056–T060 are sequential validation steps.

### User Story Dependencies

- **US1 (installer maintenance)**: needs Phases 1–5.
- **US2 (screen maintenance)**: needs Phases 1–6.
- **US3 (smoketest parity)**: validated continuously from Phase 2 onward; final check in T052/T055.
- **US4 (console-script parity)**: validated in T056.
- **US5 (PyInstaller parity)**: validated in T053, T057.

### Within Each Extraction Task

Every extraction task follows the same sub-recipe:
1. Cut the named symbols out of `wizard.py`.
2. Paste them into the new module file.
3. Fix imports inside the new module (use `cabal.<dep>` for every other cabal submodule it touches).
4. Add `from cabal.<new_module> import <names>` to `wizard.py` (preserving facade compatibility).
5. Re-run `python -m pytest tests/contract/test_wizard_public_api.py -v` — must pass.
6. Re-run `python setup/tools/_smoketest.py` — must match `tests/contract/_baseline_smoketest.txt` byte-for-byte for the import block (component counts, etc.).
7. Commit with subject `task: extract <module> from wizard` (imperative mood, ≤72 chars; per global CLAUDE.md commit conventions).

### Parallel Opportunities

- **Phase 1**: T003 can run in parallel with T002 (independent checks).
- **Phase 8**: T053, T054, T055 can run in parallel `[P]` — three different files, no shared state.
- **Every other extraction task is sequential** (Gate 6 — all extractions edit `wizard.py`).

---

## Parallel Example: Phase 8 Polish

```bash
# Three tasks, three different files, no inter-dependencies:
Task T053: Update setup/build/cabal.spec hiddenimports
Task T054: Update setup/build/README.md references
Task T055: Final contract-test re-run on clean checkout
```

No other phase in this feature has parallel opportunities — concurrent edits to `wizard.py` would collide.

---

## Implementation Strategy

### MVP First — User Story 1 (Installer Modularization)

Phases 1 → 2 → 3 → 4 → 5 give the maintainer a clean home for every installer. After Phase 5, adding a new tool is a single-file change. The TUI hasn't been touched yet — it still works via `wizard.py`'s re-exports.

### Incremental Delivery

1. Phases 1–4 → leaf + mid layer modules → no user-visible change, contract test green.
2. Phase 5 → US1 delivered (maintainers can add installers cleanly). Demo: add a stub `dummy_install` in a new file, register in `TOOLS`, watch it appear in the Tools screen.
3. Phase 6 → US2 delivered (maintainers can add screens cleanly). Demo: open every screen.
4. Phase 7 → `wizard.py` shrinks to facade. SC-1 met.
5. Phase 8 → packaging parity verified. US4 + US5 met.

### Solo-Developer Strategy (default for this feature)

One developer / one main thread / one `@python-architect` dispatch per task. Sequential. Each task ships in its own commit. Contract test gates every commit. Total: ~60 sequential commits on `005-cabal-tools-polish`.

---

## Notes

- Every extraction edits `setup/src/cabal/wizard.py`. No two extraction tasks can run concurrently without colliding. **`Parallel: yes` is NEVER used in this feature.**
- The contract test (`tests/contract/test_wizard_public_api.py`) is the safety net: it must pass after every commit on this branch. If it goes red, revert the last commit before continuing.
- `wizard.py` shrinks monotonically across Phases 3–7. After T051 it is a re-export facade.
- The CSS blob in `CabalApp.CSS` is **moved as-is** in T050 with no edits — preserve every character (per FR-5 + research.md R2).
- Do not rename any public symbol during extraction. Renames belong to a separate commit (or feature) and are forbidden by Constitution Principle II's "no incidental cleanup" spirit.

---
---

# Part B Tasks — Init Project + Project MCP + Claude Stats Panel (Extended 2026-05-28)

Adds the Init Project flow (US6–US10), Claude stats panel (US11), and `.mcp.json` gitignore guarantee (FR-17) on top of the Part A refactor. Part A facade and contract test (T004/T005) remain the safety net — every Part B task that touches `cabal.wizard`'s re-export list or `cabal.mcp_ops` MUST keep the contract test green.

**Parallel Execution Map**: still **N/A** per plan.md — Part B work is dispatched sequentially. `[P]` markers within a phase indicate same-phase parallelizability (different files, no shared state) but `/speckit-implement` still dispatches one writer at a time.

## Phase 9: Part B Foundational (claude_cli helper + test infra)

**Status**: ✅ Complete (4/4 — T061–T064)
**Purpose**: Pull shared `_run_claude_cli` into its own module so both `mcp_ops` and the new Init Project Apply step reuse the MSYS-shim wrapper; create the `tests/` tree for Part B's unit + integration tests.

**⚠️ CRITICAL**: T062/T063 keep the existing `cabal.wizard.enumerate_mcp_servers` / `claude_mcp_add_from_template` / `claude_mcp_remove` re-exports working. Re-run `tests/contract/test_wizard_public_api.py` (T005) after each — must stay green.

- [X] T061 Create directory tree `tests/unit/`, `tests/integration/`, `tests/fixtures/` each with an empty `__init__.py` placeholder; ensure `tests/conftest.py` exists at repo root with a `tmp_project_dir` fixture that yields a fresh `Path(tempfile.mkdtemp())` and removes it on teardown — Owner: main
- [X] T062 Extract `_run_claude_cli` from `setup/src/cabal/mcp_ops.py` (current lines 40–52) into new file `setup/src/cabal/claude_cli.py`. Add a `claude_print(prompt, cwd, on_line=None, timeout=None) -> ClaudeRunResult` helper that uses `subprocess.Popen` so the caller can `.terminate()` it (R10). Export both names — Owner: @python-architect
- [X] T063 Update `setup/src/cabal/mcp_ops.py` to `from cabal.claude_cli import _run_claude_cli` (remove the local definition). Re-run `pytest tests/contract/test_wizard_public_api.py -v` — Owner: @python-architect
- [X] T064 Add `setup/src/cabal/claude_cli.py` to the `hiddenimports` list in `setup/build/cabal.spec` (additive — keep all existing entries) — Owner: main

**Checkpoint**: `cabal.claude_cli` is the single home of the MSYS-shimmed Claude CLI wrapper; `mcp_ops` re-imports it; contract test still passes.

---

## Phase 10: User Story 6 — Init/Open Project entries on HomeScreen 🎯 MVP

**Status**: ✅ Complete (3/3 — T065–T067)
**Goal**: HomeScreen gains two new buttons: "Init new project" (launches the new InitProjectScreen) and "Open existing project" (folder picker → LocalScreen pre-pointed at picked dir).

**Independent test**: Boot `python -m cabal`; HomeScreen renders both new buttons under a "Project" section; clicking "Open existing project" launches the folder picker and on selection pushes `LocalScreen`; clicking "Init new project" pushes the (stub) `InitProjectScreen`. No regression on existing buttons.

- [X] T065 [US6] Update `setup/src/cabal/views/home.py`: add a new "Project" `Vertical(classes="home-section")` block with two buttons (`#btn-op-init`, `#btn-op-open-project`); add their handler entries to `on_button_pressed`; do NOT remove or rearrange any existing button. Lazy-import `InitProjectScreen` and `FolderBrowserScreen` inside the handler body (per R5) — Owner: @python-architect
- [X] T066 [US6] In `setup/src/cabal/views/home.py`, implement `_open_existing_project()`: push `FolderBrowserScreen(Path.cwd())` with a callback that, on a non-None Path, pushes `LocalScreen()` and then sets the `#loc-path` Input to the picked path. (LocalScreen reads `Path.cwd()` by default — adding a one-line `_seed_path` override on the new push is acceptable; do NOT change LocalScreen's constructor signature outside this one optional arg.) — Owner: @python-architect
- [X] T067 [US6] Create stub file `setup/src/cabal/views/init_project.py` with a minimal `InitProjectScreen(Screen)` that composes `AppHeader` + a `Static("Init Project — coming soon")` + a Back button. Register the screen via a top-level import in `setup/src/cabal/app.py` so PyInstaller's analyzer follows the edge (per R6) — Owner: @python-architect

**Checkpoint**: HomeScreen has the two new entry points and they navigate; the rest of the wizard is unchanged.

---

## Phase 11: User Story 7 + 9 — GitHub Template Fetcher + Local Fallback + Files Preview

**Status**: ✅ Complete (7/7 — T068–T074)
**Goal**: InitProjectScreen lets the user pick a template (GH template repo OR local), stages every file as an `InjectableFile`, and shows them in a per-row-toggleable preview table.

**Independent test**: With `gh` authed + ≥1 template repo: launch InitProjectScreen, pick parent + name, pick a GH template, see the files table populate from the extracted tarball, uncheck a row. Without `gh`: same flow auto-falls-back to local templates; picking `python` shows the scaffold rows (CLAUDE.md + .claude/ skeleton + .gitignore).

### Contracts (test before implementation — Constitution III)

- [X] T068 [P] [US7] Write `tests/unit/test_gh_templates.py`: mock `subprocess.run(["gh", "repo", "list", ...])` to return a fixture JSON; assert `list_user_templates()` filters `isTemplate == true`, drops entries missing `defaultBranchRef`, parses owner/name/branch correctly; assert `JSONDecodeError` is surfaced as `RuntimeError` with the original cause; assert missing `isTemplate` field (older `gh`) returns `[]` not raises. Per contracts/gh-cli.md C1 — Owner: @python-tester
- [X] T069 [P] [US9] Write `tests/unit/test_init_project_service.py`: build fixture tarballs at `tests/fixtures/safe.tar.gz` (one file at relative path), `tests/fixtures/unsafe_dotdot.tar.gz` (`../escape.txt`), `tests/fixtures/unsafe_abs.tar.gz` (`/etc/passwd`), `tests/fixtures/unsafe_symlink.tar.gz`. Assert `_validate_safe(tar)` raises on the three unsafe variants and passes on the safe one (per research.md R14) — Owner: @python-tester

### Implementation

- [X] T070 [P] [US7] Create `setup/src/cabal/gh_templates.py` with `@dataclass GitHubTemplateRef(owner, name, description, default_branch, url, is_template)`, `list_user_templates() -> list[GitHubTemplateRef]` (calls `gh repo list --json isTemplate,name,owner,description,defaultBranchRef,url --limit 200`), and `download_tarball(ref) -> Path` (uses `gh api repos/<owner>/<name>/tarball/<branch>` streaming to `tempfile.NamedTemporaryFile`, returns the extracted dir from `tempfile.mkdtemp(prefix="cabal-tpl-")`). Per contracts/gh-cli.md C1+C2 — Owner: @python-architect
- [X] T071 [P] [US9] Create `setup/src/cabal/init_project_service.py` with `@dataclass LocalTemplateRef`, `@dataclass InjectableFile` (with `__post_init__` validation per data-model I-5: refuse absolute `dest_relpath`, refuse `..` segments), `_validate_safe(tar)` (per R14), `enumerate_local_template_files(stem) -> list[InjectableFile]` (includes the CLAUDE.md, .claude/ skeleton, and matching gitignore preset), `enumerate_github_template_files(extract_dir) -> list[InjectableFile]` — Owner: @python-architect
- [X] T072 [US7][US9] Replace the stub `InitProjectScreen` body in `setup/src/cabal/views/init_project.py` with the full `compose()`: parent-folder picker (Browse button + Input), project-name Input, template-source RadioSet (`github` / `local`), template OptionList, `[Edit Project MCP…]` Button (disabled until template picked), files DataTable with checkbox column + total-files / total-bytes summary, `[Apply]` / `[Cancel]` buttons, status Static. Validate project name against `^[A-Za-z0-9._-]{1,64}$` + Windows-reserved-name denylist (per research.md R12); disable Apply when invalid — Owner: @python-architect
- [X] T073 [US7] Wire the GitHub template path in `InitProjectScreen`: on mount, `run_worker(self._fetch_gh_templates, thread=True)`; populate OptionList; on row select, `run_worker(self._download_and_stage, thread=True)` → populate the files table from `enumerate_github_template_files(extract_dir)`. Surface every failure mode (no gh, not authed, network, parse) as a yellow status line per contracts/gh-cli.md C1 "Our handling" — Owner: @python-architect
- [X] T074 [US7] Wire the Local fallback in `InitProjectScreen`: when the gh worker returns empty OR errors, pre-select the `local` RadioButton, populate OptionList from `sorted((GLOBAL_DIR / "project-templates").glob("*.md"))` (same enumeration as `LocalScreen`), and on row select populate the files table from `enumerate_local_template_files(stem)` — Owner: @python-architect

**Checkpoint**: Files preview table populates from either source; user can uncheck rows; no Apply implemented yet.

---

## Phase 12: User Story 8 — Project MCP Screen

**Status**: ✅ Complete (3/3 — T075–T077)
**Goal**: A `ProjectMcpScreen` shows all MCP scopes via `enumerate_mcp_servers()` but only allows toggling rows in the `project` / `template` scope. Plugin and user rows are read-only.

**Independent test**: From InitProjectScreen after picking a template, click `[Edit Project MCP…]` → ProjectMcpScreen opens against the planned target dir; toggle a template-scope server on; back to InitProjectScreen; Apply → `<target>/.mcp.json` contains the toggled entry under `mcpServers`.

- [X] T075 [P] [US8] Create `setup/src/cabal/views/project_mcp.py` with `ProjectMcpScreen(Screen)` that takes a `target_dir: Path` constructor arg. Reuses `enumerate_mcp_servers()` for rows. Renders plugin/user-scope rows with a `(read-only)` suffix and suppresses the toggle action when `info["scopes"]` intersects `{"plugin", "user"}` but does NOT contain `"project"`. Toggle on a template-scope server writes to `<target_dir>/.mcp.json` per contracts/mcp-json.md (atomic via temp-file + `os.replace`). Toggle off removes the entry — Owner: @python-architect
- [X] T076 [P] [US8] Write `tests/integration/test_project_mcp_screen.py` using Textual `App.run_test()`: mount the screen against a `tmp_project_dir`; assert plugin/user rows have a `(read-only)` token in their rendered text; toggle a template row → assert `<target>/.mcp.json` parses and contains the entry under `mcpServers.<name>` with the expected `command` / `args` / `env`; toggle off → entry gone; round-trip via `enumerate_mcp_servers()` shows `"project" in scopes` (per contracts/mcp-json.md "Round-trip safety") — Owner: @python-tester
- [X] T077 [US8] Wire the `[Edit Project MCP…]` button on `InitProjectScreen` to push `ProjectMcpScreen(target_dir=parent / name)`. The target dir does not yet exist on disk at this point — `ProjectMcpScreen` creates the parent dirs lazily on first toggle (mkdir(parents=True, exist_ok=True) before write). When the screen pops, refresh the InitProjectScreen's "Project MCP entries: N" badge — Owner: @python-architect

**Checkpoint**: ProjectMcpScreen edits `<target>/.mcp.json`; plugin/user rows are non-toggleable; integration test passes.

---

## Phase 13: User Story 10 — Apply Step (file injection + Claude CLI invocation + gitignore)

**Status**: ✅ Complete (8/8 — T078–T085)
**Goal**: InitProjectScreen.Apply creates the target dir, writes every selected `InjectableFile`, writes `.mcp.json` if any MCP entries are staged, ensures `.mcp.json` is in `.gitignore` (FR-17), writes `<target>/.claude/INIT_PROMPT.md`, and finally invokes `claude -p` with cwd at the new project.

**Independent test**: Walk quickstart.md P1 — pick GH template, toggle a project MCP, Apply → project dir populated, `.mcp.json` contains the MCP entry, `.gitignore` contains `.mcp.json` exactly once, `INIT_PROMPT.md` present in `.claude/`, claude was invoked (or yellow fallback message if not on PATH).

- [X] T078 [US10] Implement `InitProjectScreen.action_apply` validation pre-flight: confirm project name regex + Windows-reserved-name denylist (research.md R12); confirm `target_dir = parent / name` does not exist OR exists empty (FR-13 relaxed — empty or only .mcp.json present, since ProjectMcpScreen writes .mcp.json before Apply); show red status and abort otherwise. Move every subsequent write inside a try/except that surfaces the first failure to the status pane without partial cleanup (NFR-8) — Owner: @python-architect
- [X] T079 [US10] Implement file writes in `setup/src/cabal/init_project_service.py: apply_plan(plan)`: mkdir target_dir, then for each `selected=True` InjectableFile: re-validate dest path stays inside target_dir (data-model I-5: `Path(dest).resolve().relative_to(target_dir.resolve())`), mkdir parents, copy bytes with `shutil.copy2`. Skip un-checked rows. Wire `action_apply` to call it — Owner: @python-architect
- [X] T080 [US10] `<target>/.mcp.json` is written incrementally by `ProjectMcpScreen._write_project_mcp` (atomic via temp + os.replace + json round-trip) — Apply only counts entries via `count_project_mcp_entries(target)` — Owner: @python-architect
- [X] T081 [US10] Implement gitignore appender `init_project_service.ensure_mcp_gitignored(target_dir)` per contracts/mcp-json.md "Gitignore obligation": create `.gitignore` with `.mcp.json\n` if absent; append on its own line if missing; idempotent (re-run = no-op). Call from `action_apply` unconditionally — even when no MCP toggled — so the rule is established before any future toggle (per spec FR-17). Then run `git ls-files --error-unmatch .mcp.json` in target_dir; on exit 0, surface a yellow warning `".mcp.json was already tracked by git in this repo — run 'git rm --cached .mcp.json' to stop tracking it."` — Owner: @python-architect
- [X] T082 [US10] Create `setup/src/cabal/views/init_project_prompt.py` with `build_init_prompt(target_dir, template_attribution, files_written, agents, skills, commands) -> str` + `write_init_prompt(target_dir, prompt_text)`. Persists `<target>/.claude/INIT_PROMPT.md` — Owner: main
- [X] T083 [US10] Invoke Claude in `action_apply`: when `shutil.which("claude")` is truthy, `run_worker(self._apply_worker, thread=True, exclusive=True)` → reads the in-memory prompt and calls `spawn_claude(["-p", prompt], cwd=target_dir)` so we hold the Popen handle for Cancel. Stream stdout line-by-line into the status pane via `call_from_thread`. Exit ≠ 0 surfaces yellow `claude exited <N> — review .claude/ manually` (NFR-8). Exit 0 surfaces green `claude finished`. When `claude` missing: skip with yellow `"claude CLI not installed — skipping architecture step. Install from Tools screen."` (FR-15) — Owner: @python-architect
- [X] T084 [US10] Add a `[Cancel]` button to `InitProjectScreen` that terminates the active `claude` Popen if one exists and surfaces `[yellow]cancelled[/yellow]`. The file-write step is NOT cancellable mid-write — only the claude invocation — Owner: @python-architect
- [X] T085 [P] [US10] Write `tests/integration/test_init_project_screen.py`: 19 tests covering `apply_plan` (file writes, scaffold, parent-dir creation, unselected skip), `ensure_mcp_gitignored` (create, idempotent, append, no-dup, git-tracked detection), `count_project_mcp_entries`, INIT_PROMPT.md builder + writer, and screen source smoke checks (apply_worker wired, only-mcp.json target check, no credential-shaped literals). All green; combined suite 178 passed — Owner: @python-tester

**Checkpoint**: End-to-end Init flow works for both template sources; `.mcp.json` gitignored; claude invocation gated correctly.

---

## Phase 14: User Story 11 — Claude Stats Panel

**Status**: ✅ Complete (4/4 — T086–T089)
**Goal**: A nested `ClaudeStatsPanel` widget renders below `EnvPanel` on `HomeScreen` showing account type, signed-in email, plan usage, active model. Refreshable via `Ctrl+S`. Never leaks tokens.

**Independent test**: Boot `python -m cabal`; HomeScreen renders the panel within 3 s with account fields populated (when `claude` is on PATH and signed in). Press `Ctrl+S` → re-fetches. With `claude` missing, panel renders without error and shows `claude CLI not installed` plus the email from `~/.claude.json` if present.

- [X] T086 [P] [US11] Create `setup/src/cabal/widgets/claude_stats_panel.py` with `@dataclass ClaudeAccountStatus` and `ClaudeStatsPanel(Widget)`. `on_mount` dispatches `run_worker(self._refresh_worker, thread=True, exclusive=True)`. `Ctrl+S` binding handled on HomeScreen; `[Refresh]` button on the widget. Renders account type, email, 5-hour/weekly %, active model, token presence (`✓ token present` / `✗ no token`) — Owner: @python-architect
- [X] T087 [P] [US11] Implement `parse_status(stdout: str) -> ClaudeAccountStatus` with regex set from contracts/claude-cli.md C2 (longest-plan-match ordering: Max 20x > Max 5x). When nothing parses, `raw_status_output` is populated. Implement `read_claude_dot_json_fallback()` reading `oauthAccount.emailAddress` + `organizationUuid` (presence only, no value). UI updates routed through `call_from_thread` — Owner: @python-architect
- [X] T088 [P] [US11] Write `tests/integration/test_claude_stats_panel.py` with 12 tests covering: full happy-path parse, Pro/Max 5x/Max 20x ordering, partial parse, garbage→raw_status_output, signed_in heuristic, ~/.claude.json fallback (email + token_present), missing/corrupt JSON, dataclass-field allowlist (token-leak guarantee), rendered-text token-shape regex check, raw-verbatim documented behavior — Owner: @python-tester
- [X] T089 [US11] Mount `ClaudeStatsPanel(id="claude-stats")` in `setup/src/cabal/views/home.py`'s `compose()` immediately after `EnvPanel(id="env-summary")`. Added `Binding("ctrl+s", "refresh_claude_stats", "Refresh stats")` + `action_refresh_claude_stats()` handler. No Textual layout regression — existing buttons + bindings preserved — Owner: @python-architect

**Checkpoint**: HomeScreen has the new panel; tokens never leak into the rendered output; refresh works.

---

## Phase 15: FR-17 — `GITIGNORE_BY_TEMPLATE` Preset Alignment

**Status**: ✅ Complete (1/1 — T090)
**Goal**: Every entry in the existing `GITIGNORE_BY_TEMPLATE` dict in `cabal/views/folder_browser.py` lists `.mcp.json`, so template-driven first-write already contains the entry (FR-17 + contracts/mcp-json.md "Preset alignment").

- [X] T090 Update `setup/src/cabal/views/folder_browser.py`: in each of the six `GITIGNORE_BY_TEMPLATE` entries (`python`, `dotnet`, `frontend`, `monorepo`, `unity`, `other`), add a `.mcp.json` line under an `# MCP (project-scope; may contain env-var values)` header section. Idempotent with T081 — the `ensure_mcp_gitignored` appender becomes a no-op when the preset already includes the line — Owner: @python-architect

**Checkpoint**: A user picking a local template at LocalScreen (existing flow) gets `.mcp.json` ignored from the very first commit — no second pass needed.

---

## Phase 16: Part B Polish & Final Validation

**Status**: 🟡 In progress (5/8 — T091–T098; T094/T095/T096 deferred for the maintainer to walk on Windows with cabal installed)
**Purpose**: PyInstaller wiring, smoketest re-baseline, manual TUI walks, build verification, module-size budget audit, plan-verifier gate.

- [X] T091 [P] Update `setup/build/cabal.spec` `hiddenimports`: add `"cabal.claude_cli"`, `"cabal.gh_templates"`, `"cabal.init_project_service"`, `"cabal.views.init_project"`, `"cabal.views.init_project_prompt"`, `"cabal.views.project_mcp"`, `"cabal.widgets.claude_stats_panel"`. Additive — keep every existing entry from T053 — Owner: main
- [X] T092 [P] Register top-level imports of `InitProjectScreen`, `ProjectMcpScreen`, `init_project_prompt` in `setup/src/cabal/app.py` (per R6, so PyInstaller's static analyzer follows the graph). `ClaudeStatsPanel` is mounted via `views/home.py` import — no separate app.py entry needed — Owner: @python-architect
- [X] T093 [P][US3] Smoketest diff against baseline shows only a `hooks/ new=` count change driven by an unrelated `global/hooks/` working-tree edit; component count is identical (12) and every other line matches. `pytest tests/contract/test_wizard_public_api.py -v` → 130 passed (Part A facade invariant I-1 holds) — Owner: @python-tester
- [ ] T094 [US10] Manual walk of quickstart.md P1 (GH template happy path) on the maintainer's machine with `gh` authed + `claude` installed. Record outcome in the PR — Owner: main *(deferred — requires interactive Windows TUI session)*
- [ ] T095 [US10] Manual walk of quickstart.md P2 (offline local-template fallback) by temporarily hiding `gh` from PATH. Record outcome in the PR — Owner: main *(deferred — requires interactive Windows TUI session)*
- [ ] T096 [US11] Manual walk of quickstart.md P6 (Claude stats panel) both with and without `claude` on PATH. Inspect rendered output for any token-shaped string. Record outcome in the PR — Owner: main *(deferred — requires interactive Windows TUI session)*
- [X] T097 Module-size budget audit (Part B additions): every Part B module is well under 500 LOC. Max = `views/init_project.py` at 434 LOC. Other Part B files: `claude_cli.py` 108, `gh_templates.py` 95, `init_project_service.py` 203, `views/init_project_prompt.py` 47, `views/project_mcp.py` 215, `widgets/claude_stats_panel.py` 178. `wizard.py` facade at 196 (< SC-1 cap of 200) — Owner: @python-architect
- [X] T098 `@code-plan-verifier` audit: verdict **PASS WITH WARNINGS**. Plan-compliance checklist green for every FR-7…FR-17, all invariants I-1/I-3/I-5/I-6/I-7/I-8/I-9 hold, all constitution gates resolved. Warnings: (1) unrelated `global/settings.json` + `global/hooks/session_end.py` working-tree changes predate Part B and should be committed separately; (2) smoketest baseline drift is data-only (`hooks/ new=` count), not a refactor regression — baseline can be regenerated after the unrelated `global/hooks/` decision is finalised — Owner: @code-plan-verifier

**Checkpoint**: All Part B success criteria (SC-7 through SC-14) met. Branch ready to merge.

---

## Part B — Dependencies

- **Phase 9** (foundational): no deps; can start immediately after the existing Part A branch tip.
- **Phase 10** (US6): needs Phase 9 (uses `claude_cli` indirectly via the stub).
- **Phase 11** (US7 + US9): needs Phase 10 (stub screen exists); T068–T071 within the phase are `[P]` (4 distinct files). T072–T074 are sequential (all edit `init_project.py`).
- **Phase 12** (US8): needs Phase 10's stub registration in `app.py`. T075/T076 are `[P]` (different files).
- **Phase 13** (US10): needs Phases 11 + 12 (consumes the screens + the service). All Apply tasks edit `init_project.py` or `init_project_service.py` — sequential. T085 (test file) is `[P]`.
- **Phase 14** (US11): independent of Phases 10–13 (touches HomeScreen + new widget). Could in principle run after Phase 9. T086–T088 are `[P]` (different files), T089 sequential.
- **Phase 15** (FR-17 presets): independent of Phases 10–14 (one-file edit). Can land any time after Phase 9.
- **Phase 16** (polish): needs every Part B phase complete.

### Within Each Part B Phase

- Contract / unit tests (when listed) MUST be written first and observed failing (Constitution III for the `_validate_safe` and `list_user_templates` contracts; not strictly binding for everything else but the discipline is recommended).
- Same-file edits stay sequential even when both tasks carry `[P]` — `[P]` means same-phase, different-file.

### Parallel Opportunities (Part B)

- **Phase 11**: T068, T069, T070, T071 — 4 different files.
- **Phase 12**: T075, T076.
- **Phase 13**: T085 alone vs T078–T084 (test file vs implementation file).
- **Phase 14**: T086, T087, T088 (widget file, parser logic in same file are sequential; test file is `[P]` vs them).
- **Phase 16**: T091, T092, T093 (build spec, app.py, smoketest re-run — three independent files).

**`Parallel: yes` is still NEVER used** — per plan.md Parallel Execution Map = N/A. `/speckit-implement` dispatches one writing agent at a time. The `[P]` markers here are informational for future humans who may want to refactor the dispatch pattern.

---

## Part B — Implementation Strategy

### MVP — User Story 6 (Init/Open Project home entries)

Phase 9 + Phase 10 alone deliver the UI surface so the user can SEE the new entries on HomeScreen and navigate to a stub. Apply still doesn't write anything until later phases — but the navigation graph is provable.

### Incremental Delivery

1. Phase 9 → shared `claude_cli` helper extracted. Internal-only.
2. Phase 10 → HomeScreen has the two new buttons; stubs in place. Demo: walk HomeScreen.
3. Phase 11 → InitProjectScreen has a real files preview. Demo: pick parent + name + template, see the preview table populate.
4. Phase 12 → Project MCP editing works. Demo: edit project MCP standalone.
5. Phase 13 → Apply writes files + invokes claude. Demo: full happy-path scaffold of a project.
6. Phase 14 → ClaudeStatsPanel on HomeScreen. Demo: launch wizard, see account info.
7. Phase 15 → Local-template gitignore presets aligned. Internal — confirms FR-17 holds across both flows.
8. Phase 16 → PyInstaller + manual walks + plan-verifier. Branch ready.

### Solo-Developer Strategy (default)

One developer / one `@python-architect` dispatch per implementation task / one `@python-tester` per test task. Sequential. Each task ships in its own commit. Total: 38 new tasks (T061–T098).
