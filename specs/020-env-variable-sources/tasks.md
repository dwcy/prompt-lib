---
description: "Task ledger for 020 — Environment Variables multi-source browser"
---

# Tasks: Environment Variables — Multi-Source Browser

**Input**: Design documents from `/specs/020-env-variable-sources/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Contract tests are **mandatory** for the two REST surfaces (Constitution Principle III / Gate 3) and appear before their implementations. Unit tests are included where a rule is easy to get silently wrong — the degradation matrix, key flattening, and retrievability classification.

**Organization**: Grouped by user story so each can be implemented, tested, and shipped independently.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US7 from spec.md
- **Owner**: from `.specify/memory/agents.md`
- **Parallel: yes**: dispatched concurrently — `/speckit-implement` passes `isolation: "worktree"` (Gate 6)

> **Working-tree warning.** This repository has been edited by more than one session, and a
> `setup-plan.ps1` run already overwrote another feature's plan because `.specify/feature.json`
> pointed elsewhere. Before executing any task here, confirm the branch is
> `020-env-variable-sources` and that `feature.json` names this feature. Every `Parallel: yes`
> task MUST get its own worktree.

---

## Phase 1: Setup

**Status**: ✅ Done (3/3 — T001–T003)
**Purpose**: Places to put things; no behaviour yet.

- [X] T001 Create `setup/src/cabal/models/envsources.py` with the enums from data-model.md (`SourceKind`, `Retrievability`, `LinkConfidence`) and re-export `AvailabilityState` from `models/dashboard.py` — Owner: @python-architect
- [X] T002 [P] Create the frontend module skeleton — `apps/cabal-desktop/src/api/envSources.ts` and empty `src/modules/environment/components/{EnvSourceTabs,EnvSourceTable,RevealCell,EnvSourceEmptyState}.tsx` — Owner: @react-architect
- [X] T003 [P] Add per-source and per-degradation MSW fixture stubs in `apps/cabal-desktop/tests/msw/fixtures.ts` covering all four `AvailabilityState` values — Owner: @frontend-tester

---

## Phase 2: Foundational

**Status**: ✅ Done (7/7 — T004–T010)
**Purpose**: Blocking prerequisites. Every user story depends on these. **No story may start until this phase is complete.**

- [X] T004 Define `VariableSource`, `VariableContainer`, `VariableEntry`, `ConfigLayer`, `RevealResult` dataclasses in `setup/src/cabal/models/envsources.py` per data-model.md — Owner: @python-architect
- [X] T005 Assert structurally that `VariableEntry` has no `value` field and cannot serialise one, in `setup/tests/test_envsource_models.py` — Owner: @python-tester
- [X] T006 Create the collector fan-out skeleton in `setup/src/cabal/webapi/envsources_service.py`: bounded thread pool, per-collector timeout, a collector that raises or hangs becomes `degraded` and never propagates (research R5) — Owner: @python-architect
- [X] T007 [P] Unit-test the fan-out contract in `setup/tests/test_envsources_service.py` — a hanging collector must not delay the response past the cap, and a raising collector must yield `degraded` with a hint — Owner: @python-tester
- [X] T008 [P] Add the `env.reveal` audit action to `setup/src/cabal/webapi/audit.py` with no field capable of holding a value (FR-016) — Owner: @python-architect
- [X] T009 [P] Zod schemas mirroring the data model in `apps/cabal-desktop/src/api/envSources.ts`, with `VariableEntry` having no `value` member — Owner: @react-architect
- [X] T010 Review the five non-happy states (not-linked / empty / degraded / denied / never-retrievable) and write the copy for each into `specs/020-env-variable-sources/quickstart.md` before any UI is built — Owner: main (no UX reviewer in `agents.md`; see Roster drift below)

**Checkpoint**: models exist, fan-out degrades correctly, audit action registered, UI copy agreed.

---

## Phase 3: User Story 1 — Repo config files (P1) 🎯 MVP

**Status**: ✅ Done (13/13 — T011–T023)
**Goal**: Every environment/config file in the selected project becomes its own tab listing its keys, with no values shown.

**Independent test**: Select a project with two or more config files → one tab per file, named after the file, keys listed, zero values on screen. Works offline with no credentials.

### Contract tests first (Gate 3 — MUST fail before T018)

- [X] T011 [US1] Contract test `GET /api/env/sources` in `setup/tests/contract/test_env_sources_contract.py` asserting C1–C4 and C7 from `contracts/env-sources.contract.md` — Owner: @python-tester
- [X] T012 [P] [US1] Contract test asserting C10 — the route returns within its cap with a hanging collector marked `degraded` — Owner: @python-tester

### Implementation

- [X] T013 [US1] Implement config-file discovery in `setup/src/cabal/envsource_discovery.py`: walk the project for `.env*`, `appsettings*.json`, `*.env.json`, `Properties/launchSettings.json`; skip dependency/build/VCS directories; honour a depth cap (FR-026/27) — Owner: @python-architect
- [X] T014 [P] [US1] Unit-test discovery in `setup/tests/test_envsource_discovery.py`: gitignored files ARE included, `node_modules`/`__pycache__`/`dist` are NOT, depth cap holds, and the file-count cap is reported rather than silently truncating — Owner: @python-tester
- [X] T015 [US1] Parse discovered files into entries (dotenv and JSON) in `setup/src/cabal/envsource_discovery.py`, listing key names only (FR-028) — Owner: @python-architect
- [X] T016 [P] [US1] Unit-test parsing: empty file, comments-only file, malformed file, and duplicate keys each produce the right state without affecting sibling files (FR-029) — Owner: @python-tester
- [X] T017 [US1] Assign `qualifier` so same-named files across a monorepo stay distinguishable (data-model rule 4) in `setup/src/cabal/envsource_discovery.py` — Owner: @python-architect
- [X] T018 [US1] Implement `GET /api/env/sources` in `setup/src/cabal/webapi/routers/environment.py`, wiring discovery through the fan-out; existing curated/system routes untouched (FR-002) — Owner: @python-architect
- [X] T019 [US1] Build the dynamic tab strip in `apps/cabal-desktop/src/modules/environment/components/EnvSourceTabs.tsx` — tabs come only from the response, rebuilt on project change (FR-005/06) — Owner: @react-architect
- [X] T020 [US1] Render names + metadata in `apps/cabal-desktop/src/modules/environment/components/EnvSourceTable.tsx` with no value column — Owner: @react-architect
- [X] T021 [US1] Replace the two-pill switcher with the tab strip in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.tsx`, keeping Curated and System as the first two tabs — Owner: @react-architect
- [X] T022 [US1] Style the tab strip in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css`: overflow must keep every tab reachable without truncating names into ambiguity (FR-007) — Owner: @frontend-css
- [X] T023 [US1] Frontend test in `apps/cabal-desktop/tests/envSources.test.tsx`: one tab per file, no value rendered on load, tabs rebuild on project change — Owner: @frontend-tester

**Checkpoint**: US1 is shippable on its own. This is the MVP.

---

## Phase 4: User Story 2 — Reveal one value (P1) 🎯 MVP

**Status**: ✅ Done (11/11 — T024–T034)
**Goal**: An explicit eye click fetches exactly one value; everything else stays masked; every reveal is audited.

**Independent test**: Click the eye on one row → only that row's value appears, and an audit record naming the entry (but not the value) exists.

### Contract tests first (Gate 3 — MUST fail before T027)

- [X] T024 [US2] Contract test `POST /api/env/reveal` in `setup/tests/contract/test_env_sources_contract.py` asserting R1, R2, R4, R5, R9 from `contracts/env-reveal.contract.md` — Owner: @python-tester
- [X] T025 [P] [US2] Contract test asserting R3 — a `never`-classified entry returns `unavailable` **without contacting the provider** — Owner: @python-tester
- [X] T026 [P] [US2] Contract test asserting R8 and R10 — no cache-permitting headers, and nothing written to disk during a reveal — Owner: @python-tester

### Implementation

- [X] T027 [US2] Implement single-entry reveal dispatch in `setup/src/cabal/webapi/envsources_service.py`, routing by `source_id` to the owning collector — Owner: @python-architect
- [X] T028 [US2] Implement `POST /api/env/reveal` in `setup/src/cabal/webapi/routers/environment.py`, returning `revealed`/`denied`/`unavailable` and auditing every call (FR-016) — Owner: @python-architect
- [X] T029 [US2] Implement reveal for repo config files (read from disk) in `setup/src/cabal/envsource_discovery.py` — Owner: @python-architect
- [X] T030 [US2] Build the eye control and its three retrievability states in `apps/cabal-desktop/src/modules/environment/components/RevealCell.tsx` — Owner: @react-architect
- [X] T031 [US2] Hold revealed values in component state only — never the query cache — and drop them on tab or project change (FR-014/15) in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.tsx` — Owner: @react-architect
- [X] T032 [US2] Style masked / revealed / disabled-with-reason states in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css` — Owner: @frontend-css
- [X] T033 [US2] Frontend test: revealing one row leaves every other masked; re-clicking re-masks; switching tab auto-masks — Owner: @frontend-tester
- [X] T034 [US2] Verify no revealed value reaches the query cache, in `apps/cabal-desktop/tests/envSources.test.tsx` — Owner: @frontend-tester

**Checkpoint**: US1 + US2 deliver the whole promise with no network, no auth, no external CLI. **Ship here.**

---

## Phase 5: User Story 7 — .NET layers and secret store (P2)

**Status**: ✅ Done (12/12 — T035–T046)
**Purpose**: Placed first among the P2 stories because it extends US1's local discovery, needs no network, and is what makes the feature honest for .NET work.

**Goal**: Fully-qualified keys, layer precedence, launch-profile variables, and the developer secret store that lives outside the repo.

**Independent test**: Open a .NET project keeping a connection string in its secret store → the key appears attributed to that store, badged as outside the repository, and hierarchical keys read as `Logging:LogLevel:Default`.

- [X] T035 [US7] Flatten hierarchical JSON to fully-qualified leaf paths using the framework's separator in `setup/src/cabal/envsource_dotnet.py` (FR-040) — Owner: @python-architect
- [X] T036 [P] [US7] Unit-test flattening in `setup/tests/test_envsource_dotnet.py`: nested sections, arrays, deep nesting, and that a section containing only sections is NOT listed as a key (FR-041) — Owner: @python-tester
- [X] T037 [US7] Parse `Properties/launchSettings.json` and attribute `environmentVariables` to their profile in `setup/src/cabal/envsource_dotnet.py` (FR-042) — Owner: @python-architect
- [X] T038 [US7] Compute `ConfigLayer` rank and `wins` across discovered .NET layers per the order confirmed in research R3, in `setup/src/cabal/envsource_dotnet.py` (FR-043) — Owner: @python-architect
- [X] T039 [P] [US7] Unit-test precedence: a key in `appsettings.Development.json` wins over `appsettings.json`; rows stay separate; no merged effective value is produced — Owner: @python-tester
- [X] T040 [US7] Resolve `<UserSecretsId>` from the project file in `setup/src/cabal/envsource_dotnet.py` (FR-044) — Owner: @python-architect
- [X] T041 [US7] Read the secret store from the platform path (research R4) and present it as its own source badged `outside_repository` (FR-045) — Owner: @python-architect
- [X] T042 [P] [US7] Unit-test the boundary: a store is read ONLY when the selected project declares its id, and the secrets directory is never enumerated (FR-047) — Owner: @python-tester
- [X] T043 [P] [US7] Unit-test that a declared-but-never-created store reports `empty`, not an error (FR-046) — Owner: @python-tester
- [X] T044 [US7] Show layer and winner on each row, and an "outside repository" badge, in `apps/cabal-desktop/src/modules/environment/components/EnvSourceTable.tsx` — Owner: @react-architect
- [X] T045 [US7] Style the layer indicator and outside-repository badge in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css` — Owner: @frontend-css
- [X] T046 [US7] Frontend test: qualified key paths render; the secret store appears as its own badged tab — Owner: @frontend-tester

**Checkpoint**: .NET projects show where values really live.

---

## Phase 6: User Story 3 — GitHub (P2)

**Status**: ✅ Done (8/8 — T047–T054)
**Goal**: Repository environments, variables, and secrets — with secrets showing a permanently disabled eye.

**Independent test**: Select a repo with environments → tab per environment plus repo-level; secret rows carry a disabled eye explaining the value can never be retrieved.

- [X] T047 [US3] Implement the GitHub collector in `setup/src/cabal/envsource_github_service.py` following the `dashboard_github_service.py` shape — Owner: @python-architect — Parallel: yes
- [X] T048 [US3] Classify every GitHub secret as `never` with a reason, and every variable as `readable` (FR-019) in `setup/src/cabal/envsource_github_service.py` — Owner: @python-architect — Parallel: yes
- [X] T049 [P] [US3] Unit-test the GitHub degradation matrix in `setup/tests/test_envsource_collectors.py`: `gh` absent, `gh` unauthenticated, repo with no environments (`empty`), no GitHub origin (absent) — Owner: @python-tester
- [X] T050 [P] [US3] Unit-test that a reveal on a GitHub secret returns `unavailable` without any network call — Owner: @python-tester
- [X] T051 [US3] Implement GitHub variable reveal in `setup/src/cabal/envsource_github_service.py` — Owner: @python-architect
- [X] T052 [US3] Render the permanently-disabled eye with its reason in `apps/cabal-desktop/src/modules/environment/components/RevealCell.tsx` — presented as a fact, never as an error (FR-018) — Owner: @react-architect
- [X] T053 [US3] Style the disabled reveal state distinctly from a failed one in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css` — Owner: @frontend-css
- [X] T054 [US3] Frontend test: secret rows never offer a working eye; variable rows do — Owner: @frontend-tester

---

## Phase 7: User Story 4 — Azure (P2)

**Status**: ✅ Done (11/11 — T055–T065)
**Goal**: Key vault and application environment names, with permission-gated reveal that degrades gracefully.

**Independent test**: Select an Azure-linked project → vault and environment names listed, link reason stated; a permission-denied reveal explains what access is required and leaves the rest usable.

- [X] T055 [US4] Implement the Azure link ladder (`explicit` → `azd` → `iac` → `machine_default`) in `setup/src/cabal/dashboard_links.py` — pure parsing, no subprocess (FR-030) — Owner: @python-architect
- [X] T056 [P] [US4] Unit-test the ladder in `setup/tests/test_envsource_collectors.py`: each signal wins in order, and a project with only `machine_default` is NOT presented as project-linked (FR-032) — Owner: @python-tester
- [X] T057 [US4] Implement the Azure collector in `setup/src/cabal/envsource_azure_service.py`: `az keyvault list`, `az webapp config appsettings list` — Owner: @python-architect — Parallel: yes
- [X] T058 [US4] Classify Key Vault secrets as `permission_gated` and app settings as `readable`; mark `@Microsoft.KeyVault(...)` values `is_reference` (FR-022) — Owner: @python-architect — Parallel: yes
- [X] T059 [P] [US4] Unit-test the Azure degradation matrix: `az` absent, `az` not signed in, subscription with no vaults (`empty`), collector timeout — Owner: @python-tester
- [X] T060 [US4] Implement Key Vault secret reveal via `az keyvault secret show`, mapping an RBAC refusal to `denied` naming the required role (FR-021) — Owner: @python-architect
- [X] T061 [P] [US4] Unit-test that a permission refusal yields `denied` with a role name, never a 5xx — Owner: @python-tester
- [X] T062 [US4] Render the link reason and the machine-default badge in `apps/cabal-desktop/src/modules/environment/components/EnvSourceTabs.tsx` (FR-031/32) — Owner: @react-architect
- [X] T063 [US4] Render `denied` in place on the row, leaving the rest of the list usable, in `apps/cabal-desktop/src/modules/environment/components/RevealCell.tsx` — Owner: @react-architect
- [X] T064 [US4] Style the machine-default badge so it reads as weaker than a real project link, in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css` — Owner: @frontend-css
- [X] T065 [US4] Frontend test: reference values render as references, not resolved secrets; denial is in-row, not a page error — Owner: @frontend-tester

---

## Phase 8: User Story 5 — Vercel (P3)

**Status**: ✅ Done (7/7 — T066–T072)
**Goal**: Environment variable names per deployment target, with `sensitive` entries never revealable.

**Independent test**: Select a Vercel-linked project → names grouped by target; `sensitive` rows carry a permanently disabled eye.

- [X] T066 [US5] Implement the Vercel collector in `setup/src/cabal/envsource_vercel_service.py` via REST with `VERCEL_TOKEN`, CLI as optional enrichment (research R7) — Owner: @python-architect — Parallel: yes
- [X] T067 [US5] Classify `type: "sensitive"` as `never` and others as `permission_gated` (FR-020) — Owner: @python-architect — Parallel: yes
- [X] T068 [P] [US5] Unit-test the Vercel degradation matrix: no `VERCEL_TOKEN` and no CLI, token rejected, no `.vercel/project.json` (absent), timeout — Owner: @python-tester
- [X] T069 [US5] Implement decrypt-based reveal for non-sensitive entries in `setup/src/cabal/envsource_vercel_service.py` — Owner: @python-architect
- [X] T070 [P] [US5] Unit-test that a `sensitive` entry never triggers a decrypt request — Owner: @python-tester
- [X] T071 [US5] Group entries by deployment target in `apps/cabal-desktop/src/modules/environment/components/EnvSourceTable.tsx` — Owner: @react-architect
- [X] T072 [US5] Frontend test: grouping by target; sensitive rows never offer a working eye — Owner: @frontend-tester

---

## Phase 9: User Story 6 — Explicit Azure link (P3)

**Status**: ✅ Done (7/7 — T073–T079)
**Goal**: Record a subscription/resource group for a project by hand; it beats every automatic signal and can be cleared.

**Independent test**: Record a scope for a project detection got wrong, reopen → the recorded scope is used and named as the reason.

- [X] T073 [US6] Persist `AzureProjectLink` keyed by project path in the app's platform data directory — the one permitted write (FR-025) — Owner: @python-architect
- [X] T074 [P] [US6] Unit-test that the explicit link outranks `azd`, `iac`, and `machine_default`, and that clearing restores automatic detection (FR-033) — Owner: @python-tester
- [X] T075 [US6] Add the record/clear route in `setup/src/cabal/webapi/routers/environment.py`, guarded by the existing prepare/confirm action flow — Owner: @python-architect
- [X] T076 [P] [US6] Verify nothing in this path writes to Azure, Vercel, or GitHub (FR-023) in `setup/tests/test_envsource_collectors.py` — Owner: @python-tester
- [X] T077 [US6] Build the record/clear affordance in `apps/cabal-desktop/src/modules/environment/components/EnvSourceEmptyState.tsx` — Owner: @react-architect
- [X] T078 [US6] Style the link editor in `apps/cabal-desktop/src/modules/environment/EnvironmentModule.css` — Owner: @frontend-css
- [X] T079 [US6] Frontend test: recording a scope updates the stated link reason; clearing reverts to automatic — Owner: @frontend-tester

---

## Phase 10: Polish & Cross-Cutting

**Status**: ✅ Done (9/9 — T080–T088)

- [X] T080 Rename the module to "Environment variables" in `apps/cabal-desktop/src/modules/registry.ts` (`MODULE_NAV_LABELS`, title) and update the matching release-note location string in `src/modules/release-notes/releaseNotes.ts` so the header docs dialog keeps resolving (FR-001) — Owner: @react-architect
- [X] T081 [P] Add a per-source refresh control that refetches one source without restarting the app (FR-038) — Owner: @react-architect
- [X] T082 [P] Verify the four outcomes are visually distinct — `not_linked` (absent), `empty`, `degraded`, `ok` (FR-037) — Owner: main (no UX reviewer in `agents.md`; see Roster drift below)
- [X] T083 [P] Wire-level assertion in `setup/tests/contract/test_env_sources_contract.py` that a full listing response contains zero `"value"` keys (quickstart check, FR-008) — Owner: @python-tester
- [X] T084 [P] Verify the audit trail after a browsing session contains one record per reveal and no values (SC-007) — Owner: @python-tester
- [X] T085 [P] Confirm a revealed value never lands on disk — search the project and the app data directory after a reveal (SC-008, FR-015) — Owner: @python-tester
- [X] T086 Measure first-usable-content under a deliberately hung collector; must stay within 3s (SC-010) — Owner: @frontend-tester
- [X] T087 Update `docs/` and the release-notes entry to describe the multi-source browser — Owner: main
- [X] T088 Read-only verification of the implementation against [plan.md](./plan.md) and all 47 requirements — Owner: @code-plan-verifier

---

## Dependencies

```text
Setup (T001–T003)
   └─> Foundational (T004–T010)   ← blocks every story
          ├─> US1 (T011–T023)  P1  ─┐
          │        └─> US2 (T024–T034)  P1  ─┴─> MVP, shippable
          ├─> US7 (T035–T046)  P2   (extends US1's discovery; no network)
          ├─> US3 (T047–T054)  P2   ─┐
          ├─> US4 (T055–T065)  P2   ─┼─ independent of each other
          ├─> US5 (T066–T072)  P3   ─┘
          │        └─> US6 (T073–T079)  P3   (needs US4's ladder)
          └─> Polish (T080–T088)
```

- **US2 depends on US1** — there must be entries before there is anything to reveal.
- **US6 depends on US4** — the explicit link is the top rung of US4's ladder.
- **US3, US4, US5, US7 are mutually independent** once Foundational lands.
- T018 must follow T011/T012; T028 must follow T024–T026 (Gate 3).

## Parallel execution (Gate 6)

One concurrent batch, matching the Parallel Execution Map in plan.md:

| Batch | Tasks | Agents | Isolation |
|---|---|---|---|
| Provider collectors | T047, T048 (GitHub) · T057, T058 (Azure) · T066, T067 (Vercel) | `@python-architect` ×3 | `isolation: "worktree"` each |

These touch three separate files with no shared state. Everything else is sequential — the `[P]`
marker elsewhere means "no dependency", not "dispatch concurrently", and those stay in one tree.

Merge each worktree branch back to `020-env-variable-sources` before starting the next phase.

## Roster drift (finding)

`@ux-analyst` exists in this harness and is the right owner for T010 and T082, but it is not in
`.specify/memory/agents.md`, and Gate 2 forbids naming agents the roster does not list. Both tasks
are assigned to `main` with the reason inline rather than inventing a name. `@frontend-designer`,
`@api-designer`, and `@solution-architect` are missing from the roster too. Reconciling
`agents.md` with the live roster deserves its own change; it is not folded into this feature.

## Implementation strategy

**Ship after Phase 4.** US1 + US2 need no network, no authentication, and no external CLI — they
work the moment the module opens and they answer the original complaint ("I can't see that it
fetches the settings from projects"). Everything after is an additive source.

**Then US7**, because .NET is the ecosystem where the values that matter are systematically not in
the files the repo contains, and it still needs nothing external.

**Then the cloud sources in confidence order**: GitHub (already authenticated on this machine),
Azure (signed in, but permissions vary), Vercel (CLI not installed — REST path only).

**Task count**: 88 total — Setup 3, Foundational 7, US1 13, US2 11, US7 12, US3 8, US4 11, US5 7,
US6 7, Polish 9.

---

## Implementation record (deviations from the plan)

Four things landed differently from what plan.md and data-model.md specified. Each is recorded
where it belongs as well; collected here so a reviewer sees them in one place.

1. **Test locations.** plan.md put the backend tests under `setup/tests/`. The webapi suites
   actually live in the repo-root `tests/` tree (`tests/contract/`, `tests/unit/`) alongside
   `webapi_fixtures.py`; `setup/tests/` holds the TUI and service tests. The real paths are
   `tests/contract/test_env_sources_contract.py` and `tests/unit/test_envsource_*.py`.

2. **`AvailabilityState` is the browser's own enum**, not an extension of the dashboard's.
   See the amendment note in data-model.md. Wire values are unchanged.

3. **`no_project_selected` is 404, not 409.** Both contracts said 409; every other
   project-scoped read in this app (`/api/docs`, `/api/security/scan`, `/api/dashboard`)
   answers 404, and `test_webapi_action_safety_contract.py`'s GET sweep asserts against that
   set. Both contract docs were corrected.

4. **Per-source refresh carries a much larger timeout than the first paint.** SC-010 caps first
   usable content at 3s, but `az keyvault list` plus a `secret list` per vault measured ~15s
   against a real subscription — so a single cap would have left Azure permanently reporting a
   timeout. The listing degrades fast (2.5s) and FR-038's per-source refresh
   (`GET /api/env/sources?source=<id>`) re-collects one source with a 45s budget. Both
   requirements are met; the wait is opt-in rather than paid on every page load.

**Not implemented, and not required by any FR:** Azure Container Apps (research defers it behind
App Service) and a merged .NET effective value (research R3 rules it out deliberately).
