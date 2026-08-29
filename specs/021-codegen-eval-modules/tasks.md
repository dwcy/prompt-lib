---
description: "Task list for 021-codegen-eval-modules"
---

# Tasks: Codegen & Eval Workspace Modules

**Input**: Design documents from `/specs/021-codegen-eval-modules/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Contract tests are **mandatory** here, not optional. Constitution Gate 3 binds four protocol surfaces (`contracts/`), and each contract test task appears before its implementation tasks. Unit and UI tests are included where a requirement is easy to satisfy incorrectly.

**Organization**: Tasks are grouped by user story so each story ships independently.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US8, mapping to spec.md user stories
- **Owner**: from `.specify/memory/agents.md`
- **Parallel: yes**: dispatched concurrently — `/speckit-implement` passes `isolation: "worktree"` (Constitution Gate 6)

## The constraint that shapes this whole list

Phase 2 is **sequential and blocking**. Both modules sit on `run_supervisor.py`, and per research.md R1 the run-ownership model is the one decision everything else inherits: runs are detached OS processes, the artifact tree is the source of truth, the job record is a live view. Building any module surface before that exists means building it twice.

Nothing in Phase 3+ may start until Phase 2 is complete.

---

## Phase 1: Setup (Shared Infrastructure)

**Status**: ✅ Complete (6/6 — T001–T006)
**Purpose**: Create the skeletons both modules fill in. No behaviour yet.

- [X] T001 [P] Create backend service stubs `setup/src/cabal/webapi/run_supervisor.py`, `codegen_service.py`, `evals_service.py`, `evals_definitions_service.py` — Owner: @python-architect
- [X] T002 [P] Create action catalog stubs `setup/src/cabal/webapi/actions_catalog/codegen.py` and `actions_catalog/evals.py`, registered in the existing catalog index — Owner: @python-architect
- [X] T003 [P] Create router stubs `setup/src/cabal/webapi/routers/codegen.py` and `routers/evals.py`, mounted in `setup/src/cabal/webapi/app.py` — Owner: @python-architect
- [X] T004 [P] Create frontend module trees `apps/cabal-desktop/src/modules/codegen/` and `modules/evals/`, each with `components/` and `hooks/` — Owner: @react-architect
- [X] T005 [P] Create typed API clients `apps/cabal-desktop/src/api/codegen.ts` and `api/evals.ts` — Owner: @react-architect
- [X] T006 Register both modules in `apps/cabal-desktop/src/modules/registry.ts`, routed to the existing `ModuleUnavailable` placeholder until their phases land — Owner: @react-architect

---

## Phase 2: Foundational (BLOCKING — sequential, single owner)

**Status**: 🟡 In progress (8/9 — T007–T015; only T012b remains, deferred to the launch actions in T029/T050)
**Purpose**: The run-supervision layer. Everything else depends on it.

⚠️ **Do not parallelise this phase and do not start Phase 3 before it completes.** One owner, in order — see research.md R1/R2/R7.

- [X] T007 Contract test for the SSE run-event grammar in `tests/contract/test_run_events.py` — assert a client that disconnects longer than the 200-frame ring buffer and reconnects with `Last-Event-ID` still reaches correct state, and that a gap is signalled explicitly rather than silently — Owner: @python-tester
- [X] T008 Implement detached process launch and PID tracking in `setup/src/cabal/webapi/run_supervisor.py` — the process must survive backend exit (research.md R1) — Owner: @python-architect
- [X] T009 Implement read-time state reconciliation in `run_supervisor.py`: process alive → `running`; process gone + artifacts complete → the artifacts' outcome; process gone + artifacts incomplete → `interrupted` — Owner: @python-architect
- [X] T010 Ensure `interrupted` is a derived presentation state only, never written to the `jobs` table state column, so the existing job state machine and its other consumers are untouched — Owner: @python-architect
- [X] T011 Implement the post-restart exclusive-resource liveness check in `run_supervisor.py` — the in-memory `_resources` lock is lost on restart while a detached run may still be live (research.md R7) — Owner: @python-architect
- [ ] T012 Emit structured `run.progress` and `run.state` events carrying **absolute** position, not deltas, per `contracts/run-events.md` — Owner: @python-architect
  - [X] T012a Structured-event **channel**: one sequence space in `jobs.py` carrying both output lines and typed events, rendered by `sse.py` through the same Last-Event-ID/gap machinery, so a single reconnect header resumes both — Owner: @python-architect
  - [ ] T012b Actual **emission** from the supervisor. `run_supervisor.py` emits nothing today; the contract test goes green via the `test.job_emitter` fixture, which proves the grammar but not the producer. A run only produces progress once something tails the detached process, so this lands with the launch actions — verify in T029 (codegen) and T050 (evals) that events come from a real run, not a fixture — Owner: @python-architect
- [X] T013 Implement process-tree cancellation reusing `cabal.evals.proc.kill_process_tree`, with temporary-worktree cleanup — Owner: @python-architect
- [X] T014 Implement `ModuleAvailability` probes for both modules per data-model B3, keeping `no_benchmark_tree` (setup state) and `definitions_invalid` (error) distinct — Owner: @python-architect
- [X] T015 Integration tests for the reconciliation state machine in `tests/integration/test_run_supervisor.py`, including the stranded-`running` case that motivated it — Owner: @python-tester

---

## Phase 3: US1 — Generate .NET code and decide at the approval gate (P1)

**Status**: ⬜ Pending (0/14 — T016–T029)
**Goal**: A complete, useful generator: prose request → reviewable plan → explicit decision → written and verified code.
**Independent test**: Submit a change request, confirm the run pauses with a readable plan and the working tree is byte-identical, reject it and confirm the tree is still clean, then repeat and approve and confirm only the described files were written.

- [ ] T016 [P] [US1] Contract test for the codegen API in `tests/contract/test_codegen_api.py` per `contracts/codegen-api.md` — gate shape, digest bound to the intent token, stale refusal, replay refusal, the working-tree-unchanged assertion, and that every mutating action writes an audit entry (FR-006) — Owner: @python-tester
- [ ] T017 [US1] Implement the read surface in `setup/src/cabal/webapi/codegen_service.py`: run list, run detail, pending intent with computed `stale` — Owner: @python-architect — Parallel: yes
- [ ] T018 [US1] Implement the `codegen.plan` action in `actions_catalog/codegen.py` — spawns detached, returns immediately, writes nothing to the target project — Owner: @python-architect — Parallel: yes
- [ ] T019 [US1] Implement the `codegen.approve` action with `compute_digest` bound to the pending intent's token, so the webapi ticket and the subsystem's own gate cannot disagree (research.md R3) — Owner: @python-architect — Parallel: yes
- [ ] T020 [US1] Implement the `codegen.reject` action — clears the intent, records outcome `rejected at gate`, writes an audit entry — Owner: @python-architect — Parallel: yes
- [ ] T021 [US1] Implement the `codegen.new_service` action with destination resolved relative to the selected project, post-normalisation escape refusal (`400 destination_outside_project`) and non-empty refusal (`409 destination_not_empty`) per research.md R10 — Owner: @python-architect — Parallel: yes
- [ ] T022 [US1] Wire the read endpoints in `setup/src/cabal/webapi/routers/codegen.py` — Owner: @python-architect — Parallel: yes
- [ ] T023 [P] [US1] Review the approval-gate presentation for states, edge cases, and how a stale or expired plan reads — Owner: @ux-analyst
- [ ] T024 [US1] Build `apps/cabal-desktop/src/modules/codegen/CodegenModule.tsx` — module shell, project gate, prose request form, template selection, and the new-service destination control constrained to paths inside the selected project (FR-011a, SC-014) — Owner: @react-architect — Parallel: yes
- [ ] T025 [US1] Build `modules/codegen/components/ApprovalGate.tsx` — intended-file-change list, explicit approve and reject controls, stale-plan banner. Must never proceed on timeout or navigation — Owner: @react-architect — Parallel: yes
- [ ] T026 [US1] Build `modules/codegen/components/RunOutcome.tsx` rendering the four persisted outcomes from `run-record.schema.json` (`completed`, `rejected_at_gate`, `halted_at_ceiling`, `aborted_environment`) distinctly, plus the no-run-record case where the process failed outright. `aborted_environment` vs `halted_at_ceiling` IS the environment-vs-defect distinction (FR-017) — see data-model A3; do not invent a sixth outcome from CLI exit codes — Owner: @react-architect — Parallel: yes
- [ ] T027 [P] [US1] CSS for the codegen module — Owner: @frontend-css
- [ ] T028 [P] [US1] Vitest + RTL coverage for the gate and outcome components in `apps/cabal-desktop/tests/` — Owner: @frontend-tester
- [ ] T029 [US1] Playwright end-to-end: working tree unchanged at the gate; reject leaves it clean; approve applies only the listed files; the gate survives a full app restart — Owner: @frontend-tester

---

## Phase 4: US2 — Read the A/B verdict for a completed eval run (P1)

**Status**: ⬜ Pending (0/12 — T030–T041)
**Goal**: The payload of the entire harness — did the candidate beat the baseline, and on what evidence.
**Independent test**: Point the module at a run directory the CLI produced and confirm the comparison renders correctly, with no ability to launch anything.

- [ ] T030 [P] [US2] Contract test for the evals report payload in `tests/contract/test_evals_api.py` per `contracts/evals-api.md` — every aggregate carries `n`; `stddev` absent below n=3; excluded-pair counts present; `order_agreement: false` reported as a tie; every mutating action writes an audit entry (FR-006) — Owner: @python-tester
- [ ] T031 [US2] Implement run listing in `setup/src/cabal/webapi/evals_service.py` reading `evals/results/`, with state reconciled at read time and no "launched here" flag — Owner: @python-architect — Parallel: yes
- [ ] T032 [US2] Implement the report endpoint by delegating to the subsystem's own reducer — never re-derive the aggregation rules (SC-010) — Owner: @python-architect — Parallel: yes
- [ ] T033 [US2] Implement the cell-detail endpoint, returning a timed-out check as a result with a timeout flag rather than an error — Owner: @python-architect — Parallel: yes
- [ ] T034 [US2] Ensure the deterministic half of a report still returns when judge results are absent (FR-043) — Owner: @python-architect — Parallel: yes
- [ ] T035 [P] [US2] Review the comparison view for how contested and partial evidence reads — ties from order disagreement, judge errors, low-n aggregates, and excluded pairs must not resolve into a false clean winner — Owner: @ux-analyst
- [ ] T036 [US2] Build `apps/cabal-desktop/src/modules/evals/EvalsModule.tsx` — module shell and run list — Owner: @react-architect — Parallel: yes
- [ ] T037 [US2] Build `modules/evals/components/ComparisonView.tsx` — per-metric baseline vs candidate, per task and aggregated, every figure showing its `n`. Renders numbers only; computes nothing — Owner: @react-architect — Parallel: yes
- [ ] T038 [US2] Build `modules/evals/components/CellDetail.tsx` drill-down into a single cell's checks and agent metrics — Owner: @react-architect — Parallel: yes
- [ ] T039 [P] [US2] CSS for the evals module — Owner: @frontend-css
- [ ] T040 [P] [US2] Vitest + RTL: a tie renders as a tie, excluded pairs are visible, a low-n metric shows no spread, an absent judge degrades rather than empties the view — Owner: @frontend-tester
- [ ] T041 [US2] Verify SC-010: workspace figures match `python -m cabal.evals report <run-id>` for the same run, with no divergence in any aggregate — Owner: @python-tester

---

## Phase 5: US3 — Launch and watch an eval matrix (P2)

**Status**: ⬜ Pending (0/9 — T042–T050)
**Goal**: Start a matrix from the workspace and watch it, with the run outliving the window.
**Independent test**: Launch a one-task one-repetition matrix, navigate away and back mid-run, then close and reopen the workspace, and confirm state is accurate throughout.

- [ ] T042 [US3] Implement the `evals.launch` action — refuse with `409 definitions_invalid` when the tree fails validation, spawn detached, return the isolated config directory the run will use — Owner: @python-architect — Parallel: yes
- [ ] T043 [US3] Implement the `evals.cancel` action — terminate the process tree, clean up temporary worktrees, leave partial results readable, idempotent on a finished run — Owner: @python-architect — Parallel: yes
- [ ] T044 [US3] Emit `cell.complete` events carrying absolute `completed`/`total` so a client that missed earlier cells still shows correct progress — Owner: @python-architect — Parallel: yes
- [ ] T045 [US3] Build `modules/evals/components/MatrixLauncher.tsx` — baseline profile, candidate profile, task subset, repetitions — Owner: @react-architect — Parallel: yes
- [ ] T046 [US3] Build `modules/evals/components/LiveMatrix.tsx` — per-cell progress over SSE, rebuilding state from artifacts plus events after a reconnect gap — Owner: @react-architect — Parallel: yes
- [ ] T047 [US3] Build the config-isolation indicator making visible that the run never touched the user's real agent configuration (FR-034) — Owner: @react-architect — Parallel: yes
- [ ] T048 [P] [US3] CSS for the launcher and live matrix — Owner: @frontend-css
- [ ] T049 [P] [US3] Vitest: reconnect-after-gap rebuilds correct progress — Owner: @frontend-tester
- [ ] T050 [US3] Playwright: navigate away and back mid-run; close and reopen the workspace and confirm the run is still listed with accurate state — Owner: @frontend-tester

---

## Phase 6: US4 — See what a generation run cost, stage by stage (P2)

**Status**: ⬜ Pending (0/6 — T051–T056)
**Goal**: Confirm or falsify the routing premise — cheap model routes, expensive model architects.
**Independent test**: Open a completed run's cost view and confirm every stage appears with its own spend, repair spend is separate, and the figures reconcile against the recorded total.

- [ ] T051 [US4] Implement the cost read in `codegen_service.py`: every stage present including explicit zeros, `priced: false` preserved, cache figures **absent** when unreported, repair spend separated from initial spend — Owner: @python-architect — Parallel: yes
- [ ] T052 [US4] Build `modules/codegen/components/StageCostTable.tsx` with the initial-vs-repair split and the largest-spending stage identifiable at a glance (SC-004) — Owner: @react-architect — Parallel: yes
- [ ] T053 [US4] Build the build-failure classification display separating an environment problem from a genuine code defect (FR-017, SC-005) — Owner: @react-architect — Parallel: yes
- [ ] T054 [P] [US4] CSS for the cost views — Owner: @frontend-css
- [ ] T055 [P] [US4] Vitest: a locally hosted stage renders as a real zero, an unpriced stage renders as unknown, and the two are visibly different — Owner: @frontend-tester
- [ ] T056 [US4] Verify computed totals reconcile against the run record's own figures within the subsystem's 5% tolerance — Owner: @python-tester

---

## Phase 7: US5 — Validate the benchmark definitions before spending on a run (P2)

**Status**: ⬜ Pending (0/5 — T057–T061)
**Goal**: Catch a malformed benchmark before an hour of running does.
**Independent test**: Introduce a deliberate error, validate from the module, and fix it on the first attempt from the reported location alone.

- [ ] T057 [US5] Implement the validation endpoint in `evals_service.py`, reporting each problem with its file and enough locating detail to fix it, and a summary count on success — Owner: @python-architect — Parallel: yes
- [ ] T058 [US5] Enforce the launch block while the tree fails validation, returning the failures as the reason (FR-031) — Owner: @python-architect — Parallel: yes
- [ ] T059 [US5] Build `modules/evals/components/ValidationPanel.tsx` — Owner: @react-architect — Parallel: yes
- [ ] T060 [P] [US5] CSS for the validation panel — Owner: @frontend-css
- [ ] T061 [P] [US5] Vitest: an invalid tree blocks launch and surfaces the reason — Owner: @frontend-tester

---

## Phase 8: US6 — Author a benchmark definition without leaving the workspace (P2)

**Status**: ⬜ Pending (0/10 — T062–T071)
**Goal**: Create and edit tasks, rubrics, and profiles in the workspace, writing ordinary version-controlled files.
**Independent test**: Author a task entirely in the workspace, then validate and run it with the CLI and the workspace closed, and confirm it is accepted unchanged.

- [ ] T062 [P] [US6] Contract test the round-trip in `tests/contract/test_definition_roundtrip.py` per `contracts/definition-roundtrip.md` — G1 the unmodified CLI accepts module-authored output **as a subprocess**; G2 a no-op save is byte-identical; G3 unmodelled fields survive an edit; G4 a non-representable definition opens read-only — Owner: @python-tester
- [ ] T063 [US6] Implement format-preserving read/write in `setup/src/cabal/webapi/evals_definitions_service.py`, preserving comments, key order, and unmodelled fields — Owner: @python-architect — Parallel: yes
- [ ] T064 [US6] Implement the `editable` flag, marking a definition read-only rather than normalising content the editor cannot represent faithfully — Owner: @python-architect — Parallel: yes
- [ ] T065 [US6] Implement the `evals.definition_save` action — validate before writing, digest bound to the current content hash so an external edit yields `409 definition_changed_externally`, atomic write — Owner: @python-architect — Parallel: yes
- [ ] T066 [US6] Implement the `evals.definition_delete` action, keeping stored runs readable by reading each against the manifest it recorded at launch (FR-054) — Owner: @python-architect — Parallel: yes
- [ ] T067 [US6] Implement uncommitted-status reporting for the definition tree (FR-055) — Owner: @python-architect — Parallel: yes
- [ ] T068 [US6] Build `modules/evals/components/DefinitionEditor.tsx` with save gated on validation and the specific problem shown on refusal — Owner: @react-architect — Parallel: yes
- [ ] T069 [US6] Build the read-only mode and the external-change warning — Owner: @react-architect — Parallel: yes
- [ ] T070 [P] [US6] CSS for the definition editor — Owner: @frontend-css
- [ ] T071 [P] [US6] Vitest: an invalid save is refused with the problem shown; an externally changed file warns instead of overwriting — Owner: @frontend-tester

---

## Phase 9: US7 — Confirm which model each pipeline stage is bound to (P3)

**Status**: ⬜ Pending (0/4 — T072–T075)
**Goal**: Verify the routing is configured as intended.
**Independent test**: Open the bindings view and confirm every stage lists its provider and model, with local bindings identifiable.

- [ ] T072 [US7] Implement the bindings endpoint — `is_local` read from the provider instance and **never inferred from its name**, plus a reachability flag (data-model B2) — Owner: @python-architect — Parallel: yes
- [ ] T073 [US7] Build `modules/codegen/components/StageBindings.tsx`, flagging any unreachable or misconfigured binding — Owner: @react-architect — Parallel: yes
- [ ] T074 [P] [US7] CSS for the bindings view — Owner: @frontend-css
- [ ] T075 [P] [US7] Vitest: an unreachable binding is flagged rather than shown healthy — Owner: @frontend-tester

---

## Phase 10: US8 — Come back to a run that was already in flight (P3)

**Status**: ⬜ Pending (0/7 — T076–T082)
**Goal**: Durable, browsable, resumable runs across restarts.
**Independent test**: Start a matrix, terminate the workspace mid-run, restart, confirm it is listed as interrupted and resumable, resume it, and confirm completed cells are not re-executed.

- [ ] T076 [US8] Implement the `evals.resume` action, determining completion from the manifest and cell directories rather than any job record (FR-036, SC-008) — Owner: @python-architect — Parallel: yes
- [ ] T077 [US8] Implement worktree listing and the `evals.worktree_cleanup` action, refusing to remove a worktree belonging to a live run (FR-044) — Owner: @python-architect — Parallel: yes
- [ ] T078 [US8] Implement codegen run-history browsing so any past run's plan, outcome, and cost open without knowing its identifier (FR-021) — Owner: @python-architect — Parallel: yes
- [ ] T079 [US8] Build the shared `RunHistory` presentation for both modules, newest first — Owner: @react-architect — Parallel: yes
- [ ] T080 [US8] Build the interrupted-and-resumable affordance, and mark a pending codegen plan as still-approvable or expired — never silently applied — Owner: @react-architect — Parallel: yes
- [ ] T081 [P] [US8] CSS for run history — Owner: @frontend-css
- [ ] T082 [P] [US8] Playwright: interrupt a matrix, resume it, and assert completed cell directories are not rewritten — Owner: @frontend-tester

---

## Phase 11: Polish & Cross-Cutting Concerns

**Status**: ⬜ Pending (0/9 — T083–T091)

- [ ] T083 [P] Harden both run listings against malformed or partially written artifacts — one unreadable run must not break the list; and against enormous run output, which must stay navigable without degrading the workspace (spec edge cases) — Owner: @python-architect
- [ ] T084 [P] Verify no run data was copied into SQLite: everything a user reads about a completed run comes from the artifact tree (data-model cross-cutting rule 1) — Owner: @python-tester
- [ ] T085 [P] Confirm the frontend computes no aggregate anywhere — no mean, spread, or win rate in TypeScript — Owner: @frontend-tester
- [ ] T086 Record the two findings from research.md against their features: `cabal.evals` has no `--json` mode → `specs/019-agent-eval-harness/`; `JobManager` never rehydrates from SQLite, stranding `running` jobs → `specs/015-web-ui-overhaul/` — Owner: main
- [ ] T087 Remove both subsystems from the "Shipped in this release, used outside the app" section of `apps/cabal-desktop/src/modules/release-notes/releaseNotes.ts` and give each its module entry (SC-012) — Owner: main
- [ ] T088 Update `apps/cabal-desktop/src/modules/registry.ts` to route both modules to their real components, and refresh module docs — Owner: main
- [ ] T089 Read-only audit of the implementation against this plan — Owner: @code-plan-verifier
- [ ] T090 [P] Verify FR-006 audit coverage across all nine action descriptors (`codegen.plan`/`approve`/`reject`/`new_service`, `evals.launch`/`cancel`/`resume`/`definition_save`/`definition_delete`) — each records what ran, against what, when, and its outcome — Owner: @python-tester
- [ ] T091 [P] Verify the plan's performance goals: a completed matrix comparison renders within 1s, per-cell progress appears within 2s of a cell finishing, and the module stays interactive while a run streams — Owner: @frontend-tester

---

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational — run_supervisor)  ⚠️ BLOCKING, sequential, single owner
    ↓
    ├─→ Phase 3 (US1, P1) ─────────┐
    ├─→ Phase 4 (US2, P1) ─────────┤   US1 and US2 are independent of each other
    │                               │
    │   ┌───────────────────────────┘
    │   ↓
    ├─→ Phase 5 (US3, P2)   needs Phase 4's run listing
    ├─→ Phase 6 (US4, P2)   needs Phase 3's run records
    ├─→ Phase 7 (US5, P2)   independent
    ├─→ Phase 8 (US6, P2)   needs Phase 7's validation
    ├─→ Phase 9 (US7, P3)   independent
    └─→ Phase 10 (US8, P3)  needs Phases 3 and 5
            ↓
        Phase 11 (Polish)
```

**Story independence**: US1 and US2 share nothing but Phase 2 and can be built fully in parallel. US5 and US7 are independent of everything after Phase 2. US6 depends on US5 only because saving reuses the validator.

---

## Parallel Execution (Constitution Gate 6)

Every `Parallel: yes` task is dispatched with `isolation: "worktree"`; the returned branch merges back to `021-codegen-eval-modules` before the next phase. **Hard cap: 4 concurrent subagents.**

**Batch A — Phases 3 + 4** (the plan's first parallel phase):

| Agent | Tasks |
|---|---|
| `@python-architect` | T017–T022, T031–T034 |
| `@react-architect` | T024–T026, T036–T038 |

`@ux-analyst` (T023, T035) is read-only and exempt from worktree isolation. `@frontend-css` and the testers run after their phase's components land.

**Batch B — Phases 5–8** (the plan's second parallel phase):

| Agent | Tasks |
|---|---|
| `@python-architect` | T042–T044, T051, T057–T058, T063–T067 |
| `@react-architect` | T045–T047, T052–T053, T059, T068–T069 |
| `@frontend-css` | T048, T054, T060, T070 |

Three concurrent writers, within the cap of 4.

**Batch C — Phases 9 + 10** (stage bindings ‖ history and resume):

| Agent | Tasks |
|---|---|
| `@python-architect` | T072, T076–T078 |
| `@react-architect` | T073, T079–T080 |

**Never parallelise**: Phase 2 (shared foundation), and T086–T088 (all touch cross-cutting files).

---

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3.** That yields a working .NET generator with a real approval gate — the safety property that justifies the module at all — and is demonstrable on its own.

**Best second increment: Phase 4 (US2).** It needs no process supervision and delivers the entire point of the eval harness against runs already on disk. If work has to stop after two increments, these two are the ones that leave something worth having.

**Then**: Phases 5–8 as Batch B, Phases 9–10 last.

### Checks worth running by hand at each increment

A passing unit test can coexist with each of these being broken (see quickstart.md):

- **After Phase 3**: `git status --porcelain` in the target project is byte-identical before and after reaching the gate.
- **After Phase 4**: workspace aggregates match `python -m cabal.evals report <run-id>` exactly.
- **After Phase 5**: close the workspace mid-run, reopen, and the run is still listed accurately. This is the test that fails loudest if Phase 2 was built as a job thread.
- **After Phase 6**: a local-model stage and an unpriced stage do not both render as `$0.00`.
- **After Phase 8**: `git diff` is empty after opening a hand-written definition and saving it unchanged.
