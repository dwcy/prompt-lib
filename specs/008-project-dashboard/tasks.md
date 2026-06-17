---

description: "Task list for 008-project-dashboard implementation"
---

# Tasks: Project Dashboard Panel

**Input**: Design documents from `/specs/008-project-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the contracts (`contracts/*.md`) and spec success criteria
(SC-003, SC-005) require unit + integration coverage, and Constitution Gate 3
requires the public-API contract test before implementation.

**Organization**: Grouped by user story (spec.md) for independent implementation and
testing. All impl → `@python-architect`; all tests → `@python-tester`; final audit →
`@code-plan-verifier` (read-only). Inline Textual `DEFAULT_CSS` is Python, owned by
`@python-architect` — `@frontend-css` is only for `*.css` files (none here).

**Parallel dispatch**: Gate 6 is N/A for this feature (sequential single-writer
dispatch), so NO task carries `Parallel: yes`. `[P]` below is advisory only — it marks
tasks that touch different files and have no incomplete-task dependency.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (2/2 — T001–T002)
**Purpose**: Project initialization for the dashboard module surface

- [X] T001 Create the models package `setup/src/cabal/models/` with `__init__.py` (so `from cabal.models import dashboard` resolves) — Owner: @python-architect
- [X] T002 [P] Confirm no new runtime dependency is required (stdlib `urllib.request` for GET-only API calls per research D8); verify `tests/unit`, `tests/integration`, `tests/contract` exist for the new modules — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (8/8 — T003–T010)
**Purpose**: Data models, pure link parsing, and the DashboardPanel framework that every user story renders into

**⚠️ CRITICAL**: No user-story section can render until the panel shell + models exist

> **Design note (resolves analyze finding I1):** no `dashboard_service.py`/`build_snapshot` orchestrator — the panel dispatches one worker per section (`_fetch_<name>`), each calling its own collector. Stories add their `_fetch_*` method + collector. `refresh_dashboard` dynamically dispatches whatever `_fetch_*` methods exist.

- [X] T003 Implement data models in `setup/src/cabal/models/dashboard.py` — `AvailabilityState`, `GitRemote`, `GitSection`, `WorkflowRun`, `PullRequest`, `GitHubSection`, `ProjectMember`, `SupabaseSection`, `VercelSection`, `DashboardSnapshot` + `to_cacheable()` / `from_cached()`; no I/O, no Textual import, no token fields (contracts/dashboard_models.md) — Owner: @python-architect
- [X] T004 [P] Implement `setup/src/cabal/dashboard_links.py` — `find_supabase_ref`, `supabase_dashboard_url`, `supabase_schema_url`, `find_vercel_link`, `parse_github_remote` (HTTPS + SSH + non-GitHub → None); pure, no network (contracts/dashboard_services.md §dashboard_links) — Owner: @python-architect
- [X] T005 [P] Unit-test the models in `tests/unit/test_dashboard_models.py` — every `AvailabilityState`, `to_cacheable()` json round-trip with no token-named keys, `from_cached(None/{bogus})` → `None` (C-M1…C-M4) — Owner: @python-tester
- [X] T006 [P] Unit-test `dashboard_links` in `tests/unit/test_dashboard_links.py` — `parse_github_remote` over HTTPS/`.git`/SSH/non-GitHub, supabase/vercel link detection in temp dirs, URL derivation (C-L1, C-L2) — Owner: @python-tester
- [X] T007 Implement the `DashboardPanel` shell in `setup/src/cabal/widgets/dashboard_panel.py` — `compose()` (title bar + 4 labelled section `Static` bodies + Refresh button + `DEFAULT_CSS`), cache-first paint via `widget_cache.load_entry("dashboard:<hash(project_path)>")`, `selected_project is None` placeholder, `refresh_dashboard()` entry, per-section worker scaffolding (`run_worker(..., thread=True, exclusive=True)` + `call_from_thread`); helpers named by role (`_build_*`/`_apply_*`, never `_render*`/`_compose*`) per the Textual shadow rule (contracts/dashboard_panel.md, depends T003) — Owner: @python-architect
- [X] T008 Integrate the panel into `setup/src/cabal/views/home.py` — mount `DashboardPanel(id="dashboard")` in the home scroll, add `Binding("ctrl+d", "refresh_dashboard", ...)` + guarded `action_refresh_dashboard`, and `on_screen_resume` project-change re-scope (FR-002, FR-003, C-P4; depends T007) — Owner: @python-architect
- [X] T009 Extend the public-API contract test `tests/contract/test_wizard_public_api.py` — assert any name re-exported via `cabal.wizard` (panel/models) resolves to its defining module; if nothing is re-exported, assert the dashboard is reached via `HomeScreen` only (Constitution Gate 3, C-P-C1) — Owner: @python-tester
- [X] T010 Smoke integration test in `tests/integration/test_dashboard_panel.py` — panel mounts + renders with at least one `await pilot.pause()` and no `Visual.to_strips`/`_render_content` shadow crash; `selected_project = None` shows the placeholder and starts no workers (C-P-T4, C-P-T5) — Owner: @python-tester

**Checkpoint**: Panel framework, models, and link parsing ready — user-story sections can be wired in.

---

## Phase 3: User Story 1 - Local git overview (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (4/4 — T011–T014)
**Goal**: The Git section shows current branch, local branches, and remotes for the selected project, degrading gracefully.

**Independent Test**: Select a temp git repo → Git section lists current branch (highlighted), other branches, and remotes; select a non-git folder → "not a git repository" hint, no traceback.

- [X] T011 [P] [US1] Unit-test `collect_git` in `tests/unit/test_dashboard_git_service.py` — canned `git` output for normal, detached HEAD, not-a-repo (`NOT_LINKED`), and missing `git` (`NO_CLI`), via a monkeypatched subprocess runner (no live git) — Owner: @python-tester
- [X] T012 [P] [US1] Integration test (Pilot) in `tests/integration/test_dashboard_panel.py` — Git section renders branch/branches/remotes for a temp repo and the non-repo hint (stubbed `collect_git`) — Owner: @python-tester
- [X] T013 [US1] Implement `setup/src/cabal/dashboard_git_service.py::collect_git(project)` — `git -C` for current branch / `branch --format` / `remote -v`; detached HEAD → short SHA + `detached=True`; tag `GitRemote.is_github` via `parse_github_remote`; never raises (FR-010…FR-012, contracts §dashboard_git_service) — Owner: @python-architect
- [X] T014 [US1] Wire the git worker in `DashboardPanel` — `_fetch_git` → `call_from_thread(_apply_git, section)`; render `GitSection` (current branch highlighted, branch list, remotes) and its hints (depends T007, T013) — Owner: @python-architect

**Checkpoint**: Git section fully functional and independently testable — MVP.

---

## Phase 4: User Story 2 - GitHub Actions + PRs (Priority: P2)

**Status**: ✅ Complete (4/4 — T015–T018)
**Goal**: The GitHub section shows connection status, Actions runs for the current branch, and open PRs, reusing cabal's `gh` auth.

**Independent Test**: With `gh` authed + a GitHub remote → runs (status/conclusion/url) + open PRs (number/title/author/url); `gh` unauth → "run `gh auth login`" hint + link to gh-accounts.

- [X] T015 [P] [US2] Unit-test `collect_github` in `tests/unit/test_dashboard_services.py` — remote choice (origin vs first GitHub), no-GitHub-remote (`NOT_LINKED`), no-`gh` (`NO_CLI`), unauth (`NOT_AUTHED`), and `gh run list`/`gh pr list` `--json` parsing, with `gh` stubbed (no network) — Owner: @python-tester
- [X] T016 [US2] Implement `setup/src/cabal/dashboard_github_service.py::collect_github(project, current_branch, remotes)` — choose remote + set `remote_used`, derive `owner_repo`, `gh run list --branch <b> --json …`, `gh pr list --state open --json …`, auth-state hints; never raises (FR-020…FR-023, contracts §dashboard_github_service) — Owner: @python-architect
- [X] T017 [US2] Wire the github worker + render `GitHubSection` in `DashboardPanel` — connected flag, runs ("no workflow runs" when empty), open PRs, and the unauth hint linking the existing gh-accounts / device-flow path (depends T007, T016) — Owner: @python-architect
- [X] T018 [US2] Integration test (Pilot) in `tests/integration/test_dashboard_panel.py` — GitHub section renders runs + PRs (stubbed service) and the unauth hint state — Owner: @python-tester

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 5 - Fast, non-blocking refresh (Priority: P2)

**Status**: ✅ Complete (4/4 — T019–T022) — also fixed warm-cache paint clobber (FR-050) + gh auth-status timeout guard; closed analyze finding C2 (git ERROR/TIMEOUT tests)
**Goal**: The dashboard paints from cache instantly, refreshes in the background, re-scopes on project change, and isolates per-section failures — with a manual refresh control.

**Independent Test**: Warm-cache mount paints last-known values without awaiting workers; a failing section shows only its own error; switching projects re-keys the cache; `Ctrl+D` re-fetches all sections.

- [X] T019 [US5] (re-scope + refresh-all implemented in the panel per the I1 design note; no separate `dashboard_service.py`) Implement `setup/src/cabal/dashboard_service.py::build_snapshot(project, captured_at)` — call the available collectors, assemble a `DashboardSnapshot`; wire `DashboardPanel.refresh_dashboard()` to dispatch all section workers and re-key the cache by project path (FR-050, FR-052, C-P4; depends T014, T017) — Owner: @python-architect
- [X] T020 [US5] Save fresh snapshots via `widget_cache.save_entry(key, snapshot.to_cacheable())` (no token fields) and ensure `Ctrl+D` / `action_refresh_dashboard` triggers every wired worker without blocking the UI thread (FR-051, FR-054, C-P7) — Owner: @python-architect
- [X] T021 [P] [US5] Integration test (Pilot) in `tests/integration/test_dashboard_panel.py` — warm-cache first paint without awaiting workers (C-P1), a worker exception isolates to its section while others render (C-P3), and a project change re-keys the cache (C-P4) — Owner: @python-tester
- [X] T022 [P] [US5] Regression test in `tests/integration/test_dashboard_panel.py` — after a refresh with tokens set in env, assert no access-token value appears in `~/.cabal/cache.json` (SC-005, FR-054) — Owner: @python-tester

**Checkpoint**: Cross-cutting refresh/caching/isolation behavior verified against real sections.

---

## Phase 6: User Story 3 - Supabase stats + links (Priority: P3)

**Status**: ⬜ Pending (0/4 — T023–T026)
**Goal**: The Supabase section shows linked-project baseline (ref, last migration, db location, dashboard + Schema Visualizer links) and, when `SUPABASE_ACCESS_TOKEN` is set, status/region/plan/last-backup/github-connected/members — degrading per AvailabilityState.

**Independent Test**: Linked project + `supabase` installed → baseline + clickable links; with token → enriched rows; remove token → enrich hint, baseline still shown; no link file → collapsed "no linked Supabase project".

- [ ] T023 [P] [US3] Unit-test `collect_supabase` in `tests/unit/test_dashboard_services.py` — not-linked / no-CLI / baseline, and enrich states TOKEN_MISSING / TOKEN_REJECTED (401/403) / TIMEOUT / OK with CLI + management-API HTTP stubbed (no network); assert no token in the returned section (FR-030…FR-034) — Owner: @python-tester
- [ ] T024 [US3] Implement `setup/src/cabal/dashboard_supabase_service.py::collect_supabase(project)` — link via `dashboard_links.find_supabase_ref`, baseline (last migration, db location, derived dashboard + schema URLs), enrich via Supabase Management API GET (`urllib.request`, `SUPABASE_ACCESS_TOKEN` from env only, bounded timeout); never raises, never returns the token (contracts §dashboard_supabase_service, research D4/D8/D9) — Owner: @python-architect
- [ ] T025 [US3] Wire the supabase worker + render `SupabaseSection` in `DashboardPanel` — baseline + enriched rows, clickable dashboard/Schema-Visualizer links via `[@click=...]` + copyable URL (research D7), `enrich_hint` when token missing/rejected; register collector in `build_snapshot` (depends T019, T024) — Owner: @python-architect
- [ ] T026 [US3] Integration test (Pilot) in `tests/integration/test_dashboard_panel.py` — Supabase section renders baseline, token-enriched, and collapsed not-linked states (stubbed service) — Owner: @python-tester

**Checkpoint**: US1 + US2 + US5 + US3 functional.

---

## Phase 7: User Story 4 - Vercel stats + links (Priority: P3)

**Status**: ⬜ Pending (0/4 — T027–T030)
**Goal**: The Vercel section mirrors Supabase — project name, latest deployment status + URL, and (with `VERCEL_TOKEN`) team/plan, region, members — degrading per AvailabilityState.

**Independent Test**: `.vercel/project.json` + `vercel` installed → project + latest deployment + link; with token → team/region/members; no link file → collapsed "no linked Vercel project".

- [ ] T027 [P] [US4] Unit-test `collect_vercel` in `tests/unit/test_dashboard_services.py` — not-linked / no-CLI / baseline, and enrich TOKEN_MISSING / TOKEN_REJECTED / TIMEOUT / OK with CLI + REST HTTP stubbed; assert no token leaks (FR-040…FR-043) — Owner: @python-tester
- [ ] T028 [US4] Implement `setup/src/cabal/dashboard_vercel_service.py::collect_vercel(project)` — link via `dashboard_links.find_vercel_link` (`.vercel/project.json`), CLI baseline (project name, latest deployment status/url), enrich via Vercel REST GET (`urllib.request`, `VERCEL_TOKEN` env only, bounded timeout); never raises, never returns the token (contracts §dashboard_vercel_service, research D5/D8/D9) — Owner: @python-architect
- [ ] T029 [US4] Wire the vercel worker + render `VercelSection` in `DashboardPanel` — baseline + enriched rows, clickable project/deployment link + copyable URL, `enrich_hint`; register collector in `build_snapshot` (depends T019, T028) — Owner: @python-architect
- [ ] T030 [US4] Integration test (Pilot) in `tests/integration/test_dashboard_panel.py` — Vercel section renders baseline, token-enriched, and collapsed not-linked states (stubbed service) — Owner: @python-tester

**Checkpoint**: All four sources independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Status**: ⬜ Pending (0/4 — T031–T034)
**Purpose**: Validation, size discipline, and plan-compliance gate

- [ ] T031 [P] Walk the `quickstart.md` degradation matrix on a real project (non-git folder, gh unauth, missing CLIs, invalid token, no project) and tighten any rough hint text (SC-003) — Owner: main
- [ ] T032 [P] Verify every new module is under its Python soft cap and single-responsibility (services hold all I/O, the widget holds none); split or add a line-1 justification if any file exceeds the hard cap — Owner: @python-architect
- [ ] T033 Run the full suite green — `python -m pytest tests/ setup/tests/ -q` (unit + integration + contract) — Owner: @python-tester
- [ ] T034 Read-only plan-compliance audit against plan.md + contracts (no mock data, no token persistence, no I/O in the widget, AvailabilityState coverage) — Owner: @code-plan-verifier

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → after Setup. **Blocks all user stories** (models + panel shell + link parsing).
- **US1 (P3)** → after Foundational. The MVP slice.
- **US2 (P4)** → after Foundational. Independent of US1 (uses its own remote data; only needs `current_branch`/`remotes` shape from the model, not US1 code).
- **US5 (P5)** → after US1 + US2 exist (needs ≥1 real section to exercise cache-paint + isolation); `build_snapshot` wires whatever collectors exist.
- **US3 (P6)**, **US4 (P7)** → after Foundational; each registers its collector into `build_snapshot` (T019). Independent of each other.
- **Polish (P8)** → after all desired stories.

### Within each story

- Tests are written first and observed failing, then implementation (services before worker-wiring/render).
- Service module (`dashboard_*_service.py`) before the panel worker that calls it.

### Parallel opportunities (advisory `[P]` — sequential dispatch per Gate 6)

- T004 ∥ T005 ∥ T006 touch different files (links module vs two test modules).
- Each story's unit test (`[P]`) is file-independent from its impl until wiring.
- US3 and US4 are mutually independent once Foundational + T019 land.

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**: Git section works on the HomeScreen for the selected project. Demo-able MVP.

### Incremental delivery

Foundational → US1 (git, MVP) → US2 (GitHub) → US5 (refresh/cache hardening) → US3 (Supabase) → US4 (Vercel) → Polish. Each step adds value without breaking the prior sections.

---

## Notes

- `[P]` = different files, no incomplete-task dependency (advisory). No `Parallel: yes` — dispatch is sequential single-writer (Constitution Gate 6 N/A).
- Every task ends with `— Owner: @<agent>`; owners are from `.specify/memory/agents.md`.
- All subprocess/HTTP I/O lives in `dashboard_*_service.py`; the widget never shells out (Python size rule).
- Tokens are read from env at fetch time only and never written to `~/.cabal/cache.json`.
- Re-run the Phase Status lines on every `[X]` change during `/speckit-implement`.
