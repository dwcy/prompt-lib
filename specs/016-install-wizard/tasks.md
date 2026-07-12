# Tasks: Installable Distribution with Installation Wizard

**Input**: Design documents from `/specs/016-install-wizard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md, quickstart.md

**Tests**: Included — the plan commits to test-first for the CLI contract and new services (`setup/tests/`).

**Organization**: Tasks grouped by user story from spec.md. All dispatch is **sequential** (Constitution Gate 6: N/A — no concurrent writers), so no task carries `Parallel: yes`; `[P]` marks logical independence only.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

## Phase 1: Setup

**Status**: ✅ Complete (1/1 — T001–T001)
**Purpose**: Baseline before touching anything

- [X] T001 Record a green baseline: run `python scripts/test-all.py --strict-missing` and note the result (any pre-existing failures are out of scope and must not be swept into this feature) — Owner: main
  - Baseline 2026-07-11: root suite FAILED `setup/tests/test_mcp_bus_registry.py::test_mcp_bus_status_returns_a_string`; orchestrator suite FAILED `tests/unit/test_worktree.py::test_acquire_SameKeyTwice_Serializes`; a2a-bridge + mcp-bus green. Both failures pre-exist this feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (3/3 — T002–T004)
**Purpose**: The install manifest is the entity every user story reads or writes; version single-sourcing feeds `--version` and the manifest

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Implement the install-manifest module in setup/src/cabal/install_manifest.py: `InstallManifest`/`ManagedFile` dataclasses per data-model.md, JSON load/save at `~/.claude/.cabal/install-manifest.json`, `in_progress → complete` journal helpers, history rotation to `~/.claude/.cabal/history/<timestamp>.json` capped at 10, path-traversal guard on `rel`, `schema_version = 1` (unknown version → treat as absent) — Owner: @python-architect
- [X] T003 Manifest unit tests in setup/tests/test_install_manifest.py: save/load roundtrip, journal transitions, unknown schema_version treated as absent, `..`/absolute `rel` rejected, history cap enforced, all against a tmp_path HOME — Owner: @python-tester
- [X] T004 Single-source the version: keep `cabal/__init__.py.__version__` authoritative and switch pyproject.toml to hatch dynamic versioning (`[tool.hatch.version] path = "setup/src/cabal/__init__.py"`); verify `python -m build --sdist` still resolves the version — Owner: @python-architect

**Checkpoint**: Manifest module tested; user stories can begin

---

## Phase 3: User Story 1 - Fresh-Machine Install (Priority: P1) 🎯 MVP

**Status**: ✅ Complete (6/6 — T005–T010)
**Goal**: One command installs the tool; wizard or headless apply deploys the payload, records the manifest, and ends with a verification summary

**Independent Test**: In a sandbox HOME, `python -m cabal apply --yes` deploys all components, writes a `complete` manifest, and prints the summary; `python -m cabal --version` reports the package version; the wizard path shows the same summary after apply

### Tests for User Story 1 (write first, observe failing)

- [X] T005 [US1] CLI behaviour tests in setup/tests/test_headless_cli.py locking down contracts/cli-contract.md before the implementation exists: `--version` output format, `apply --dry-run` (exit 0, nothing written), `apply` without `--yes` with pending changes (exit 3), `apply --yes` (exit 0, files deployed), `apply --json` schema keys, `--components` with unknown key (exit 2) and with required-core exclusion (exit 2), all against a sandbox HOME fixture (monkeypatched `cabal._paths.TARGET`) — Owner: @python-tester

### Implementation for User Story 1

- [X] T006 [US1] argparse entry layer in setup/src/cabal/__main__.py: zero args → run the Textual wizard unchanged; subcommands `apply`/`doctor`/`uninstall` dispatch to `cabal.headless`; `--version` prints `cabal <version> (<source_mode>)`; stays within the 250-LoC script budget — Owner: @python-architect
- [X] T007 [US1] Headless apply runner (landed as setup/src/cabal/apply_service.py + headless.py — orchestration extracted per plan's LoC-budget option) in setup/src/cabal/headless.py reusing `components`/`diff_apply` services: `--components` filter with required-core (`settings`, `claude_md`) always included, `--dry-run`, `--yes`, `--json` output and exit codes 0/2/3 per the contract; never prompts on non-TTY — Owner: @python-architect
- [X] T008 [US1] Manifest recording in the shared apply path (landed in setup/src/cabal/apply_service.py; diff_apply.py stays the diff/backup primitive layer): write manifest `in_progress` with planned files before the first write, record per-file `sha256`/`action`/`backup`, flip to `complete` after the last write; used identically by the wizard apply worker and headless.py — Owner: @python-architect
- [X] T009 [US1] Post-install verification summary: after apply, both the wizard update screen and headless output report created/updated/unchanged/backed_up counts, backup dir, and manifest path (US1 acceptance 1) — Owner: @python-architect
- [X] T010 [US1] Apply-integration tests in setup/tests/test_headless_cli.py: after `apply --yes` the manifest exists with `status: complete` and correct per-file records; a second `apply --yes` reports `up-to-date` with zero changes (SC-003) — Owner: @python-tester

**Checkpoint**: Fresh install works headlessly and via wizard, fully recorded — MVP

---

## Phase 4: User Story 2 - Safe Upgrade of an Existing Installation (Priority: P2)

**Status**: ✅ Complete (4/4 — T011–T014)
**Goal**: Re-running the installer previews, backs up, upgrades, and recovers cleanly from interrupted applies

**Independent Test**: Seed a sandbox HOME with an older deploy + manifest; run apply → preview shows changes, backups taken, manifest history rotated. Force-kill mid-apply (simulate by writing an `in_progress` manifest) → next run offers resume/rollback

### Implementation for User Story 2

- [X] T011 [US2] Interrupted-apply recovery API (landed as setup/src/cabal/recovery_service.py to avoid an import cycle; headless --yes path rewired through resume_interrupted()): detect `in_progress` manifest on any run; `resume` = re-apply (idempotent), `rollback` = restore the recorded `backup_dir`; headless exits 4 without `--yes`, resumes with `--yes` per the contract — Owner: @python-architect
- [X] T012 [US2] Wizard recovery modal (views/recovery_modal.py; wired in views/home.py on_mount and views/update.py action_apply): on wizard launch and before any apply, an `in_progress` manifest raises a modal offering Resume / Roll back / Review, wired to the T011 API; modal lives in setup/src/cabal/views/ (view + worker split per house rules) — Owner: @python-architect
- [X] T013 [US2] Upgrade-flow verification (all three guarantees verified in place; no gaps — evidence recorded in implementation report): declining the preview writes nothing (US2 acceptance 2), up-to-date runs short-circuit to `up-to-date` status without touching the manifest history, and machine-local/unmanaged files are untouched by apply (US2 acceptance 4) — verify existing behaviour and close any gap found in setup/src/cabal/diff_apply.py — Owner: @python-architect
- [X] T014 [US2] Upgrade + recovery tests (landed as setup/tests/test_recovery_service.py + test_recovery_modal.py + 2 additions to test_headless_cli.py): interrupted-apply detected, resume completes and flips to `complete`, rollback restores backups, decline-preview leaves disk identical, unmanaged file survives apply — Owner: @python-tester

**Checkpoint**: Upgrades are previewable, backed up, and crash-safe

---

## Phase 5: User Story 3 - Health Check and Repair (Priority: P3)

**Status**: ✅ Complete (4/4 — T015–T018)
**Goal**: Doctor compares disk against the manifest and bundled source, reports precise differences, and repairs only what differs

**Independent Test**: In a sandbox HOME with a completed install, delete one managed file and hand-edit another; `cabal doctor` reports both with correct classification; repair restores only those two files

### Implementation for User Story 3

- [X] T015 [US3] Manifest-aware doctor checks (landed as setup/src/cabal/manifest_doctor.py — config_doctor.py was near its 400-LoC cap; categories: missing-managed-file, stale-manifest, user-modified, interrupted-apply, version-skew, manifest-tampered): missing managed file, hash-mismatch classified `stale` (matches an older source) vs `user-modified` (matches neither manifest nor source), `in_progress` manifest, tool/manifest version skew — new findings reuse the existing `Finding` dataclass — Owner: @python-architect
- [X] T016 [US3] Headless `cabal doctor [--json]` in setup/src/cabal/headless.py: runs existing + new checks, exit codes 0 (healthy) / 1 (error findings) / 5 (no manifest, diff-fallback findings still reported), JSON shape per the contract — Owner: @python-architect
- [X] T017 [US3] Targeted repair (setup/src/cabal/repair_service.py + Repair action on ClaudeDoctorPanel; repair structurally excludes user-modified files): from doctor findings, re-deploy only the differing managed files (reuses the apply path with a file filter); exposed as a wizard action on the doctor panel and documented for headless as `cabal apply --yes` scoped follow-up; user-modified files are never repaired without explicit per-file confirmation in the wizard — Owner: @python-architect
- [X] T018 [US3] Doctor tests (landed as setup/tests/test_manifest_doctor.py + test_doctor_panel.py): deleted file detected, hand-edited file classified user-modified, exit codes 0/1/5, repair restores only differing files and skips user-modified ones — Owner: @python-tester

**Checkpoint**: Drift is detectable and repairable without a full redeploy

---

## Phase 6: User Story 4 - Clean Uninstall (Priority: P4)

**Status**: ✅ Complete (4/4 — T019–T022)
**Goal**: Remove exactly what cabal deployed, offer pre-install backup restoration, leave user files intact

**Independent Test**: Sandbox HOME with a completed install plus one user-authored agent file and one pre-install backed-up file; uninstall removes managed files, offers/performs backup restore, leaves the user agent untouched, and prints a removal summary

### Implementation for User Story 4

- [X] T019 [US4] Uninstall service in setup/src/cabal/uninstall_service.py (legacy mode removes only files byte-matching bundled source; everything else skipped as needs-review): manifest-driven removal of listed files (skip + report files whose hash matches neither manifest nor source), offer restore of manifest-referenced backups, remove `~/.claude/.cabal/` last, legacy component-diff fallback gated behind an explicit flag, no recursive directory sweeps — Owner: @python-architect
- [X] T020 [US4] Wizard uninstall screen in setup/src/cabal/views/uninstall.py (wired into home Claude Settings ops row; home has no Restore entry, so placement follows the op_screens pattern): preview (files to remove, files skipped as user-modified, backups available) → confirm → per-step report; view + worker split, within the 400-LoC view budget — Owner: @python-architect
- [X] T021 [US4] Headless `cabal uninstall [--restore-backups] [--dry-run] [--yes] [--legacy] [--json]` in setup/src/cabal/headless.py with exit codes 0/1/2/3/5 per the contract — Owner: @python-architect
- [X] T022 [US4] Uninstall tests in setup/tests/test_uninstall_service.py: manifest-driven removal, user-modified skip, backup restoration, `.cabal/` removed last, no-manifest exit 5 without `--legacy`, user-authored file survives — Owner: @python-tester

**Checkpoint**: All four user stories independently functional

---

## Phase 7: Polish, Docs & Release Readiness

**Status**: ✅ Complete (5/5 — T023–T027)
**Purpose**: Cross-cutting docs, the user-owned release procedure, and the verification gate

- [X] T023 [P] Write docs/release-runbook.md: ordered user-owned first-release steps from research.md R6 — name decision (record the verified PyPI `cabal` collision + `cabal-panel` recommendation), pyproject/release.yml rename edits, PyPI project + Trusted Publishing + GitHub `pypi` environment setup, test/wheel/exe gates, tagging rule — Owner: main
- [X] T024 [P] Update docs/release-readiness.md (name-collision finding, link to the runbook) and setup/README.md (CLI modes table: `apply`/`doctor`/`uninstall`/`--version`, manifest + uninstall rows in the Modes table) — Owner: main
- [X] T025 Local wheel gate (found + fixed a duplicate-asset force-include bug in pyproject.toml; wheel now builds clean with all required paths present): `python -m build`, then verify the wheel contains `cabal/_data/global`, `cabal/_data/setup/env`, `cabal/_data/setup/mcp-templates.json`, `cabal/__main__.py`; record the result in the runbook — Owner: main
- [X] T026 Full orchestrated test run `python scripts/test-all.py --strict-missing` green (compare against the T001 baseline) — Owner: main
  - 2026-07-12: only the pre-existing `setup/tests/test_mcp_bus_registry.py::test_mcp_bus_status_returns_a_string` failure remains (confirmed untouched by this feature via `git status`); the orchestrator's `test_worktree.py::test_acquire_SameKeyTwice_Serializes` failure from the T001 baseline did not recur (flaky). No new failures introduced.
- [X] T027 Read-only plan-compliance audit of the whole feature against plan.md and the contracts (verdict + findings; no edits) — Owner: @code-plan-verifier
  - 2026-07-12: **PASS WITH WARNINGS**. 415/415 setup tests pass; FR-007/008/010/011/017 verified with code evidence; CLI contract exit codes/JSON shapes match exactly; no stubs/TODOs/mock data; no Textual shadow-naming violations; Gate 4 and Gate 6 hold; no `v*` tag created, nothing pushed. Warnings: plan.md's file list had drifted from the actual module layout (fixed in this edit); `.claude/settings.local.json` carries an unrelated uncommitted change — excluded from this feature's commit; a few new modules (headless.py 348, uninstall_service.py 315) sit between soft/hard LoC caps — no split needed now.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup — T002 blocks everything; T004 independent of T002/T003
- **US1 (Phase 3)**: after Phase 2 — T005 (tests) before T006–T009; T010 after T008
- **US2 (Phase 4)**: after US1 (recovery rides on the manifest-recording apply path from T008)
- **US3 (Phase 5)**: after US1 (doctor reads manifests written by T008); independent of US2/US4
- **US4 (Phase 6)**: after US1 (uninstall reads manifests); independent of US2/US3
- **Polish (Phase 7)**: T023/T024 any time after planning; T025–T027 after all stories

### Within-story ordering

- Tests marked "write first" (T005) MUST be authored and observed failing before their implementation tasks start.
- T008 (manifest recording) is the pivot task — T011, T015, T019 all consume its output format.

### Parallel Opportunities

Dispatch is sequential by design (Gate 6: N/A). Logically independent pairs, if ever needed: T003∥T004, T023∥T024, US3∥US4 after US1.

---

## Implementation Strategy

**MVP first**: Phases 1–3 deliver the installable core (fresh install, headless + wizard, manifest, summary). Stop and validate US1 in a sandbox HOME before continuing. Then US2 (crash-safe upgrades), US3 (doctor), US4 (uninstall), and finally the release-readiness docs and gates. The actual `v0.1.0` tag is **not** a task — it stays user-owned per docs/release-readiness.md and the runbook.

---

## Notes

- Every service touches `~/.claude/` only through `cabal._paths.TARGET` so tests can sandbox HOME.
- LoC budgets per `~/.claude/rules/python.md` (library 200/400, views 250/400, `__main__` 150/250, tests 300/500).
- No new skills/agents; no `global/` edits; no pushes or tags.
