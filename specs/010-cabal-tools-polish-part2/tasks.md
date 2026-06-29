# Tasks: Cabal Tools View Polish Part 2

**Input**: Design documents from `specs/010-cabal-tools-polish-part2/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are included because the feature contracts explicitly define expected catalog, UI, database container, version, backup, and copy behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the foundational catalog work.

## Phase 1: Setup

**Status**: Complete. Import-safe modules and baseline scaffolding are in place.

- [X] T001 Create import-safe placeholder module `setup/src/cabal/tool_catalog.py` for tool metadata dataclasses and compatibility helpers — Owner: @python-architect
- [X] T002 Create import-safe placeholder module `setup/src/cabal/installers/devtools.py` for Postman, Hugo, and Uvicorn installers — Owner: @python-architect
- [X] T003 Create import-safe placeholder module `setup/src/cabal/installers/versions.py` for runtime version providers — Owner: @python-architect
- [X] T004 Create import-safe placeholder module `setup/src/cabal/installers/runtime_backups.py` for runtime backup records and restore guidance — Owner: @python-architect

---

## Phase 2: Foundational Tool Catalog

**Status**: Complete. Catalog tests passed in the local `.venv`.

- [X] T005 [P] Add failing catalog contract tests `test_all_rendered_tools_have_metadata`, `test_all_tools_have_description_and_source_status`, and `test_source_required_tools_disable_automation` in `setup/tests/test_tools_catalog.py` — Owner: @python-tester
- [X] T006 [P] Add failing catalog safety tests `test_existing_tools_are_not_dropped` and `test_no_secret_shaped_literals_in_tool_metadata` in `setup/tests/test_tools_catalog.py` — Owner: @python-tester
- [X] T007 Define `ToolDefinition`, `ToolCategory`, `SourceStatus`, `InstallChannel`, `PlatformSupport`, and catalog validation helpers in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T008 Move existing `ENV_INSTALLERS` and `ENV_TOOL_GROUPS` row metadata into catalog definitions while preserving existing tool keys in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T009 Update `setup/src/cabal/tools.py` to derive grouped Tools rows from `setup/src/cabal/tool_catalog.py` while keeping `_installer_for`, status probes, and existing row order compatible — Owner: @python-architect
- [X] T010 Add source verification, automation-disabled, unsupported-platform, and redaction metadata validators in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T011 Update `setup/tests/test_tools_vercel_plugin.py` so the Vercel plugin smoke test reads through the catalog-backed Tools registry in `setup/src/cabal/tools.py` — Owner: @python-tester
- [X] T012 Run `python -m pytest setup/tests/test_tools_catalog.py setup/tests/test_tools_vercel_plugin.py` and fix catalog regressions in `setup/src/cabal/tool_catalog.py` or `setup/src/cabal/tools.py` — Owner: @python-tester

---

## Phase 3: User Story 1 - Understand Tools Before Installing (Priority: P1)

**Status**: Complete. Tools metadata tests passed in the local `.venv`.

**Independent Test**: Open the Tools view and verify every visible tool row has a concise description, status text, and read-more/source action or explicit source-unavailable/source-required state.

- [X] T013 [P] [US1] Add `test_tools_screen_renders_descriptions`, `test_tools_screen_renders_read_more_actions`, and `test_read_more_uses_source_url` in `setup/tests/test_tools_screen_metadata.py` — Owner: @python-tester
- [X] T014 [P] [US1] Add `test_source_required_row_disables_install_button` in `setup/tests/test_tools_screen_metadata.py` for rows such as Hermes agent in `setup/src/cabal/views/tools.py` — Owner: @python-tester
- [X] T015 [US1] Render each catalog description under the tool label in `setup/src/cabal/views/tools.py` without blocking status refresh workers — Owner: @python-architect
- [X] T016 [US1] Add read-more/source actions in `setup/src/cabal/views/tools.py` that open verified `source_url` metadata and show source-required/source-unavailable labels when automation is disabled — Owner: @python-architect
- [X] T017 [US1] Update Tools row button state mapping in `setup/src/cabal/views/tools.py` so verified, manual-only, unsupported, and source-required tools display the correct install action — Owner: @python-architect
- [X] T018 [US1] Add concise descriptions and official source URLs for all pre-existing Tools rows in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T019 [US1] Redact token-shaped source/status strings before rendering metadata in `setup/src/cabal/views/tools.py` using validators from `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T020 [US1] Run `python -m pytest setup/tests/test_tools_screen_metadata.py setup/tests/test_tools_catalog.py` and fix UI metadata regressions in `setup/src/cabal/views/tools.py` — Owner: @python-tester

---

## Phase 4: User Story 2 - Install and Detect a Broader Tool Catalog (Priority: P1)

**Status**: Complete. Expanded catalog tests passed in the local `.venv`.

**Independent Test**: Open the Tools view and verify the new sections and requested tools appear with correct category, description, source state, status, platform support, and install/manual behavior.

- [X] T021 [P] [US2] Add `test_requested_tools_are_in_expected_categories` in `setup/tests/test_tools_catalog.py` covering LM Studio, Hermes agent, OpenCode, Zed, Rider, Visual Studio, SSMS, DBeaver, Azure local tools, Postman, Hugo, and Uvicorn — Owner: @python-tester
- [X] T022 [P] [US2] Add `test_opencode_cli_and_desktop_status_are_separate` in `tests/unit/test_local_ai_tools.py` — Owner: @python-tester
- [X] T023 [P] [US2] Add `test_unsupported_platform_rows_remain_visible_and_disabled` in `setup/tests/test_tools_catalog.py` for Windows-only and platform-specific entries — Owner: @python-tester
- [X] T024 [US2] Add Local AI catalog entries for `lm-studio`, `hermes-agent`, and split OpenCode CLI/app metadata in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T025 [US2] Update OpenCode detection in `setup/src/cabal/env_detect.py` so CLI-on-PATH and desktop-app-present states are reported separately — Owner: @python-architect
- [X] T026 [US2] Add source-gated Hermes agent status and disabled/manual install behavior in `setup/src/cabal/installers/ai_clis.py` because no trusted official upstream is configured yet — Owner: main
- [X] T027 [US2] Add IDE/editor catalog entries and installers/probes for `zed`, `rider`, and `visualstudio` in `setup/src/cabal/tool_catalog.py` and `setup/src/cabal/installers/editors.py` — Owner: @python-architect
- [X] T028 [US2] Add `Database Clients` section with SSMS and DBeaver metadata, platform support, status probes, and install behavior in `setup/src/cabal/tool_catalog.py` and `setup/src/cabal/installers/databases.py` — Owner: @python-architect
- [X] T029 [US2] Add `Azure Local Tools` section for Azure SQL local, Cosmos DB emulator, and Azurite metadata/probes/install behavior in `setup/src/cabal/tool_catalog.py` and `setup/src/cabal/installers/cloud.py` — Owner: @python-architect
- [X] T030 [US2] Add `Developer Tools` section metadata for Postman, Hugo, and Uvicorn in `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T031 [US2] Implement Postman, Hugo, and Uvicorn installers/probes in `setup/src/cabal/installers/devtools.py` and wire them through `setup/src/cabal/tools.py` — Owner: @python-architect
- [X] T032 [US2] Update Tools section ordering and headings in `setup/src/cabal/tool_catalog.py` so Local AI, IDEs/Editors, Database Clients, Azure Local Tools, Developer Tools, and existing groups render predictably — Owner: @python-architect
- [X] T033 [US2] Run `python -m pytest setup/tests/test_tools_catalog.py tests/unit/test_vllm_tools.py` and fix broadened catalog regressions in `setup/src/cabal/tool_catalog.py`, `setup/src/cabal/env_detect.py`, and installer modules — Owner: @python-tester

---

## Phase 5: User Story 3 - Reliable Container-Backed Database Installs (Priority: P1)

**Status**: Complete. Database container spec tests passed in the local `.venv`.

**Independent Test**: With Docker or Podman available, run Redis, MariaDB, Turso/libSQL, Qdrant, Weaviate, and Milvus install/status flows; with the engine stopped or a port occupied, verify Cabal reports the blocking condition and does not claim success.

- [X] T034 [P] [US3] Add `test_container_service_specs_have_required_fields`, `test_database_services_declare_ports_and_volumes`, and `test_embedded_engines_are_not_marked_daemon_services` in `tests/unit/test_database_container_specs.py` — Owner: @python-tester
- [X] T035 [P] [US3] Add `test_preflight_blocks_when_container_engine_missing`, `test_port_conflict_blocks_install`, and `test_health_failure_does_not_report_success` in `tests/unit/test_database_container_specs.py` — Owner: @python-tester
- [X] T036 [P] [US3] Add `test_database_status_detects_existing_container` and `test_database_logs_and_cleanup_guidance_are_present` in `tests/unit/test_database_container_specs.py` — Owner: @python-tester
- [X] T037 [US3] Define `ContainerServiceSpec`, `ContainerPort`, `ContainerVolume`, `ContainerHealthCheck`, and `EmbeddedDatabaseSpec` in `setup/src/cabal/installers/container_services.py` — Owner: @python-architect
- [X] T038 [US3] Add container engine detection, missing/stopped-engine errors, and Docker/Podman command selection helpers in `setup/src/cabal/installers/containers.py` — Owner: @python-architect
- [X] T039 [US3] Add preflight checks for host port conflicts, container name conflicts, volume conflicts, image availability, and status detection in `setup/src/cabal/installers/container_services.py` — Owner: @python-architect
- [X] T040 [US3] Add service specs for Redis, MariaDB, Turso/libSQL, Qdrant, Weaviate, and Milvus in `setup/src/cabal/installers/databases.py` — Owner: @python-architect
- [X] T041 [US3] Add Azure SQL local, Cosmos DB emulator, and Azurite service specs or platform-aware emulator specs in `setup/src/cabal/installers/cloud.py` — Owner: @python-architect
- [X] T042 [US3] Add embedded utility specs and catalog labels for SQLite and DuckDB in `setup/src/cabal/installers/databases.py` and `setup/src/cabal/tool_catalog.py` — Owner: @python-architect
- [X] T043 [US3] Replace direct host database service install paths in `setup/src/cabal/installers/databases.py` with container-backed install/start/status/logs/cleanup command generation for service databases — Owner: @python-architect
- [X] T044 [US3] Surface container preflight, health, logs, cleanup, and existing-instance status text in `setup/src/cabal/views/tools.py` without freezing navigation — Owner: @python-architect
- [X] T045 [US3] Run `python -m pytest tests/unit/test_database_container_specs.py` and fix database container regressions in `setup/src/cabal/installers/databases.py`, `setup/src/cabal/installers/container_services.py`, and `setup/src/cabal/views/tools.py` — Owner: @python-tester

---

## Phase 6: User Story 4 - Upgrade Runtimes Safely (Priority: P2)

**Status**: Complete. Runtime version and backup tests passed in the local `.venv`.

**Independent Test**: Open a covered runtime row, confirm installed/latest options render, LTS markers only appear where upstream defines them, start an update with backup enabled, and verify the backup record exists before any install/update command runs.

- [X] T046 [P] [US4] Add `test_version_options_include_installed_when_metadata_unavailable`, `test_node_versions_mark_lts_from_upstream_status`, `test_dotnet_versions_mark_lts_and_sts`, and `test_python_versions_do_not_fake_lts` in `tests/unit/test_tool_versions.py` — Owner: @python-tester
- [X] T047 [P] [US4] Add `test_runtime_backup_record_created_before_install`, `test_backup_failure_blocks_or_requires_confirmation`, and `test_restore_hint_is_present_for_each_runtime` in `tests/unit/test_runtime_backups.py` — Owner: @python-tester
- [X] T048 [P] [US4] Add `test_version_selector_renders_for_runtime_tools` and `test_long_running_version_check_does_not_block_initial_render` in `tests/integration/test_tools_screen_versions.py` — Owner: @python-tester
- [X] T049 [US4] Implement runtime version provider dataclasses and stale/unavailable metadata results in `setup/src/cabal/installers/versions.py` — Owner: @python-architect
- [X] T050 [US4] Implement provider functions for Bun, npm, pnpm, Python, Node, and dotnet in `setup/src/cabal/installers/versions.py` with source URLs and ecosystem-specific LTS/support labels — Owner: @python-architect
- [X] T051 [US4] Implement `RuntimeBackupRecord`, safe config capture, install-channel detection, restore guidance, and redaction in `setup/src/cabal/installers/runtime_backups.py` — Owner: @python-architect
- [X] T052 [US4] Wire backup creation before install/update for Bun, npm, pnpm, Python, Node, and dotnet in `setup/src/cabal/tools.py` and the relevant installer modules under `setup/src/cabal/installers/` — Owner: @python-architect
- [X] T053 [US4] Render non-blocking version selectors and LTS/support badges for covered runtimes in `setup/src/cabal/views/tools.py` — Owner: @python-architect
- [X] T054 [US4] Run `python -m pytest tests/unit/test_tool_versions.py tests/unit/test_runtime_backups.py tests/integration/test_tools_screen_versions.py` and fix version or backup regressions in runtime modules and `setup/src/cabal/views/tools.py` — Owner: @python-tester

---

## Phase 7: User Story 5 - Copy and Inspect Tool Output (Priority: P2)

**Status**: Complete. Tools copy and Ctrl+C guard tests passed in the local `.venv`.

**Independent Test**: Select a tool description, status, version, source URL, or install error in the Tools view, press Ctrl+C or Ctrl+Shift+C, and confirm the clipboard receives the selected redacted text.

- [X] T055 [P] [US5] Add `test_tools_screen_copies_selected_description_text` and `test_tools_screen_copies_install_error_text` in `tests/integration/test_tools_screen_copy.py` — Owner: @python-tester
- [X] T056 [P] [US5] Extend `tests/integration/test_ctrl_c_quits.py` to cover Ctrl+C in the Tools view after text selection without quitting the app — Owner: @python-tester
- [X] T057 [US5] Make tool labels, descriptions, status text, version text, source URLs, and error output selectable in `setup/src/cabal/views/tools.py` — Owner: @python-architect
- [X] T058 [US5] Route Tools view selected text through existing `CabalApp.action_copy` and `copy_to_clipboard` behavior in `setup/src/cabal/app.py` without adding a Tools-only clipboard system — Owner: @python-architect
- [X] T059 [US5] Redact copied status/error/output text from Tools workers in `setup/src/cabal/views/tools.py` before it reaches clipboard-facing selection text — Owner: @python-architect
- [X] T060 [US5] Run `python -m pytest tests/integration/test_tools_screen_copy.py tests/integration/test_ctrl_c_quits.py setup/tests/test_clipboard.py` and fix copy regressions in `setup/src/cabal/views/tools.py` or `setup/src/cabal/app.py` — Owner: @python-tester

---

## Phase 8: Polish and Cross-Feature Validation

**Status**: Partially complete. Focused feature and guard suites pass; broader suite timed out locally, and specialist verifier audit was not run.

- [X] T061 Update any PyInstaller hidden imports or packaging metadata needed for new modules in `setup/build/cabal.spec` — Owner: @python-architect
- [X] T062 Update `specs/010-cabal-tools-polish-part2/quickstart.md` if implementation-specific validation commands change during buildout — Owner: main
- [X] T063 [P] Run focused feature tests from quickstart: `python -m pytest setup/tests/test_tools_catalog.py tests/unit/test_database_container_specs.py tests/unit/test_tool_versions.py tests/unit/test_runtime_backups.py tests/integration/test_tools_screen_copy.py tests/integration/test_tools_screen_versions.py` — Owner: @python-tester
- [X] T064 [P] Run existing guard tests: `python -m pytest tests/integration/test_ctrl_c_quits.py setup/tests/test_clipboard.py tests/unit/test_vllm_tools.py setup/tests/test_tools_vercel_plugin.py` — Owner: @python-tester
- [ ] T065 Run `python -m pytest setup/tests tests/unit tests/integration` and record any unrelated pre-existing failures in `specs/010-cabal-tools-polish-part2/quickstart.md` — Owner: @python-tester
- [ ] T066 Perform read-only plan compliance review against `specs/010-cabal-tools-polish-part2/spec.md`, `specs/010-cabal-tools-polish-part2/plan.md`, and this task list — Owner: @code-plan-verifier
- [X] T067 Review `git diff --stat` and `git status --short` against `specs/010-cabal-tools-polish-part2/tasks.md` and the planned feature files before handoff — Owner: main

---

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 must complete before Phase 2.
- Phase 2 blocks all user stories because the catalog is the shared source of truth for descriptions, sources, categories, status, and automation state.
- User Stories 1, 2, and 3 are all P1 and should be completed before P2 runtime/copy enhancements if scope needs to be trimmed.
- User Story 4 depends on Phase 2 and can proceed after runtime catalog rows exist.
- User Story 5 depends on User Story 1 because selectable copy text should include descriptions and source/status text.
- Phase 8 runs after all implemented stories.

### User Story Dependencies

- US1 depends on the catalog metadata from Phase 2.
- US2 depends on Phase 2 and may run after US1 tests are in place, but it should not bypass source metadata requirements.
- US3 depends on Phase 2 catalog definitions and may be implemented independently from US2 except for shared database client/Azure categories.
- US4 depends on Phase 2 and the existing runtime installer rows in `setup/src/cabal/tools.py`.
- US5 depends on US1 rendering descriptions/status text in selectable widgets.

### Suggested MVP

Complete Phases 1-5 for the first usable release: foundational catalog, descriptions/read-more, expanded requested catalog entries, and reliable container-backed database installs.

### Parallel Opportunities

- T005 and T006 can be authored independently because they add separate catalog test assertions before implementation.
- T013 and T014 can be authored independently because they target different Tools UI assertions.
- T021, T022, and T023 can be authored independently because they cover separate catalog and detection contracts.
- T034, T035, and T036 can be authored independently because they cover separate database container contract behaviors.
- T046, T047, and T048 can be authored independently because they target version, backup, and UI integration contracts.
- T055 and T056 can be authored independently because they cover copy behavior and Ctrl+C quit regression guards.

Do not dispatch multiple writing agents concurrently on the same shared worktree. If implementation uses concurrent writers for any `Parallel: yes` task, each writer must run in an isolated git worktree.

---

## Notes

- Hermes agent remains source-gated until a trusted official source URL and install channel are confirmed.
- OpenCode must model CLI and desktop app status separately because a user can have one installed without the other.
- SQLite and DuckDB must be visible in Databases but labelled as embedded/file-oriented utilities, not daemon services.
- LTS badges must only appear where upstream defines LTS/support semantics; do not invent LTS labels for Bun, npm, pnpm, or Python.
- No status, log, source, copied text, or backup record should expose token-shaped strings.
