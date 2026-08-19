# Tasks: Agent Eval & Regression Harness

**Input**: Design documents from `/specs/019-agent-eval-harness/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. Contract tests are MANDATORY (Constitution Gate 3 — the artifact schemas, definition file formats, and adapter interface are this feature's protocol surfaces) and MUST be observed failing before their implementation tasks. Unit tests are included because plan.md explicitly plans them.

**Organization**: Tasks grouped by user story (spec.md US1–US6, P1–P6) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **Parallel: yes**: will be dispatched concurrently with another writing task → `/speckit-implement` passes `isolation: "worktree"` (Constitution Gate 6)
- Owners come from `.specify/memory/agents.md`; `main` only where no specialist fits

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (2/2 — T001–T002)
**Purpose**: Package skeleton and versioned eval-data tree

- [X] T001 Create package skeleton `setup/src/cabal/evals/` per plan.md structure — `__init__.py`, `__main__.py` (delegates to `cli.main`, mirroring `cabal/dotnetgen/__main__.py`), `cli.py` with argparse subcommand scaffolding for `validate|run|judge|report` (each exits 2 "not implemented" for now), empty `adapters/__init__.py`; one-line module docstrings everywhere per python.md — Owner: @python-architect
- [X] T002 [P] Scaffold eval-data tree at repo root: `evals/eval.config.toml` (defaults per contracts/definitions-format.md), empty `evals/tasks/`, `evals/rubrics/`, `evals/configs/` with `.gitkeep`, and add `evals/results/` to `.gitignore` — Owner: main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Status**: ✅ Complete (7/7 — T003–T009)
**Purpose**: Contract tests pinned first (Gate 3), then the shared core every story needs: definitions loading, adapter seam, worktree lifecycle, profile materialization

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. T003/T004 MUST be written and observed FAILING before T005–T008.

- [X] T003 [P] Contract test for definition file formats in `setup/tests/contract/test_evals_definitions.py` — pins `task.toml` / `profile.toml` / `eval.config.toml` shapes and every validation rule in contracts/definitions-format.md (unknown keys rejected, ref resolution, in-profile path confinement, ≥1 check, id pattern); run and observe failing — Owner: @python-tester — Parallel: yes
- [X] T004 [P] Contract test for artifact schemas + adapter interface in `setup/tests/contract/test_evals_artifacts.py` — validates fixture `metrics.json`/`comparison.json`/`report.json` against `specs/019-agent-eval-harness/contracts/*.schema.json` via `jsonschema` (null-vs-zero rule, order_agreement→tie invariant, schema_version) and pins the `AgentAdapter` protocol per contracts/agent-adapter.md using a `FakeAdapter`; run and observe failing — Owner: @python-tester — Parallel: yes
- [X] T005 Implement definition loaders/validators in `setup/src/cabal/evals/definitions.py` — `Task`, `CheckSpec`, `ConfigProfile`, `EvalConfig` dataclasses + `load_*`/`validate_tree()` reporting file+field per error, `tomllib`-based (makes T003 pass) — Owner: @python-architect
- [X] T006 Implement adapter seam in `setup/src/cabal/evals/adapters/base.py` (`AgentAdapter` protocol, `AgentRunSpec`, `AgentRunResult`, `AdapterCapabilities`, `AdapterUnavailableError`) and name registry in `setup/src/cabal/evals/adapters/__init__.py` (makes T004's adapter section pass) — Owner: @python-architect
- [X] T007 Implement worktree lifecycle in `setup/src/cabal/evals/worktree.py` — `add --detach` at pinned ref, diff collection (`add -N` + `diff` → patch.diff, `status --porcelain` → changed files, insertions/deletions stats), `remove --force` with prune fallback, per research.md R4 — Owner: @python-architect
- [X] T008 Implement profile materialization in `setup/src/cabal/evals/profile.py` — synthesize per-run scratch `CLAUDE_CONFIG_DIR` from `user_overlay`, copy `project_overlay` into worktree, resolve `settings_file`/`env`, byte-identical baseline/candidate → `no-op comparison` warning — Owner: @python-architect
- [X] T009 Unit tests for worktree + profile in `setup/tests/test_evals_worktree.py` — scratch git repo fixture (tmp_path), full add→mutate→collect→remove cycle, untracked-file diff, unreachable-ref error, profile materialization confinement — Owner: @python-tester

**Checkpoint**: Foundation ready — user story phases can begin

---

## Phase 3: User Story 1 - A/B compare two configurations on a task set (Priority: P1) 🎯 MVP

**Status**: 🟡 In progress (1/7 — T010–T016)
**Goal**: `python -m cabal.evals run --baseline X --candidate Y --runs N` executes the full matrix with per-run worktrees, config isolation, artifact capture, incremental resume, and failure isolation

**Independent Test**: One task, two profiles (candidate = baseline + one skill), `--runs 1` → per-run `patch.diff`/`output.txt`/`transcript.jsonl`/`metrics.json` exist and validate against the schemas; interrupt + `--resume` skips the completed cell

- [X] T010 [US1] Smoke-verify config isolation on this machine: run live `claude -p` with a relocated `CLAUDE_CONFIG_DIR` (auth resolution, skills/CLAUDE.md pickup) and `--permission-mode acceptEdits --output-format stream-json` headless flags; record confirmed behavior (or the credential-copy fallback) in research.md R2/R3 — Owner: main (done: relocation honored, credential-copy fallback REQUIRED — see research.md R2; CLAUDE.md pickup deferred to T031 marker check)
- [ ] T011 [US1] Implement Claude Code adapter in `setup/src/cabal/evals/adapters/claude_code.py` per contracts/agent-adapter.md — one-shot `claude -p` with stream-json capture to `transcript_path`, timeout process-tree kill → `failed/agent_timeout`, `is_error`/missing-result → `agent_crash`, `skip_permissions` flag handling — Owner: @python-architect — Parallel: yes
- [ ] T012 [P] [US1] Implement metrics extraction in `setup/src/cabal/evals/metrics.py` — transcript.jsonl → tool_calls_total/by_name, num_turns, tokens/cost (absence → `null`, never 0, mirroring `dotnetgen.providers.usage` semantics), merge diff stats + wall time + status into schema-valid `metrics.json` — Owner: @python-architect — Parallel: yes
- [ ] T013 [US1] Implement matrix engine in `setup/src/cabal/evals/matrix.py` — cell enumeration (tasks × 2 configs × N), run-id creation, per-cell orchestration (worktree → profile → adapter → collect → metrics), atomic `.tmp`→rename writes, resume-skips-completed, per-cell failure capture that never aborts the matrix (FR-011/FR-012) — Owner: @python-architect
- [ ] T014 [US1] Wire `run` subcommand in `setup/src/cabal/evals/cli.py` — `--baseline`, `--candidate`, `--runs`, `--tasks <id,…>`, `--resume <run-id>`, `--adapter`, exit codes (0 all cells done, 1 some failed, 2 config error) — Owner: @python-architect
- [ ] T015 [P] [US1] Unit tests for metrics in `setup/tests/test_evals_metrics.py` — recorded stream-json fixture transcripts under `setup/tests/fixtures/evals/` (success, error-result, missing-usage), null-not-zero assertions, tool-call bucketing — Owner: @python-tester
- [ ] T016 [US1] Unit tests for matrix in `setup/tests/test_evals_matrix.py` — FakeAdapter-driven: enumeration order, resume skips cells with valid metrics.json, injected adapter failure isolates to its cell, no-op profile warning surfaces, atomic-write crash simulation leaves no half-written metrics.json — Owner: @python-tester

**Checkpoint**: MVP — a real matrix runs end-to-end and survives failures; only judging/reporting missing

---

## Phase 4: User Story 2 - Author tasks, rubrics, and configurations as versioned files (Priority: P2)

**Status**: 🟡 In progress (1/3 — T017–T019)
**Goal**: `python -m cabal.evals validate` verifies the whole `evals/` tree with file+field precision; real seed benchmark content exists

**Independent Test**: `validate` on the seeded tree passes; corrupting a ref/rubric/profile path produces the exact expected error strings

- [ ] T017 [US2] Wire `validate` subcommand in `setup/src/cabal/evals/cli.py` over `definitions.validate_tree()` — human-readable per-error output (`<file>: <field>: <problem>`), exit 0/1, `--tasks` filter — Owner: @python-architect
- [X] T018 [P] [US2] Author seed benchmark content: `evals/rubrics/architecture.md`, `evals/rubrics/coding-quality.md`, `evals/rubrics/instruction-following.md` (each with a `## Criteria` bullet list), example task `evals/tasks/001-sample-task/` (task.toml + prompt.md pinned to a ref in this repo), and profiles `evals/configs/baseline/` + `evals/configs/candidate-example/` per contracts/definitions-format.md — Owner: main
- [ ] T019 [US2] Validate-command tests in `setup/tests/test_evals_validate.py` — good tree passes; bad ref, missing rubric, out-of-profile absolute/`..` path, empty prompt.md, unknown TOML key each fail with file+field named — Owner: @python-tester

**Checkpoint**: Benchmark-as-code authoring loop closed (author → validate → fix)

---

## Phase 5: User Story 3 - Deterministic code checks per run (Priority: P3)

**Status**: ⬜ Pending (0/3 — T020–T022)
**Goal**: Every run's `metrics.json` carries check outcomes (test/build/lint with parsed counts) and unrequested-change scope measurement

**Independent Test**: Task whose check is a pytest suite → metrics.json records passed/failed counts, build result, and files changed outside `expected_files`

- [ ] T020 [US3] Implement deterministic checks in `setup/src/cabal/evals/checks.py` — ordered `CheckSpec` execution in the worktree, per-check timeout kill → `timeout` status, `pytest`/`dotnet`/`exit-code` output parsers for passed/failed counts, `expected_files` glob scope → `unrequested_changes_count`/`unrequested_files` — Owner: @python-architect
- [ ] T021 [US3] Integrate checks into the run pipeline in `setup/src/cabal/evals/matrix.py` + `metrics.py` — checks execute after the agent finishes (also on empty diff), results land in metrics.json `checks[]` and diff group per metrics.schema.json — Owner: @python-architect
- [ ] T022 [P] [US3] Unit tests in `setup/tests/test_evals_checks.py` — parser fixtures (pytest/dotnet output samples), exit-code default, hanging-command timeout kill, scope-glob matching incl. Windows path separators — Owner: @python-tester

**Checkpoint**: Runs now self-grade deterministically

---

## Phase 6: User Story 4 - LLM pairwise judge with rubrics (Priority: P4)

**Status**: ⬜ Pending (0/3 — T023–T025)
**Goal**: `python -m cabal.evals judge <run-id>` produces schema-valid `comparison.json` per task with both-orders position-bias control

**Independent Test**: Judge two pre-recorded run cells → comparison.json with winner/confidence/criteria; force order-disagreement via stub → recorded as tie

- [ ] T023 [US4] Implement pairwise judge in `setup/src/cabal/evals/judge.py` — build judge prompt (task prompt + rubric files verbatim + both cells' patch.diff/output.txt/check summaries, per-file truncation at `judge.diff_char_limit` with `truncated` flag), one-shot `claude -p` JSON-only verdict, judge both A/B orders, disagreement → `tie` + `order_agreement: false`, call failure → `judge_error` with detail, repetition-i pairing — Owner: @python-architect
- [ ] T024 [US4] Wire `judge` subcommand in `setup/src/cabal/evals/cli.py` — standalone over a recorded results dir (FR-014), `--tasks` filter, re-judge overwrites prior comparison.json atomically — Owner: @python-architect
- [ ] T025 [P] [US4] Unit tests in `setup/tests/test_evals_judge.py` — stubbed judge callable: both-orders agreement/disagreement/tie matrix, malformed judge JSON → judge_error, truncation flag set, schema-valid output — Owner: @python-tester

**Checkpoint**: Quality dimension measured; deterministic metrics remain primary

---

## Phase 7: User Story 5 - Aggregate report across tasks and runs (Priority: P5)

**Status**: ⬜ Pending (0/3 — T026–T028)
**Goal**: `python -m cabal.evals report <run-id>` renders the baseline-vs-candidate table (terminal via rich + report.json/report.md)

**Independent Test**: Point `report` at a recorded results dir → table with ≥7 metric rows and both config columns; failed runs counted against task pass rate but excluded from quality means

- [ ] T026 [US5] Implement aggregation in `setup/src/cabal/evals/report.py` — reduce all metrics.json + comparison.json into report.json per report.schema.json: task/test/build pass rates, unrequested changes, tool calls, tokens, wall time, pairwise win rate (ties excluded), mean/min/max/stddev when n≥3, failure inventory, failed-run exclusion rules per data-model.md — Owner: @python-architect
- [ ] T027 [US5] Wire `report` subcommand in `setup/src/cabal/evals/cli.py` — rich table to terminal, persist `report.json` + `report.md` into the run-id dir — Owner: @python-architect
- [ ] T028 [P] [US5] Unit tests in `setup/tests/test_evals_report.py` — aggregation math against hand-computed fixtures, variance only at n≥3, failed-run handling, win-rate tie exclusion, schema-valid report.json — Owner: @python-tester

**Checkpoint**: The headline question ("which config won?") is answered end-to-end

---

## Phase 8: User Story 6 - Multiple agent CLIs (Priority: P6)

**Status**: ⬜ Pending (0/2 — T029–T030)
**Goal**: Adapter selection is config-driven and the null-capability path works end-to-end, proving Codex/Gemini adapters can drop in without core changes (real second adapter deferred per plan)

**Independent Test**: Matrix run with a registered FakeAdapter lacking token capability → identical artifact schema with token fields `null`

- [ ] T029 [US6] Config-driven adapter selection end-to-end — `eval.config.toml` `adapter` + `run --adapter` override resolve through the registry in `setup/src/cabal/evals/adapters/__init__.py`; unknown name fails at validate time; document the drop-in contract for future `codex`/`gemini` adapters in the registry module docstring — Owner: @python-architect
- [ ] T030 [P] [US6] Adapter registry + capability tests in `setup/tests/test_evals_adapters.py` — registry resolution, unknown-adapter error, capability-gated `null` metrics flow through matrix → metrics.json (US6-AS2) — Owner: @python-tester

**Checkpoint**: All user stories independently functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Status**: ⬜ Pending (0/4 — T031–T034)
**Purpose**: Live verification, docs, full suite, independent audit

- [ ] T031 Execute the quickstart.md smoke test live: `validate` → 1-task × 2-config × 1-run matrix → `judge` → `report` with the real `claude` CLI; fix any fallout; confirm SC-005 (no writes outside worktrees/scratch/results — check `git status` on main tree + `~/.claude` untouched) — Owner: main
- [ ] T032 [P] Documentation: add `evals/README.md` (authoring guide distilled from contracts/definitions-format.md) and register the `cabal.evals` module in `setup/src/cabal/README.md` — Owner: main
- [ ] T033 Full test pass: `python -m pytest setup/tests -k evals` green, plus python.md size-cap self-audit on every new module (soft 200 / hard 400 LoC) — Owner: main
- [ ] T034 Read-only plan-compliance audit of the implementation against plan.md, contracts/, and constitution gates; PASS required before the completion commit — Owner: @code-plan-verifier

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately; T001 ∥ T002
- **Foundational (Phase 2)**: needs Phase 1. T003 ∥ T004 first (contract tests, observed failing — Gate 3), then T005–T008 (T005 after T003; T006 after T004; T007/T008 after T001), T009 after T007+T008
- **US1 (Phase 3)**: needs Phase 2. T010 anytime after Phase 1 (independent live smoke); T011 ∥ T012 (after T006/T010 and T004 respectively); T013 after T005+T007+T008+T011+T012; T014 after T013; T015 after T012; T016 after T013
- **US2 (Phase 4)**: needs T005. Independent of US1 (T017 ∥ US1 work possible); T018 anytime after T002; T019 after T017
- **US3 (Phase 5)**: needs US1's T013 (pipeline hook). T020 after T005; T021 after T013+T020; T022 after T020
- **US4 (Phase 6)**: needs US1 artifacts + US3 check summaries. T023 after T021; T024 after T023; T025 after T023
- **US5 (Phase 7)**: needs metrics (US1/US3) for deterministic rows; judge rows degrade gracefully, but full report after US4. T026 after T021 (+T023 for win rate); T027 after T026; T028 after T026
- **US6 (Phase 8)**: needs T006+T013. T029 then T030
- **Polish (Phase 9)**: needs all desired stories; T031 after US5; T034 last

### Story independence notes

US2 (validate) is independent of US1 once foundational `definitions.py` exists. US3–US5 form the evaluation pipeline and intentionally build on US1's matrix (integration, not violation — each remains independently testable against recorded fixtures).

### Parallel Opportunities

- T001 ∥ T002 (different trees)
- T003 ∥ T004 — both marked `Parallel: yes` (two @python-tester writers, concurrent dispatch → worktree isolation each)
- T011 ∥ T012 — both marked `Parallel: yes` (adapter vs metrics, different files, different fixtures)
- Test tasks marked [P] (T015, T022, T025, T028, T030) can run alongside the next phase's architect task when dispatched sequentially-per-writer; only mark them concurrent if actually batched
- T018 (seed content, `main`) can proceed any time after T002

## Parallel Example: Foundational contract tests

```text
# Concurrent dispatch (each writer isolated per Gate 6):
Agent(subagent_type="python-tester", isolation="worktree",
      prompt="T003: contract test for definition formats … observed failing")
Agent(subagent_type="python-tester", isolation="worktree",
      prompt="T004: contract test for artifact schemas + adapter protocol … observed failing")
```

## Implementation Strategy

### MVP First (US1)

1. Phases 1–2 (setup + foundational, contract tests failing first)
2. Phase 3 (US1) → **STOP and VALIDATE**: run the independent test (1 task × 2 configs × 1 run, resume check)
3. A real matrix already produces diffable artifacts — judging/reporting can wait

### Incremental Delivery

Each subsequent phase closes one loop: US2 authoring/validation → US3 self-grading runs → US4 quality verdicts → US5 the headline report → US6 adapter proof. Every checkpoint is shippable; commit per completed phase (per-feature commits, git-identity wrapper, plan-completion auto-commit rules apply).

## Notes

- Constitution Gate 3 satisfied: T003/T004 precede all implementation of the surfaces they pin
- Gate 6 satisfied: only T003∥T004 and T011∥T012 are concurrent writer batches; both marked `Parallel: yes`
- Respect the 4-concurrent-subagent cap from CLAUDE.md — the marked batches are pairs, well under it
- New modules obey python.md caps (200 soft / 400 hard LoC) — the pre-split module layout in plan.md exists precisely for this
