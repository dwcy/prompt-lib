# Tasks: Cabal Web UI Overhaul — Full-Feature Desktop Workspace

**Input**: Design documents from `/specs/015-web-ui-overhaul/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Contract tests are REQUIRED (Constitution Gate 3) for the four contract surfaces (web API, jobs/SSE, action safety, shell handshake) and MUST precede their implementations. Integration/unit/frontend tests are included per the plan's testing strategy.

**Organization**: Phases 3–10 map 1:1 to spec user stories US1–US8. Within each story phase, the backend lane (`@python-architect`) and frontend lane (`@react-architect` / `@frontend-css`) are dispatched concurrently — every task in a concurrent lane carries `Parallel: yes` and is dispatched with `isolation: "worktree"`; tasks within one lane run sequentially inside that agent's single dispatch. Contract-test tasks always complete before their story's implementation lanes start.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1–US8), story phases only
- **Owner**: agent from `.specify/memory/agents.md` (plus `@frontend-tester`, noted in plan.md footnote)
- **Parallel: yes**: dispatched concurrently → `isolation: "worktree"` (Constitution Gate 6)

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (7/7 — T001–T007)
**Purpose**: Package skeletons, toolchains, and test scaffolding for backend, frontend, and shell.

- [X] T001 Create backend package skeleton setup/src/cabal/webapi/{__init__.py,routers/__init__.py} and add fastapi/uvicorn/platformdirs deps + `cabal-backend` script entry to setup/pyproject.toml — Owner: @python-architect
- [X] T002 [P] Scaffold apps/cabal-desktop Vite + React + TS app with pnpm (package.json, vite.config.ts incl. handshake-file dev proxy, tsconfig.json, index.html, src/main.tsx, src/App.tsx) plus Zustand/TanStack Query/Virtual/Zod deps — Owner: @react-architect — Parallel: yes
- [X] T003 [P] Configure Tailwind CSS v4 + Biome + base src/styles/globals.css (reset only; tokens come in T024) in apps/cabal-desktop — Owner: @frontend-css — Parallel: yes
- [X] T004 [P] Scaffold Tauri v2 shell in apps/cabal-desktop/src-tauri (tauri.conf.json, capabilities/default.json, Cargo.toml with shell/single-instance/window-state plugins, src/main.rs skeleton) — Owner: main
- [X] T005 [P] Create pytest placeholders tests/contract/test_webapi_{envelope,modules,jobs_sse,action_safety,handshake}_contract.py — Owner: @python-tester
- [X] T006 [P] Configure Vitest + React Testing Library + MSW in apps/cabal-desktop (vitest.config.ts, tests/setup.ts, one passing smoke test) — Owner: @frontend-tester
- [X] T007 [P] Configure Playwright scaffold apps/cabal-desktop/tests/e2e (playwright.config.ts, fixture-backend launcher stub) — Owner: @frontend-tester

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (21/21 — T008–T028)
**Purpose**: Contract tests for all four surfaces, then the backend core (security, envelope, jobs, actions, audit) and frontend core (client, shell, shared components) that every module needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. T008–T011 MUST be written and observed failing before T012+.

### Contract tests (write first, observe failing)

- [X] T008 [P] Envelope + auth contract tests per contracts/web-api.contract.md (v2 envelope shape, 401 on missing bearer, 405 on mutating verbs, redaction assertion #4) in tests/contract/test_webapi_envelope_contract.py — Owner: @python-tester
- [X] T009 [P] Handshake contract tests per contracts/desktop-shell.contract.md (atomic write, owner-only perms, stale-pid replacement, shutdown removes file) in tests/contract/test_webapi_handshake_contract.py — Owner: @python-tester
- [X] T010 [P] Action-safety contract tests per contracts/action-safety.contract.md (all 6 minimum assertions: prepare/execute, digest drift 409, ticket reuse/expiry, registry self-check, redacted previews, zero-write GET sweep) in tests/contract/test_webapi_action_safety_contract.py — Owner: @python-tester
- [X] T011 [P] Jobs/SSE contract tests per contracts/jobs-and-streams.contract.md (all 6 minimum assertions: lifecycle, cancel, Last-Event-ID replay/gap, stream redaction, restart persistence, job_conflict) in tests/contract/test_webapi_jobs_sse_contract.py — Owner: @python-tester

### Backend core lane

- [X] T012 Move setup/src/cabal/web/redaction.py → setup/src/cabal/redaction.py as the single shared rule set (extend patterns per action-safety contract; leave a re-export shim in web/redaction.py so legacy web keeps working) — Owner: @python-architect — Parallel: yes
- [X] T013 Implement SQLite bootstrap in setup/src/cabal/webapi/storage.py (platformdirs user-data dir, jobs/tickets/audit/diagnostics tables, migrations-on-open) — Owner: @python-architect — Parallel: yes
- [X] T014 Implement setup/src/cabal/webapi/security.py (token generation, atomic handshake file write/remove with owner-only ACL, ephemeral-port bind helper, FastAPI auth dependency, locked CORS) — Owner: @python-architect — Parallel: yes
- [X] T015 Implement setup/src/cabal/webapi/envelope.py (SnapshotEnvelope v2 + ModuleHealth pydantic models, precondition-digest helpers, redaction-at-boundary serializer) — Owner: @python-architect — Parallel: yes
- [X] T016 Implement setup/src/cabal/webapi/jobs.py (JobManager state machine, ring buffer, SSE publishers with seq/heartbeat/gap, exclusive-resource conflict, SQLite persistence via storage.py) — Owner: @python-architect — Parallel: yes
- [X] T017 Implement setup/src/cabal/webapi/actions.py (ActionDescriptor registry, params validation, prepare→ConfirmationTicket with EffectPreview + digest, execute with recompute/409/410/single-use, job creation) — Owner: @python-architect — Parallel: yes
- [X] T018 Implement setup/src/cabal/webapi/audit.py (AuditEntry writes on execute, DiagnosticEvent persistence + in-memory feed, diagnostics SSE source) — Owner: @python-architect — Parallel: yes
- [X] T019 Implement setup/src/cabal/webapi/app.py create_app() + routers/system.py (health with 22 ModuleHealth rows, diagnostics list/stream, jobs list/get/cancel, system.shutdown incl. service_supervisor.shutdown_all) + __main__.py entrypoint (--project, uvicorn runner, handshake lifecycle) — Owner: @python-architect — Parallel: yes

### Frontend core lane (concurrent with backend core lane)

- [X] T020 Implement typed API client in apps/cabal-desktop/src/api/ (fetch wrapper with bearer auth + handshake config, Zod schemas for envelope v2/ModuleHealth/Job/Ticket, schema-version guard with refresh prompt) — Owner: @react-architect — Parallel: yes
- [X] T021 Implement Zustand stores in apps/cabal-desktop/src/stores/ (projectContext, uiPrefs w/ persisted last-module, jobTray) — Owner: @react-architect — Parallel: yes
- [X] T022 Implement SSE client hook in apps/cabal-desktop/src/lib/sse.ts (fetch-stream with Authorization header, Last-Event-ID reconnect, heartbeat staleness, gap surfacing) — Owner: @react-architect — Parallel: yes
- [X] T023 Implement app shell in apps/cabal-desktop/src/App.tsx + src/components/shell/ (grouped sidebar nav for all 22 modules, connectivity/health strip, reconnecting state, module router with per-module error boundaries + retry) — Owner: @react-architect — Parallel: yes
- [X] T024 Design tokens + dark operational theme in apps/cabal-desktop/src/styles/ (CSS custom properties, Tailwind v4 theme, canonical loading/empty/error/disabled/stale state visuals, density scale, narrow-width behavior) — Owner: @frontend-css — Parallel: yes
- [X] T025 Shared components in apps/cabal-desktop/src/components/ (VirtualDataTable via TanStack Virtual, StatePill, EmptyState, DetailDrawer, DiffView, LogStream, JobPane, ConfirmDialog rendering full EffectPreview incl. removals/backup) — Owner: @react-architect — Parallel: yes
- [X] T026 MSW handler library + component tests for envelope guard, ConfirmDialog prepare/execute flow (incl. 409 re-review path), JobPane stream states in apps/cabal-desktop/tests/ — Owner: @frontend-tester

### Desktop shell core (after both lanes merge)

- [X] T027 Implement sidecar lifecycle in apps/cabal-desktop/src-tauri/src/main.rs (adopt-live-backend check via handshake+health, spawn `cabal-backend` sidecar, bounded handshake wait, inject port/token into webview, shutdown ordering with grace-window kill per contracts/desktop-shell.contract.md) — Owner: main
- [X] T028 Wire single-instance (focus existing window) + window-state persistence + capabilities (shell sidecar execute permission) in apps/cabal-desktop/src-tauri/ — Owner: main

**Checkpoint**: Foundation ready — envelope/auth/jobs/actions/handshake contract tests green; shell opens with connectivity strip against a live backend.

---

## Phase 3: User Story 1 - One Desktop Workspace for Everything (Priority: P1) 🎯 MVP

**Status**: ⬜ Pending (0/10 — T029–T038)
**Goal**: Project gate, full navigation, aggregated overview, project dashboard, diagnostics — every module reachable (stubs show honest empty states until their phase lands).

**Independent Test**: Launch desktop app → gate offers recents/browse/clone/new → workspace opens with all 22 nav entries, live overview/dashboard/diagnostics, per-module independent loading, auto-reconnect after backend kill.

- [ ] T029 [P] [US1] Contract tests for /api/project (+recents), /api/overview, /api/dashboard sections, project.select action in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T030 [US1] Implement routers/projects.py core: recents via cabal.recent_projects (dead-path pruning), project context get, `project.select` action descriptor in setup/src/cabal/webapi/routers/projects.py — Owner: @python-architect — Parallel: yes
- [ ] T031 [US1] Implement /api/overview aggregation + /api/dashboard per-section endpoints (dashboard_git/github/supabase/vercel services, widget_cache cache-first + stale flag, drift flags via diff_apply.has_deploy_drift + codex equivalent) in setup/src/cabal/webapi/routers/system.py — Owner: @python-architect — Parallel: yes
- [ ] T032 [US1] Frontend project-gate module in apps/cabal-desktop/src/modules/project-gate/ (recents table, path input w/ Tauri dialog when available, gate-before-workspace flow) — Owner: @react-architect — Parallel: yes
- [ ] T033 [US1] Frontend overview module in apps/cabal-desktop/src/modules/overview/ (summary cards for dashboard/sessions/account/doctor/knowledge/security, drift badges, deep links) — Owner: @react-architect — Parallel: yes
- [ ] T034 [US1] Frontend project-dashboard module in apps/cabal-desktop/src/modules/project-dashboard/ (four sections, per-section refresh, external links, hidden-when-unlinked) — Owner: @react-architect — Parallel: yes
- [ ] T035 [US1] Frontend diagnostics module in apps/cabal-desktop/src/modules/diagnostics/ (persisted history w/ severity filter, live stream tail, per-source retry) — Owner: @react-architect — Parallel: yes
- [ ] T036 [US1] Project-switch invalidation wiring (TanStack Query cache keys scoped by project, switch without restart) in apps/cabal-desktop/src/api/queryKeys.ts + stores — Owner: @react-architect — Parallel: yes
- [ ] T037 [P] [US1] Frontend tests: gate flow, overview render from MSW fixtures, module-isolation on one failing section in apps/cabal-desktop/tests/ — Owner: @frontend-tester
- [ ] T038 [US1] Backend integration test: project switch invalidates project-scoped snapshots; overview degrades per-section (one collector failing) in tests/integration/test_webapi_overview.py — Owner: @python-tester

**Checkpoint**: MVP — usable desktop workspace over live data.

---

## Phase 4: User Story 2 - Live Tool Readiness & Actions (Priority: P1)

**Status**: ⬜ Pending (0/8 — T039–T046)
**Goal**: Full tools catalog with definitive async statuses, filters, detail, and confirmed install/update with streamed progress.

**Independent Test**: Tools statuses all terminate definitively and match TUI probes; one update runs through confirm → job stream → refreshed status.

- [ ] T039 [P] [US2] Contract tests for /api/tools{,/status,/{key},/{key}/status} incl. definitive-status assertion #5 in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T040 [US2] Implement routers/tools.py (catalog metadata from tool_catalog, bulk + single status probes via tools.py probe helpers run as background sweep job, detail w/ versions from installers/versions + dotnet_releases) in setup/src/cabal/webapi/routers/tools.py — Owner: @python-architect — Parallel: yes
- [ ] T041 [US2] Register `tools.install` / `tools.update` action descriptors (version param, runtime_backups pre-action backup policy, installer subprocess as Job) in setup/src/cabal/webapi/actions_catalog/tools.py — Owner: @python-architect — Parallel: yes
- [ ] T042 [US2] Frontend tools module in apps/cabal-desktop/src/modules/tools/ (category rail, search + status/channel/badge filters w/ live counts, VirtualDataTable, detail drawer w/ version Select, async status fill-in) — Owner: @react-architect — Parallel: yes
- [ ] T043 [US2] Frontend install/update flow (ConfirmDialog w/ command+backup preview → JobPane stream → invalidate tool status) in apps/cabal-desktop/src/modules/tools/actions.tsx — Owner: @react-architect — Parallel: yes
- [ ] T044 [US2] Tools module styling pass (status badges, density, drawer layout, narrow reflow) in apps/cabal-desktop/src/modules/tools/*.css tokens usage — Owner: @frontend-css — Parallel: yes
- [ ] T045 [P] [US2] Frontend tests: filter/count logic, confirm-gated install, status fill-in in apps/cabal-desktop/tests/ — Owner: @frontend-tester
- [ ] T046 [US2] Backend integration test: fake-installer install end-to-end (prepare→execute→job→status refresh→audit row) in tests/integration/test_webapi_tools.py — Owner: @python-tester

**Checkpoint**: The old web UI's biggest defect (dead statuses, no actions) is fixed.

---

## Phase 5: User Story 3 - Config Deployment & Drift (Priority: P1)

**Status**: ⬜ Pending (0/12 — T047–T058)
**Goal**: Deploy tree + diffs + apply-with-backup, extras cleanup + restores, settings overrides, local project config, Codex parity screens.

**Independent Test**: Modify a repo config file → drift badge → preview/diff → apply (backup taken) → restore; toggle a local settings override; run codex conversion audit.

- [ ] T047 [P] [US3] Contract tests for /api/config/{tree,diff,extras,backups}, /api/settings, /api/local-config, /api/codex/conversion + digest stability assertion #7 in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T048 [US3] Implement routers/config.py (component tree + DriftReport w/ digest via components/diff_apply, per-file diff, extras via find_extras, backups list via cleanup_service + settings backups) in setup/src/cabal/webapi/routers/config.py — Owner: @python-architect — Parallel: yes
- [ ] T049 [US3] Register `config.apply` / `config.cleanup` / `config.restore_cleanup` / `config.restore_settings` descriptors (diff_apply.apply w/ backup+prune, cleanup_service.backup_and_remove/restore; DriftReport digest as precondition) in setup/src/cabal/webapi/actions_catalog/config.py — Owner: @python-architect — Parallel: yes
- [ ] T050 [US3] Implement routers/local_config.py + settings endpoints and `settings.toggle` / `settings.reset_local` / `local_config.apply_group` descriptors (claude_settings, local_setup.build_plan/apply_group; spec-workflow init runs as Job) in setup/src/cabal/webapi/routers/local_config.py — Owner: @python-architect — Parallel: yes
- [ ] T051 [US3] Implement routers/codex.py + `codex.apply` / `codex.local_apply` descriptors (codex_setup.components/diff_apply/local_setup/conversion) in setup/src/cabal/webapi/routers/codex.py — Owner: @python-architect — Parallel: yes
- [ ] T052 [US3] Frontend config-deploy module in apps/cabal-desktop/src/modules/config-deploy/ (target switch claude/codex, tri-state component tree, per-file DiffView, extras view-only rows, apply flow w/ per-file results) — Owner: @react-architect — Parallel: yes
- [ ] T053 [US3] Frontend cleanup-restore module in apps/cabal-desktop/src/modules/cleanup-restore/ (extras grouped w/ stale defaults, destructive confirm w/ backup statement, cleanup + settings restore lists) — Owner: @react-architect — Parallel: yes
- [ ] T054 [US3] Frontend settings module in apps/cabal-desktop/src/modules/settings/ (catalog w/ source markers, toggle local override, reset-all) — Owner: @react-architect — Parallel: yes
- [ ] T055 [US3] Frontend local-config module in apps/cabal-desktop/src/modules/local-config/ (action cards w/ per-item preview toggles, template Select, apply-per-group) — Owner: @react-architect — Parallel: yes
- [ ] T056 [US3] Frontend codex module in apps/cabal-desktop/src/modules/codex/ (deploy tree reuse, local scaffold, conversion audit table w/ source/output compare) — Owner: @react-architect — Parallel: yes
- [ ] T057 [US3] Nav drift badges wired from /api/health drift flags in apps/cabal-desktop/src/components/shell/NavBadges.tsx — Owner: @react-architect — Parallel: yes
- [ ] T058 [US3] Backend integration tests: apply with mutated-source → 409 no-write; cleanup backup/remove/restore round-trip; settings toggle idempotence in tests/integration/test_webapi_config.py — Owner: @python-tester

**Checkpoint**: All P1 stories done — daily deploy workflow fully web-capable.

---

## Phase 6: User Story 4 - Sessions, Account & Usage Observability (Priority: P2)

**Status**: ⬜ Pending (0/8 — T059–T066)
**Goal**: Cross-project sessions dashboard with tabs and delete, account panel, config doctor, model assignments.

**Independent Test**: Sessions totals/table match TUI for same transcripts; delete one session with confirm; reassign one model pin (repo + target).

- [ ] T059 [P] [US4] Contract tests for /api/sessions (pagination assertion #6), /api/sessions/{id} tabs, /api/account, /api/doctor, /api/models, /api/claude-info in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T060 [US4] Implement routers/sessions.py (cursor-paginated summaries + totals via session_reader/session_pricing, lazy tab payloads, `sessions.delete` descriptor w/ removals populated) in setup/src/cabal/webapi/routers/sessions.py — Owner: @python-architect — Parallel: yes
- [ ] T061 [US4] Implement routers/account.py (account from ~/.claude.json presence-only, doctor via config_doctor.run_doctor_cached, model assignments list + `models.assign` descriptor via model_assignments, claude-info payload) in setup/src/cabal/webapi/routers/account.py — Owner: @python-architect — Parallel: yes
- [ ] T062 [US4] Frontend sessions module in apps/cabal-desktop/src/modules/sessions/ (totals bar, virtualized hierarchy table w/ sort, tabs overview/activity/raw/triggers, delete flow) — Owner: @react-architect — Parallel: yes
- [ ] T063 [US4] Frontend account + doctor modules in apps/cabal-desktop/src/modules/{account,doctor}/ — Owner: @react-architect — Parallel: yes
- [ ] T064 [US4] Frontend model-assignments module in apps/cabal-desktop/src/modules/model-assignments/ (pin table, validated picker, sync-state column) — Owner: @react-architect — Parallel: yes
- [ ] T065 [P] [US4] Frontend tests: sessions virtualization + sort, delete confirm gating, model picker validation in apps/cabal-desktop/tests/ — Owner: @frontend-tester
- [ ] T066 [US4] Backend integration test: 1,000-session fixture pagination stays bounded + correct totals in tests/integration/test_webapi_sessions.py — Owner: @python-tester

**Checkpoint**: Observability parity with TUI sessions/account/doctor/models.

---

## Phase 7: User Story 5 - Knowledge Graph & Retrieval (Priority: P2)

**Status**: ⬜ Pending (0/7 — T067–T073)
**Goal**: Visual interactive graph, export/doctor/index actions, full-text + semantic search, context packs, preflight, usage ledger.

**Independent Test**: Export from UI → visual graph pan/zoom/select with inspector evidence → one full-text + one semantic search → context pack at each budget.

- [ ] T067 [P] [US5] Contract tests for /api/knowledge{,/graph,/search,/context-pack,/preflight,/usage} incl. semantic-unavailable honest state in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T068 [US5] Implement routers/knowledge.py (bundle availability/counts, paginated graph payload, okf search/semantic/context/preflight/usage services; `knowledge.export` + `knowledge.index` descriptors running as Jobs) in setup/src/cabal/webapi/routers/knowledge.py — Owner: @python-architect — Parallel: yes
- [ ] T069 [US5] Frontend knowledge module shell in apps/cabal-desktop/src/modules/knowledge/ (tabs graph/search/packs/reports, empty state w/ inline export, export/index job panes) — Owner: @react-architect — Parallel: yes
- [ ] T070 [US5] GraphCanvas component (d3-force layout, canvas render, pan/zoom, hover/select, type+relation filters, search-to-highlight) in apps/cabal-desktop/src/modules/knowledge/GraphCanvas.tsx — Owner: @react-architect — Parallel: yes
- [ ] T071 [US5] Inspector + search results + context-pack (budget select, copy/export) + preflight/usage views in apps/cabal-desktop/src/modules/knowledge/ — Owner: @react-architect — Parallel: yes
- [ ] T072 [US5] Graph + knowledge styling (node palette by type, edge states, inspector layout) — Owner: @frontend-css — Parallel: yes
- [ ] T073 [P] [US5] Frontend tests: graph interaction logic (layout mocked), search rendering, budget select in apps/cabal-desktop/tests/ — Owner: @frontend-tester

**Checkpoint**: Knowledge is visibly better in the browser than the terminal.

---

## Phase 8: User Story 6 - MCP Connectors & Agent Services (Priority: P2)

**Status**: ⬜ Pending (0/7 — T074–T080)
**Goal**: Full MCP scope management and service lifecycle with live logs.

**Independent Test**: MCP table matches TUI; activate + disable one template server; start/stop a service watching its live log stream.

- [ ] T074 [P] [US6] Contract tests for /api/mcp{,/{name}/status}, /api/services, service log SSE channel in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T075 [US6] Implement routers/mcp.py (rows via mcp_ops/mcp_view_logic, per-row recheck; `mcp.activate_global` / `mcp.activate_local` / `mcp.approve` / `mcp.disable` descriptors w/ scope param) in setup/src/cabal/webapi/routers/mcp.py — Owner: @python-architect — Parallel: yes
- [ ] T076 [US6] Implement routers/services.py (ServiceRow + PrereqCheck via service_catalog/service_prereqs/service_supervisor, log SSE from supervisor streams; `services.setup` / `services.start` / `services.stop` descriptors; dashboard handoff endpoint spawning external terminal) in setup/src/cabal/webapi/routers/services.py — Owner: @python-architect — Parallel: yes
- [ ] T077 [US6] Frontend mcp module in apps/cabal-desktop/src/modules/mcp/ (scope table, row spinner recheck, activate flows, multi-scope disable dialog) — Owner: @react-architect — Parallel: yes
- [ ] T078 [US6] Frontend services module in apps/cabal-desktop/src/modules/services/ (rows w/ prereq messages, gated setup/start/stop, LogStream pane, external dashboard handoff button) — Owner: @react-architect — Parallel: yes
- [ ] T079 [US6] Backend integration test: fixture service start→log stream→stop; app-shutdown stops app-started services in tests/integration/test_webapi_services.py — Owner: @python-tester
- [ ] T080 [P] [US6] Frontend tests: scope-disable dialog logic, prereq gating, log stream rendering in apps/cabal-desktop/tests/ — Owner: @frontend-tester

**Checkpoint**: Operational controls complete.

---

## Phase 9: User Story 7 - Project Lifecycle: Clone & Init (Priority: P3)

**Status**: ⬜ Pending (0/7 — T081–T087)
**Goal**: Provider login/accounts/repos/clone and the full new-project wizard with staged preview and cancellable assistant handoff.

**Independent Test**: Device login → clone a repo with streamed output → init a project from template with per-file staging → workspace switches to it.

- [ ] T081 [P] [US7] Contract tests for /api/provider{,/repos}, /api/init/{templates,plan}, login state machine states in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T082 [US7] Extend routers/projects.py with provider endpoints + `provider.login` (device flow via installers/gh as polled state) / `provider.clone` (gh clone as Job w/ destination param) descriptors + accounts via gh_accounts in setup/src/cabal/webapi/routers/projects.py — Owner: @python-architect — Parallel: yes
- [ ] T083 [US7] Implement init endpoints + `init.apply` descriptor (init_project_service.apply_plan, gh_templates, INIT_PROMPT, claude_cli.spawn_claude streamed into Job, cancellable) in setup/src/cabal/webapi/routers/projects.py — Owner: @python-architect — Parallel: yes
- [ ] T084 [US7] Frontend provider module in apps/cabal-desktop/src/modules/provider/ (login w/ user-code display + poll state, accounts, repo list w/ search, clone dialog w/ destination + job stream) — Owner: @react-architect — Parallel: yes
- [ ] T085 [US7] Frontend init-project wizard in apps/cabal-desktop/src/modules/init-project/ (dest/name validation, template source radio, staged-file toggles, project MCP editor, apply job pane w/ cancel; Tauri dialog for folder pick, manual path fallback in browser) — Owner: @react-architect — Parallel: yes
- [ ] T086 [US7] Post-init/clone context switch + recents update wiring in apps/cabal-desktop/src/modules/{provider,init-project}/ + stores — Owner: @react-architect — Parallel: yes
- [ ] T087 [US7] Backend integration test: init plan preview + apply with fake handoff process (no real claude spawn), cancel mid-stream in tests/integration/test_webapi_init.py — Owner: @python-tester

**Checkpoint**: Full project lifecycle without the terminal.

---

## Phase 10: User Story 8 - Security, Environment & Identity (Priority: P3)

**Status**: ⬜ Pending (0/7 — T088–T094)
**Goal**: Package security scan/fix, curated + system environment, git identity + commit policy.

**Independent Test**: Scan findings match TUI; apply one fix via exact-command confirm; edit one curated env var; change one policy field with validation.

- [ ] T088 [P] [US8] Contract tests for /api/security/scan, /api/env, /api/git/{identity,policy} in tests/contract/test_webapi_modules_contract.py — Owner: @python-tester
- [ ] T089 [US8] Implement routers/security_scan.py (package_security.service scan/cache; `security.apply_fix` descriptor w/ exact command preview, fix as Job) in setup/src/cabal/webapi/routers/security_scan.py — Owner: @python-architect — Parallel: yes
- [ ] T090 [US8] Implement routers/environment.py (curated set + redacted system snapshot; `env.apply` descriptor via setx/env_profile per platform; git identity get + `git.identity.set`; policy get + `git.policy.set` w/ validation via git_policy) in setup/src/cabal/webapi/routers/environment.py — Owner: @python-architect — Parallel: yes
- [ ] T091 [US8] Frontend package-security module in apps/cabal-desktop/src/modules/package-security/ (findings table w/ severity, notices, fix confirm w/ exact command, rescan) — Owner: @react-architect — Parallel: yes
- [ ] T092 [US8] Frontend environment module in apps/cabal-desktop/src/modules/environment/ (curated editor w/ path browse, apply flow, searchable read-only system view) — Owner: @react-architect — Parallel: yes
- [ ] T093 [US8] Frontend git-identity module in apps/cabal-desktop/src/modules/git-identity/ (identity per scope, policy editor w/ validation) — Owner: @react-architect — Parallel: yes
- [ ] T094 [US8] Backend integration test: fix preview matches executed command; env apply fixture round-trip; policy validation rejects bad types in tests/integration/test_webapi_env_identity.py — Owner: @python-tester

**Checkpoint**: All eight user stories complete.

---

## Phase 11: Polish, Packaging & Retirement

**Status**: ⬜ Pending (0/10 — T095–T104)
**Purpose**: Ship the desktop bundle, prove parity and performance, retire the legacy web UI, audit.

- [ ] T095 Create PyInstaller sidecar spec setup/build/cabal-backend.spec (hidden imports for cabal.webapi.*, verify binary starts + writes handshake) — Owner: @python-architect
- [ ] T096 Finalize tauri.conf.json (externalBin cabal-backend, icons, productName, NSIS target) and verify `pnpm tauri build` produces a working installer — Owner: main
- [ ] T097 [P] Playwright e2e smoke in apps/cabal-desktop/tests/e2e/ (fixture backend: walk all 22 nav entries, run one full prepare/execute flow, kill backend → reconnect banner) — Owner: @frontend-tester
- [ ] T098 Parity walkthrough vs the 22-module table (SC-001) + safety checks from quickstart.md §Verifying; record results in specs/015-web-ui-overhaul/parity.md — Owner: main
- [ ] T099 [P] Performance validation: SC-002 warm-start < 3 s, SC-010 fixtures (1k sessions, 1k graph nodes) interaction < 200 ms; record in specs/015-web-ui-overhaul/parity.md — Owner: @frontend-tester
- [ ] T100 Retire legacy web UI: remove setup/src/cabal/web/, run-web-ui{,.cmd}, legacy web tests (port still-relevant assertions to webapi suites), update setup/build/cabal.spec hidden imports + README.md references — Owner: @python-architect
- [ ] T101 [P] Docs: add `@frontend-tester` row to .specify/memory/agents.md (noted in plan.md footnote), add desktop app section to README.md — Owner: main
- [ ] T102 Full green run: pytest (contract/unit/integration incl. existing TUI suite — SC-008), pnpm test, pnpm test:e2e — Owner: main
- [ ] T103 Conformance audit of implementation vs plan/contracts/spec — Owner: @code-plan-verifier
- [ ] T104 Execute quickstart.md end-to-end on Windows (dev browser mode, tauri dev, production build) and fix doc drift — Owner: main

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** → nothing. T002–T007 parallel after T001.
- **Phase 2 (Foundational)** → Phase 1. T008–T011 (contract tests) precede T012–T026; backend lane T012–T019 and frontend lane T020–T026 run concurrently (worktrees); T027–T028 after both lanes merge. BLOCKS all stories.
- **Phases 3–10 (US1–US8)** → Phase 2. Sequential in priority order for a single implementation pass; each story's backend/frontend lanes run concurrently within its phase. US3 depends on nothing in US2; US7's context-switch task (T086) builds on US1's T036.
- **Phase 11 (Polish)** → all story phases. T100 (retirement) strictly after T098 parity confirmation.

### Within each story phase

Contract tests (T0x9-style) → backend lane + frontend lane (concurrent, worktree-isolated) → integration/frontend tests → checkpoint.

### Parallel dispatch pattern (Gate 6)

Each `Parallel: yes` lane is dispatched as ONE worktree-isolated agent run covering its consecutive tasks (e.g. US3 backend lane T048–T051 = one `@python-architect` dispatch; US3 frontend lane T052–T057 = one `@react-architect` dispatch). Merge lanes back to `015-web-ui-overhaul` at each phase boundary before starting the next phase.

## Parallel Example: User Story 2 (Tools)

```text
# After T039 contract tests are red:
Agent(@python-architect, isolation: worktree)  → T040, T041
Agent(@react-architect,  isolation: worktree)  → T042, T043
Agent(@frontend-css,     isolation: worktree)  → T044
# Merge all three lanes → then sequential:
Agent(@frontend-tester) → T045 ; Agent(@python-tester) → T046
```

## Implementation Strategy

- **MVP = Phase 1 + 2 + 3 (US1)**: a real desktop workspace with overview/dashboard/diagnostics and honest stubs elsewhere. Stop, validate, demo.
- **P1 slice = + US2 + US3**: daily-driver replacement for the TUI's core workflows (tools + config deploy).
- **Incremental**: each subsequent story is independently testable and shippable; run the story checkpoint before moving on.
- Commit at each phase checkpoint (per-phase commits on `015-web-ui-overhaul`).
- Existing TUI tests run in T102 but should be spot-checked at every phase that touches shared services (T012 redaction move, T050 local_config, T076 supervisor).
