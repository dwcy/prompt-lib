---

description: "Task list for 018-dotnet-codegen"
---

# Tasks: dotnet-codegen — fast, cheap C# backend generation

**Input**: Design documents from `/specs/018-dotnet-codegen/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Contract tests are **mandatory**, not optional — Constitution Principle III and Gate 3 bind two protocol surfaces (the headless CLI `--json` output consumed by the skill, and the edit-operation schema on which SC-003 is measured). Unit and integration tests are included where a success criterion cannot otherwise be measured.

**Scope**: Phase A only — US1 through US5 (greenfield). **US6 (brownfield) and the Roslyn semantic map are Phase B** and deliberately absent from this file (research R2, plan *Phase Gating*).

**Execution order was revised after Phase 2 closed.** Task IDs are stable — T001–T073 keep the numbers they were assigned and the numbers referenced in commits — but four phases moved. The four changes and why:

1. **One template, not three, on the critical path.** Only `vertical-slice` (T024, the declared default) is built in Phase 3. `minimal-service` (T023) and `clean-arch` (T025) move to Phase 9, after the design's central bet has been tested. Hand-authoring three solution templates is the highest-effort, lowest-information work in the feature; the registry's closed-set validation (T027/T028) behaves identically with one entry.
2. **The runaway guard precedes the unattended path.** T046–T048 (parse → classify → enforce) move from Phase 5 into Phase 3b, ahead of Phase 4. T035 wires the unattended tail (FR-010d); shipping that while every non-toolchain failure is provisionally classed `code_defect` means environment failures burn retry budget.
3. **The ledger precedes the bet it measures.** T061–T063 (RunRecord, per-stage capture, derived metrics) move from Phase 7 into Phase 4b. US2's map-caching bet is unfalsifiable without an instrument; SC-002/SC-005 need one before Phase 4 is judged.
4. **Two measurement gaps closed.** T074 captures the SC-002 unassisted baseline *before* any tool-shaped solution exists. T075 makes SC-006 measurable in Phase A by running the read-only `map` against a real large solution instead of deferring the number to Phase B.

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **Owner**: from `.specify/memory/agents.md`
- **Parallel: yes**: dispatched concurrently with other writers; `/speckit-implement` passes `isolation: "worktree"`

---

## Phase 1: Setup

**Status**: ✅ Complete (5/5 — T001–T005)

- [X] T001 Create pipeline package skeleton with module stubs per plan structure in `setup/src/cabal/dotnetgen/` (`__init__.py`, `pipeline.py`, `state.py`, `ledger.py`, and the `stages/`, `context/`, `edits/`, `verify/`, `providers/`, `templates/` subpackages) — Owner: @python-architect
- [X] T002 [P] Create test roots with shared fixtures in `setup/tests/dotnetgen/` (`contract/`, `integration/`, `unit/`, `conftest.py`) — Owner: @python-tester
- [X] T003 [P] Add `python -m cabal.dotnetgen` entry point and argparse skeleton mirroring the established pattern, in `setup/src/cabal/dotnetgen/__main__.py` and `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [X] T004 [P] Create the per-machine stage-binding file with documented defaults — provider and model **names only, never API keys** — in `global/dotnetgen-bindings.toml` — Owner: main
- [X] T005 [P] Add toolchain preflight asserting .NET 10 SDK and Python 3.14+, recording discovered versions, in `setup/src/cabal/dotnetgen/preflight.py` — Owner: @python-architect

---

## Phase 2: Foundational (blocking — no user story may start until complete)

**Status**: ✅ Complete (17/17 — T006–T022)

Contract tests come first per Principle III. T006–T008 must be written and **observed failing** before T009 onward.

- [X] T006 [P] Contract test for the edit-operation schema — symbol/search exclusivity, `delete` without `content`, `create-file` allowance, and the absence of any line-number field — in `setup/tests/dotnetgen/contract/test_edit_operation_schema.py` — Owner: @python-tester
- [X] T007 [P] Contract test for the run-record schema, including the `consumed <= ceiling` invariant and the four `outcome` values, in `setup/tests/dotnetgen/contract/test_run_record_schema.py` — Owner: @python-tester
- [X] T008 [P] Contract test for CLI global options, the exit-code map (0/2/3/4/5), and the rule that `--json` puts a single object on stdout with human output on stderr, in `setup/tests/dotnetgen/contract/test_cli_surface.py` — Owner: @python-tester
- [X] T009 EditOperation model with schema validation and the two non-schema rules (content must parse; a no-op rewrite is rejected) in `setup/src/cabal/dotnetgen/edits/model.py` — Owner: @python-architect
- [X] T010 [P] StageBinding model and bindings loader reading `global/dotnetgen-bindings.toml` with per-project override, in `setup/src/cabal/dotnetgen/providers/config.py` — Owner: @python-architect
- [X] T011 [P] Provider interface exposing a chat call plus usage reporting that **must include cached input tokens** (required by SC-005 and SC-010), in `setup/src/cabal/dotnetgen/providers/base.py` — Owner: @python-architect
- [X] T012 OpenAI-compatible adapter driven by `base_url`, covering Codex, Ollama and LM Studio in one implementation, in `setup/src/cabal/dotnetgen/providers/openai_compatible.py` — Owner: @python-architect
- [X] T013 CLI-shell adapter using subscription auth via the `claude`/`codex` CLIs, built on the persistent-subprocess pattern (reusing `setup/src/cabal/claude_cli.py` and the `/cli-llm-app` guidance) rather than one process per turn, in `setup/src/cabal/dotnetgen/providers/cli_shell.py` — Owner: @python-architect
- [X] T014 Usage extraction from the CLI-shell `stream-json` event stream, including cached input tokens — without this the subscription path cannot satisfy SC-005 or SC-010 — in `setup/src/cabal/dotnetgen/providers/cli_shell.py` — Owner: @python-architect
- [X] T015 Five-band stable-to-volatile context assembly with cache checkpoints after bands 2 and 3, in `setup/src/cabal/dotnetgen/context/bands.py` — Owner: @python-architect
- [X] T016 [P] ProjectState read/write with immutable `template_id` and explicit refusal on any change attempt (FR-001c), in `setup/src/cabal/dotnetgen/state.py` — Owner: @python-architect
- [X] T017 Pipeline skeleton — stage sequencing, the ChangeIntent approval gate, and RetryBudget with default ceiling 3 — in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [X] T018 [P] Minimal applier supporting only the `create-file` disposition (enough for US1; the ladder arrives in US2) in `setup/src/cabal/dotnetgen/edits/applier.py` — Owner: @python-architect — Parallel: yes
- [X] T019 [P] Minimal verification invocation running `dotnet build` then `dotnet test` and capturing exit codes and raw output, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — Owner: @python-architect — Parallel: yes
- [X] T020 Route stage classifying question versus change request (FR-010, SC-009) in `setup/src/cabal/dotnetgen/stages/route.py` — Owner: @python-architect
- [X] T021 [P] Unit tests for band ordering, checkpoint placement, and ProjectState immutability in `setup/tests/dotnetgen/unit/test_bands_and_state.py` — Owner: @python-tester
- [X] T022 [P] Unit tests for route classification across question/change/ambiguous phrasings in `setup/tests/dotnetgen/unit/test_route.py` — Owner: @python-tester

---

## Phase 2b: Cost baseline (blocking — must precede any generated solution)

**Status**: ⬜ Pending (0/1 — T074)

**Purpose**: SC-002 compares against "an unassisted Claude Code session performing the same task on the same solution, measured once and held as the reference" (spec.md *Assumptions*). That reference must be captured before the tool has shaped any solution, or it can only be reconstructed retroactively against code the tool already influenced.

- [ ] T074 Capture the SC-002 unassisted baseline: perform the Phase 3 greenfield scenario and one representative feature edit in an unassisted Claude Code session, recording total input/output tokens, wall-clock, and first-attempt build-green per task; commit the figures as `specs/018-dotnet-codegen/baseline.md` with the model, date, and exact prompts used — Owner: main

---

## Phase 3: US1 — Stand up a new backend service without bootstrapping (P1)

**Status**: ✅ Complete for Phase 3 (11/11 — T024, T026–T035). **T036 moved to Phase 4c** (see below).

**Goal**: one sentence plus one template choice plus one approval produces a compiling, test-passing, health-serving solution.

**Independent test**: on a machine with only the .NET SDK, run the greenfield path and measure wall-clock to first green build, wall-clock to a served health request, and total tokens (SC-001).

**Template scope**: `vertical-slice` only. T023 (`minimal-service`) and T025 (`clean-arch`) are Phase 9. The registry (T027) still validates against a closed set — a set of one — so T028's "unknown id is an error, never a fallback" contract is unchanged.

- [X] T024 [US1] Build the `vertical-slice` template (the default) — feature-folder slices, one handler per slice, EF Core — in `setup/src/cabal/dotnetgen/templates/vertical-slice/` — Owner: @dotnet-architect
- [X] T026 [US1] Add an xUnit test project and a health-endpoint smoke test to the `vertical-slice` template under `setup/src/cabal/dotnetgen/templates/vertical-slice/tests/` — Owner: @dotnet-tester
- [X] T027 [US1] ArchitectureTemplate registry with closed-set validation — an unknown id is an error, never a fallback — in `setup/src/cabal/dotnetgen/templates/registry.py` — Owner: @python-architect
- [X] T028 [US1] Contract test: `new --template <unknown>` exits 2, lists the closed set, and creates no files; a template-change attempt is refused naming the recorded template — in `setup/tests/dotnetgen/contract/test_new_command.py` — Owner: @python-tester
- [X] T029 [US1] `new` command scaffolding from the template so the solution **builds before any model writes to it** (FR-003), in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [X] T030 [US1] Architect stage emitting a prose ChangeIntent, with the enforced invariant that it contains no code fence or C# syntax (FR-010b, FR-012), in `setup/src/cabal/dotnetgen/stages/architect.py` — Owner: @python-architect
- [X] T031 [US1] Contract test: `plan` mutates nothing and reports zero write-stage cost, and a rejected plan costs under 10% of a completed run (SC-011) — in `setup/tests/dotnetgen/contract/test_plan_gate.py` — Owner: @python-tester
- [X] T032 [US1] `plan` command plus `intent_token` derivation bound to the solution fingerprint so approvals cannot be replayed, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [X] T033 [US1] Contract test: `apply` with a mismatched or stale `intent_token` is refused with no mutation, in `setup/tests/dotnetgen/contract/test_apply_token.py` — Owner: @python-tester
- [X] T034 [US1] Write stage converting an approved intent into EditOperations, one type per file per `global/rules/csharp.md`, in `setup/src/cabal/dotnetgen/stages/write.py` — Owner: @python-architect
- [X] T035 [US1] `apply` command wiring write into verify with the gate enforced and the unattended tail (FR-010d), in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
**T036 is not in this phase.** Discovered by running the pipeline live: adding any feature needs one line inserted into the existing `Program.cs` to register the new slice, and Phase 3's applier creates files but cannot edit them (T018 scope; in-place editing is T042). So a greenfield run gets as far as writing the new files and then stops. Rather than redesign the template to avoid in-place edits, or build a throwaway subset of T042, the integration test moves to **Phase 4c**, after T042 gives the applier the ability the test needs. Phase 3 therefore closes having delivered the scaffolder and the full plan/apply path, but without an end-to-end US1 demonstration.


---

## Phase 3b: US3 (partial) — The runaway guard, ahead of the unattended path

**Status**: ✅ Complete (3/3 — T046–T048)

**Purpose**: T035 ships the unattended tail. Until failures are classified, `verify/dotnet.py` provisionally treats every non-toolchain, non-timeout failure as `code_defect` — deliberately honest, but it means a restore failure or a rate limit consumes repair budget. These three tasks are the feature's one hard ordering constraint (parse → classify → enforce) and they are cheap; running them before Phase 4 is what makes every later phase safe to run unattended.

- [X] T046 [P] [US3] Diagnostic parser extracting `CS####`, `NU####`, `MSB####`, `NETSDK####` and xUnit assertion failures from build and test output, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — Owner: @python-architect — Parallel: yes
- [X] T047 [US3] Classification rule per research R4, including reclassification of `MSB####` raised against a file this run wrote as a code defect, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — replaces the provisional rule documented in that module's `verify()` docstring — Owner: @python-architect
- [X] T048 [US3] RetryBudget enforcement — consume only on `code_defect`; abort immediately at zero consumed on `environment_failure` — in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect

**Checkpoint**: the repair loop can no longer spend budget on failures the code did not cause. Phases 4 onward are safe unattended.

---

## Phase 4: US2 — Add a feature to an existing solution without re-reading it (P2)

**Status**: 🟡 In progress (9/10 — T037–T045 done; T075 needs a corpus solution)

**Goal**: locate targets from a compact structural map, edit only what changes, never re-emit untouched code.

**Independent test**: request a feature touching 2–4 types on a solution of known size; measure tokens, proportion of the codebase sent, and first-attempt edit application (SC-003).

**The green/brown seam.** This phase builds ranking, a hard token budget, and `omitted_summary` — machinery that only earns its keep at brownfield scale, while Phase A's declared scope is "solutions the tool generated (hundreds to low thousands of lines)" (plan.md *Scale/Scope*). US2's own acceptance scenario 1 ("a solution larger than fits in context") therefore cannot be exercised against a template-generated solution, and plan.md records SC-006 as unmeasurable in Phase A. T075 closes that gap without pulling US6 forward: `map` is read-only, so it can be pointed at a real large solution for measurement alone, with no edit path and no convention inference involved.

- [X] T037 [P] [US2] C# signature extractor producing types and member signatures with **no member bodies**, in `setup/src/cabal/dotnetgen/context/map_csharp.py` — Owner: @python-architect — Parallel: yes
- [X] T038 [P] [US2] Symbol anchoring resolving `namespace.Type.Member(signature)` to a source span, in `setup/src/cabal/dotnetgen/edits/anchor_csharp.py` — Owner: @python-architect — Parallel: yes
- [X] T039 [US2] Map ranking by (layer, visibility, recency) with hard token budget and a populated `omitted_summary` whenever the budget binds, in `setup/src/cabal/dotnetgen/context/map_csharp.py` — Owner: @python-architect
- [X] T040 [US2] Contract test: `map` over budget reports `omitted_count > 0` with non-null `omitted_summary` — silent truncation fails the test — in `setup/tests/dotnetgen/contract/test_map_command.py` — Owner: @python-tester
- [X] T041 [US2] `map` command plus content-addressed map cache keyed on a structural fingerprint, so an unchanged solution yields byte-identical output, in `setup/src/cabal/dotnetgen/context/map_csharp.py` and `cli.py` — Owner: @python-architect
- [ ] T075 [US2] Measure SC-006 in Phase A: run `map` read-only against a real .NET solution of at least 20,000 lines that this tool did not generate, and record map-bytes-to-source-bytes ratio, `omitted_count`, wall-clock, and whether `omitted_summary` is populated — in `specs/018-dotnet-codegen/baseline.md` alongside the T074 figures. **No edits, no `change` run, no convention inference** — this is a measurement of the map alone, not an early US6. If the ratio misses the 2% target, record it as a Phase B entry finding rather than tuning the heuristic to fit — Owner: main
- [X] T042 [US2] Relaxation ladder for text-anchored fallback edits — exact, then whitespace-insensitive, then leading-trim, then normalised-token — recording `relaxation_level`, in `setup/src/cabal/dotnetgen/edits/applier.py` — Owner: @python-architect
- [X] T043 [US2] Unit tests proving symbol anchors survive a `dotnet format` pass between write and re-anchor, and that the ladder recovers the documented drift cases, in `setup/tests/dotnetgen/unit/test_applier_drift.py` — Owner: @python-tester
- [X] T044 [US2] `change` command running the full route → architect → gate → write → verify sequence, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [X] T045 [US2] Integration test: a feature edit touching 2–4 types performs no full-solution read and re-emits no unchanged members, with edit-application rate at or above 90% (SC-003), in `setup/tests/dotnetgen/integration/test_feature_edit.py` — Owner: @python-tester

---

## Phase 4b: US5 (partial) — The instrument, before the bet is judged

**Status**: ✅ Complete (3/3 — T061–T063)

**Purpose**: US2 is the design's central bet — a cached structural map and symbol anchoring cost less than re-reading files. Without a ledger that number is an opinion. plan.md already records that SC-002, SC-005, SC-008 and SC-010 cannot be verified until US5 exists; pulling the capture half of US5 forward means Phase 4 can be judged when it lands rather than retroactively at T072. Reconciliation (T064) and the `report` command (T065) stay in Phase 7.

- [X] T061 [US5] RunRecord ledger reusing `cabal.session_pricing` for per-model cost lookup, in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect
- [X] T062 [US5] Per-stage token, cached-token, cost and wall-clock capture wired through every provider adapter, in `setup/src/cabal/dotnetgen/ledger.py` and `providers/base.py` — Owner: @python-architect
- [X] T063 [US5] Derived metrics — `cache_ratio`, `edit_success_rate`, `first_attempt_build_green`, and the repair-versus-initial cost split (FR-029) — in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect

**Checkpoint**: the US2 bet is now falsifiable. Compare against the T074 baseline before starting Phase 5 — **this is the suggested stop-and-use-it-for-real-work point.**

---

## Phase 4c: US1 — the deferred greenfield demonstration

**Status**: ⬜ Pending (0/1 — T036)

**Purpose**: the US1 end-to-end test that Phase 3 could not run. It needs T042's in-place editing (to register a slice in `Program.cs`) and T074's baseline (to compare cost against). Both exist by this point.

- [ ] T036 [US1] Integration test: empty directory plus description plus approval yields a solution that compiles, passes tests, and serves health — asserting no architecture question after the template choice (SC-001) — in `setup/tests/dotnetgen/integration/test_greenfield.py` — Owner: @python-tester

**Checkpoint**: US1 is demonstrated end to end for the first time.

---

## Phase 5: US3 (remainder) — Repair routing and reporting (P3)

**Status**: ✅ Complete (4/4 — T049–T052)

**Goal**: self-repair under a hard visible budget, with environment failures never consuming it. The budget mechanics landed in Phase 3b; this phase routes repairs correctly and reports them.

**Independent test**: inject a compile error and a test failure (both repaired), then an unfixable environment failure (aborts at zero consumed) — SC-007.

- [X] T049 [US3] Repair routing sending diagnostics to the write stage and never to the architect stage, so bands 1–3 of the cache are never invalidated by a repair (FR-020), in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [X] T050 [US3] Halt and abort reporting with per-attempt history and the working tree left inspectable (FR-023), in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [X] T051 [US3] Contract tests: ceiling reached exits 3 with `consumed == ceiling`; injected environment failure exits 4 with `consumed == 0` — in `setup/tests/dotnetgen/contract/test_retry_budget.py` — Owner: @python-tester
- [X] T052 [US3] Integration test: injected compile error is repaired within budget; an unfixable failure halts at the ceiling and reports every attempt (SC-007), in `setup/tests/dotnetgen/integration/test_repair_loop.py` — Owner: @python-tester

---

## Phase 6: US4 — Choose which model does which job, including local ones (P4)

**Status**: ✅ Complete (8/8 — T053–T060)

**Goal**: bind each stage to a provider and model independently; the mechanical write stage can run locally at zero marginal cost.

**Independent test**: run one identical feature under three binding configurations and compare cost, wall-clock, and first-attempt build-green (SC-008).

- [X] T053 [P] [US4] Anthropic adapter with cache-read/cache-write token reporting, in `setup/src/cabal/dotnetgen/providers/anthropic.py` — Owner: @python-architect — Parallel: yes
- [X] T054 [P] [US4] Google adapter with usage reporting normalised to the provider interface, in `setup/src/cabal/dotnetgen/providers/google.py` — Owner: @python-architect — Parallel: yes
- [X] T055 [US4] Per-stage binding resolution with configured fallback on provider failure or rate limiting (FR-027), in `setup/src/cabal/dotnetgen/providers/config.py` — Owner: @python-architect
- [X] T056 [US4] `providers --check` probing each bound provider for reachability without running a pipeline, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [X] T057 [US4] Local-endpoint support for Ollama and LM Studio through `base_url`, with cost accounted as zero (SC-008), in `setup/src/cabal/dotnetgen/providers/openai_compatible.py` — Owner: @python-architect
- [X] T058 [US4] Unit tests for binding resolution, fallback selection, and clear surfacing of an unreachable provider, in `setup/tests/dotnetgen/unit/test_provider_routing.py` — Owner: @python-tester
- [X] T059 [US4] Integration test binding stages across all three auth modes — subscription CLI-shell, API key, and local endpoint — asserting each resolves, reports usage, and falls back correctly, in `setup/tests/dotnetgen/integration/test_auth_modes.py` — Owner: @python-tester
- [X] T060 [US4] Integration test comparing one feature across all-hosted, cheap-hosted-writer, and local-writer configurations for cost and build-green (SC-008), in `setup/tests/dotnetgen/integration/test_stage_routing.py` — Owner: @python-tester

---

## Phase 7: US5 (remainder) — Reconciliation and the cost report (P5)

**Status**: ⬜ Pending (0/3 — T064–T066)

**Goal**: every run accounts for all four cost centres, with repair cost separately attributable. Capture landed in Phase 4b; this phase reconciles it against the provider and renders it.

**Independent test**: run one scaffold and one edit; confirm the report covers all four cost centres and reconciles with provider-reported usage (SC-010).

- [ ] T064 [US5] Reconciliation against provider-reported usage with an explicit `reconciled` flag rather than silent trust (SC-010), in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect
- [ ] T065 [US5] `report` command supporting `--run` and `--last`, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T066 [US5] Contract test asserting every `--json` output across all seven commands validates against its schema, in `setup/tests/dotnetgen/contract/test_json_outputs.py` — Owner: @python-tester

---

## Phase 7b: The remaining templates

**Status**: ⬜ Pending (0/2 — T023, T025)

**Purpose**: FR-001 requires a *closed set* of templates, "small enough that every member is maintained and tested". Phase 3 deliberately shipped a set of one so the pipeline could be proven first; this phase restores the set before Phase A claims its exit criteria. Both are mechanical work against a registry and a test harness that already exist — no design decisions remain.

**Must complete before T072** — measuring Phase A exit criteria against a one-template set would not be measuring FR-001.

- [ ] T023 [P] [US1] Build the `minimal-service` template — single project, minimal API, feature folders, EF Core, no mediator — plus its xUnit project and health smoke test, in `setup/src/cabal/dotnetgen/templates/minimal-service/` — Owner: @dotnet-architect — Parallel: yes
- [ ] T025 [P] [US1] Build the `clean-arch` template — Domain/Application/Infrastructure/Api layering with CQRS — plus its xUnit project and health smoke test, in `setup/src/cabal/dotnetgen/templates/clean-arch/` — Owner: @dotnet-architect — Parallel: yes

---

## Phase 8: Polish & Cross-Cutting Concerns

**Status**: ⬜ Pending (0/7 — T067–T073)

- [ ] T067 Author the thin driver skill that parses `--json`, presents the prose gate, and never reimplements pipeline logic, in `global/skills/dotnet-codegen/SKILL.md` — Owner: main
- [ ] T068 [P] `--dry-run` support across every command — plan only, no writes, no writing-model call — in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T069 [P] Contract test asserting `--dry-run` mutates nothing and invokes no writing model, in `setup/tests/dotnetgen/contract/test_dry_run.py` — Owner: @python-tester
- [ ] T070 Verify Gate 4 reversibility: the apply flow installs `global/skills/dotnet-codegen/` and `global/dotnetgen-bindings.toml`, and deleting both plus re-running `python setup/settings-configurator-ui.py` fully removes them — record the result in `specs/018-dotnet-codegen/plan.md` — Owner: main
- [ ] T071 Run `/review-conflicts` against the new skill and record the outcome for Gate 5 in `specs/018-dotnet-codegen/plan.md` — Owner: main
- [ ] T072 Measure every Phase A exit criterion using the verification table in `specs/018-dotnet-codegen/quickstart.md` and record actuals alongside targets — Owner: main
- [ ] T073 Read-only audit of the implementation against `specs/018-dotnet-codegen/plan.md` and all six Constitution gates — Owner: @code-plan-verifier

---

## Dependencies

```text
Phase 1 Setup ✅
  └─> Phase 2 Foundational ✅  (contract tests T006–T008 before T009+)
        ├─> Phase 2b  T074 cost baseline        ← must precede T036, runs alongside Phase 3
        └─> Phase 3   US1 (P1)  T024, T026–T035   ← scaffolder + plan/apply path
                    └─> Phase 3b  US3 partial  T046–T048  ← unattended becomes safe
                          └─> Phase 4   US2 (P2)  T037–T045, T075   needs T009, T015, T018
                                └─> Phase 4b  US5 partial  T061–T063  needs T011 usage reporting
                                      ├─> Phase 4c  T036 greenfield end-to-end (needs T042 + T074)
                                      │         ← STOP: compare to T074, use it for real work
                                      ├─> Phase 5   US3 remainder  T049–T052
                                      ├─> Phase 6   US4 (P4)  T053–T060   needs T010, T011, T012
                                      └─> Phase 7   US5 remainder  T064–T066
                                            └─> Phase 7b  T023, T025 remaining templates
                                                  └─> Phase 8 Polish  (T072 needs 7b)
```

**Story independence**: US2 through US5 each depend only on Phase 2, not on each other or on US1 — they can be built in any order once Foundational is complete. US1 is nonetheless the correct first build because it is the MVP and produces the solutions the other stories are exercised against. Phases 5, 6 and 7 remain mutually independent after Phase 4b and may be reordered on cost-benefit grounds.

**The one hard ordering constraint inside a story**: T046 (parse) → T047 (classify) → T048 (enforce). Enforcing a budget on an unclassified failure is the runaway loop this feature exists to prevent. This is why those three moved ahead of Phase 4 rather than staying with the rest of US3.

**Two ordering constraints created by the revision**:

- T074 (baseline) must precede **T036**, which now sits in Phase 4c. It does *not* block T024/T026: hand-authoring the template does not taint an unassisted-from-scratch reference, so the baseline session can be captured any time before Phase 4c.
- T042 (in-place editing) must precede **T036**. A greenfield run cannot register a new slice without inserting a line into `Program.cs`, so the US1 end-to-end test is unrunnable until the applier can edit an existing file.
- T023/T025 (Phase 7b) must precede T072 — measuring FR-001's "closed set" against a set of one measures nothing.

## Parallel execution examples

**Phase 2** — three contract tests, no shared files:

```text
T006, T007, T008   → @python-tester, sequential dispatch (one agent, no race)
T018, T019         → @python-architect ×2, Parallel: yes, separate worktrees
```

**Phase 3** — with one template, the widest batch is two, and the concurrency question mostly disappears:

```text
T024               → @dotnet-architect  (C# template)
T027               → @python-architect  (registry), concurrent with the above
```

**Phase 7b** — the deferred templates, once the registry and test harness are proven:

```text
T023, T025         → @dotnet-architect ×2, Parallel: yes, separate worktrees
```

Constitution cap is four concurrent subagents; no batch in the revised plan exceeds two, which also removes the four-way worktree merge the original Phase 3 required. Merge every returned worktree branch back into `018-dotnet-codegen` before the phase closes.

**Phase 6** — two independent adapters:

```text
T053, T054         → @python-architect ×2, Parallel: yes, separate worktrees
```

## Implementation strategy

**Demonstrable slice = Phase 2b + Phase 3 (T074, T024, T026–T035).** A described service becomes a scaffolded, building solution, and `plan`/`apply` run end to end under the gate. Note this is a *scaffolder* — `dotnet new` also scaffolds — and that the apply path can create files but not yet edit them, so a feature is not fully wired until T042. It is the platform the differentiated work is tested on, not the value proposition.

**Real checkpoint = end of Phase 4b.** The original plan called Phase 3 the MVP and separately advised stopping after Phase 4; those disagreed. The differentiated value starts at US2, and US2 is unjudgeable without the ledger, so the honest stopping point is after 4b: run real work through it, compare the ledger against the T074 baseline, and only then decide whether Phases 5–7 are worth building as specified.

**Then, in cost-benefit order:**

1. **US2 (Phase 4)** — where per-turn cost actually accumulates. A scaffold happens once; edits happen hundreds of times. T075 measures SC-006 here rather than deferring it to Phase B.
2. **US5 capture (Phase 4b)** — the instrument. Moved ahead of everything else it measures.
3. **US3 remainder (Phase 5)** — repair routing and reporting. The ceiling itself is already enforced from Phase 3b, so runs are safe unattended before this lands.
4. **US4 (Phase 6)** — bends the cost curve. Only meaningful once Phase 4b has made cost measurable.
5. **US5 remainder (Phase 7)** — reconciliation and the report. **SC-002, SC-005, SC-008 and SC-010 cannot be claimed until this lands**, even though capture exists from 4b.

**Why the central bet is tested early**: US2 is where symbol anchoring plus a cached structural map either holds or does not. The original ordering built that machinery in Phase 4, measured it in Phase 7, and declared SC-006 unmeasurable in Phase A altogether — three phases between building the bet and learning whether it paid. T075 and Phase 4b close that gap to zero.
