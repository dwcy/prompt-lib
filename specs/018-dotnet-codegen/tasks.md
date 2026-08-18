---

description: "Task list for 018-dotnet-codegen"
---

# Tasks: dotnet-codegen — fast, cheap C# backend generation

**Input**: Design documents from `/specs/018-dotnet-codegen/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Contract tests are **mandatory**, not optional — Constitution Principle III and Gate 3 bind two protocol surfaces (the headless CLI `--json` output consumed by the skill, and the edit-operation schema on which SC-003 is measured). Unit and integration tests are included where a success criterion cannot otherwise be measured.

**Scope**: Phase A only — US1 through US5 (greenfield). **US6 (brownfield) and the Roslyn semantic map are Phase B** and deliberately absent from this file (research R2, plan *Phase Gating*).

## Format: `[ID] [P?] [Story] Description — Owner: @<agent> [— Parallel: yes]`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **Owner**: from `.specify/memory/agents.md`
- **Parallel: yes**: dispatched concurrently with other writers; `/speckit-implement` passes `isolation: "worktree"`

---

## Phase 1: Setup

**Status**: ⬜ Pending (0/5 — T001–T005)

- [ ] T001 Create pipeline package skeleton with module stubs per plan structure in `setup/src/cabal/dotnetgen/` (`__init__.py`, `pipeline.py`, `state.py`, `ledger.py`, and the `stages/`, `context/`, `edits/`, `verify/`, `providers/`, `templates/` subpackages) — Owner: @python-architect
- [ ] T002 [P] Create test roots with shared fixtures in `setup/tests/dotnetgen/` (`contract/`, `integration/`, `unit/`, `conftest.py`) — Owner: @python-tester
- [ ] T003 [P] Add `python -m cabal.dotnetgen` entry point and argparse skeleton mirroring the established pattern, in `setup/src/cabal/dotnetgen/__main__.py` and `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T004 [P] Create the per-machine stage-binding file with documented defaults — provider and model **names only, never API keys** — in `global/dotnetgen-bindings.toml` — Owner: main
- [ ] T005 [P] Add toolchain preflight asserting .NET 10 SDK and Python 3.14+, recording discovered versions, in `setup/src/cabal/dotnetgen/preflight.py` — Owner: @python-architect

---

## Phase 2: Foundational (blocking — no user story may start until complete)

**Status**: ⬜ Pending (0/17 — T006–T022)

Contract tests come first per Principle III. T006–T008 must be written and **observed failing** before T009 onward.

- [ ] T006 [P] Contract test for the edit-operation schema — symbol/search exclusivity, `delete` without `content`, `create-file` allowance, and the absence of any line-number field — in `setup/tests/dotnetgen/contract/test_edit_operation_schema.py` — Owner: @python-tester
- [ ] T007 [P] Contract test for the run-record schema, including the `consumed <= ceiling` invariant and the four `outcome` values, in `setup/tests/dotnetgen/contract/test_run_record_schema.py` — Owner: @python-tester
- [ ] T008 [P] Contract test for CLI global options, the exit-code map (0/2/3/4/5), and the rule that `--json` puts a single object on stdout with human output on stderr, in `setup/tests/dotnetgen/contract/test_cli_surface.py` — Owner: @python-tester
- [ ] T009 EditOperation model with schema validation and the two non-schema rules (content must parse; a no-op rewrite is rejected) in `setup/src/cabal/dotnetgen/edits/model.py` — Owner: @python-architect
- [ ] T010 [P] StageBinding model and bindings loader reading `global/dotnetgen-bindings.toml` with per-project override, in `setup/src/cabal/dotnetgen/providers/config.py` — Owner: @python-architect
- [ ] T011 [P] Provider interface exposing a chat call plus usage reporting that **must include cached input tokens** (required by SC-005 and SC-010), in `setup/src/cabal/dotnetgen/providers/base.py` — Owner: @python-architect
- [ ] T012 OpenAI-compatible adapter driven by `base_url`, covering Codex, Ollama and LM Studio in one implementation, in `setup/src/cabal/dotnetgen/providers/openai_compatible.py` — Owner: @python-architect
- [ ] T013 CLI-shell adapter using subscription auth via the `claude`/`codex` CLIs, built on the persistent-subprocess pattern (reusing `setup/src/cabal/claude_cli.py` and the `/cli-llm-app` guidance) rather than one process per turn, in `setup/src/cabal/dotnetgen/providers/cli_shell.py` — Owner: @python-architect
- [ ] T014 Usage extraction from the CLI-shell `stream-json` event stream, including cached input tokens — without this the subscription path cannot satisfy SC-005 or SC-010 — in `setup/src/cabal/dotnetgen/providers/cli_shell.py` — Owner: @python-architect
- [ ] T015 Five-band stable-to-volatile context assembly with cache checkpoints after bands 2 and 3, in `setup/src/cabal/dotnetgen/context/bands.py` — Owner: @python-architect
- [ ] T016 [P] ProjectState read/write with immutable `template_id` and explicit refusal on any change attempt (FR-001c), in `setup/src/cabal/dotnetgen/state.py` — Owner: @python-architect
- [ ] T017 Pipeline skeleton — stage sequencing, the ChangeIntent approval gate, and RetryBudget with default ceiling 3 — in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [ ] T018 [P] Minimal applier supporting only the `create-file` disposition (enough for US1; the ladder arrives in US2) in `setup/src/cabal/dotnetgen/edits/applier.py` — Owner: @python-architect — Parallel: yes
- [ ] T019 [P] Minimal verification invocation running `dotnet build` then `dotnet test` and capturing exit codes and raw output, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — Owner: @python-architect — Parallel: yes
- [ ] T020 Route stage classifying question versus change request (FR-010, SC-009) in `setup/src/cabal/dotnetgen/stages/route.py` — Owner: @python-architect
- [ ] T021 [P] Unit tests for band ordering, checkpoint placement, and ProjectState immutability in `setup/tests/dotnetgen/unit/test_bands_and_state.py` — Owner: @python-tester
- [ ] T022 [P] Unit tests for route classification across question/change/ambiguous phrasings in `setup/tests/dotnetgen/unit/test_route.py` — Owner: @python-tester

---

## Phase 3: US1 — Stand up a new backend service without bootstrapping (P1)

**Status**: ⬜ Pending (0/14 — T023–T036)

**Goal**: one sentence plus one template choice plus one approval produces a compiling, test-passing, health-serving solution.

**Independent test**: on a machine with only the .NET SDK, run the greenfield path and measure wall-clock to first green build, wall-clock to a served health request, and total tokens (SC-001).

- [ ] T023 [P] [US1] Build the `minimal-service` template — single project, minimal API, feature folders, EF Core, no mediator — in `setup/src/cabal/dotnetgen/templates/minimal-service/` — Owner: @dotnet-architect — Parallel: yes
- [ ] T024 [P] [US1] Build the `vertical-slice` template (the default) — feature-folder slices, one handler per slice, EF Core — in `setup/src/cabal/dotnetgen/templates/vertical-slice/` — Owner: @dotnet-architect — Parallel: yes
- [ ] T025 [P] [US1] Build the `clean-arch` template — Domain/Application/Infrastructure/Api layering with CQRS — in `setup/src/cabal/dotnetgen/templates/clean-arch/` — Owner: @dotnet-architect — Parallel: yes
- [ ] T026 [US1] Add xUnit test projects and a health-endpoint smoke test to all three templates under `setup/src/cabal/dotnetgen/templates/*/tests/` — Owner: @dotnet-tester
- [ ] T027 [US1] ArchitectureTemplate registry with closed-set validation — an unknown id is an error, never a fallback — in `setup/src/cabal/dotnetgen/templates/registry.py` — Owner: @python-architect
- [ ] T028 [US1] Contract test: `new --template <unknown>` exits 2, lists the closed set, and creates no files; a template-change attempt is refused naming the recorded template — in `setup/tests/dotnetgen/contract/test_new_command.py` — Owner: @python-tester
- [ ] T029 [US1] `new` command scaffolding from the template so the solution **builds before any model writes to it** (FR-003), in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T030 [US1] Architect stage emitting a prose ChangeIntent, with the enforced invariant that it contains no code fence or C# syntax (FR-010b, FR-012), in `setup/src/cabal/dotnetgen/stages/architect.py` — Owner: @python-architect
- [ ] T031 [US1] Contract test: `plan` mutates nothing and reports zero write-stage cost, and a rejected plan costs under 10% of a completed run (SC-011) — in `setup/tests/dotnetgen/contract/test_plan_gate.py` — Owner: @python-tester
- [ ] T032 [US1] `plan` command plus `intent_token` derivation bound to the solution fingerprint so approvals cannot be replayed, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T033 [US1] Contract test: `apply` with a mismatched or stale `intent_token` is refused with no mutation, in `setup/tests/dotnetgen/contract/test_apply_token.py` — Owner: @python-tester
- [ ] T034 [US1] Write stage converting an approved intent into EditOperations, one type per file per `global/rules/csharp.md`, in `setup/src/cabal/dotnetgen/stages/write.py` — Owner: @python-architect
- [ ] T035 [US1] `apply` command wiring write into verify with the gate enforced and the unattended tail (FR-010d), in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T036 [US1] Integration test: empty directory plus description plus approval yields a solution that compiles, passes tests, and serves health — asserting no architecture question after the template choice (SC-001) — in `setup/tests/dotnetgen/integration/test_greenfield.py` — Owner: @python-tester

---

## Phase 4: US2 — Add a feature to an existing solution without re-reading it (P2)

**Status**: ⬜ Pending (0/9 — T037–T045)

**Goal**: locate targets from a compact structural map, edit only what changes, never re-emit untouched code.

**Independent test**: request a feature touching 2–4 types on a solution of known size; measure tokens, proportion of the codebase sent, and first-attempt edit application (SC-003).

- [ ] T037 [P] [US2] C# signature extractor producing types and member signatures with **no member bodies**, in `setup/src/cabal/dotnetgen/context/map_csharp.py` — Owner: @python-architect — Parallel: yes
- [ ] T038 [P] [US2] Symbol anchoring resolving `namespace.Type.Member(signature)` to a source span, in `setup/src/cabal/dotnetgen/edits/anchor_csharp.py` — Owner: @python-architect — Parallel: yes
- [ ] T039 [US2] Map ranking by (layer, visibility, recency) with hard token budget and a populated `omitted_summary` whenever the budget binds, in `setup/src/cabal/dotnetgen/context/map_csharp.py` — Owner: @python-architect
- [ ] T040 [US2] Contract test: `map` over budget reports `omitted_count > 0` with non-null `omitted_summary` — silent truncation fails the test — in `setup/tests/dotnetgen/contract/test_map_command.py` — Owner: @python-tester
- [ ] T041 [US2] `map` command plus content-addressed map cache keyed on a structural fingerprint, so an unchanged solution yields byte-identical output, in `setup/src/cabal/dotnetgen/context/map_csharp.py` and `cli.py` — Owner: @python-architect
- [ ] T042 [US2] Relaxation ladder for text-anchored fallback edits — exact, then whitespace-insensitive, then leading-trim, then normalised-token — recording `relaxation_level`, in `setup/src/cabal/dotnetgen/edits/applier.py` — Owner: @python-architect
- [ ] T043 [US2] Unit tests proving symbol anchors survive a `dotnet format` pass between write and re-anchor, and that the ladder recovers the documented drift cases, in `setup/tests/dotnetgen/unit/test_applier_drift.py` — Owner: @python-tester
- [ ] T044 [US2] `change` command running the full route → architect → gate → write → verify sequence, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T045 [US2] Integration test: a feature edit touching 2–4 types performs no full-solution read and re-emits no unchanged members, with edit-application rate at or above 90% (SC-003), in `setup/tests/dotnetgen/integration/test_feature_edit.py` — Owner: @python-tester

---

## Phase 5: US3 — A repair loop that provably cannot run away (P3)

**Status**: ⬜ Pending (0/7 — T046–T052)

**Goal**: self-repair under a hard visible budget, with environment failures never consuming it.

**Independent test**: inject a compile error and a test failure (both repaired), then an unfixable environment failure (aborts at zero consumed) — SC-007.

- [ ] T046 [P] [US3] Diagnostic parser extracting `CS####`, `NU####`, `MSB####`, `NETSDK####` and xUnit assertion failures from build and test output, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — Owner: @python-architect — Parallel: yes
- [ ] T047 [US3] Classification rule per research R4, including reclassification of `MSB####` raised against a file this run wrote as a code defect, in `setup/src/cabal/dotnetgen/verify/dotnet.py` — Owner: @python-architect
- [ ] T048 [US3] RetryBudget enforcement — consume only on `code_defect`; abort immediately at zero consumed on `environment_failure` — in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [ ] T049 [US3] Repair routing sending diagnostics to the write stage and never to the architect stage, so bands 1–3 of the cache are never invalidated by a repair (FR-020), in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [ ] T050 [US3] Halt and abort reporting with per-attempt history and the working tree left inspectable (FR-023), in `setup/src/cabal/dotnetgen/pipeline.py` — Owner: @python-architect
- [ ] T051 [US3] Contract tests: ceiling reached exits 3 with `consumed == ceiling`; injected environment failure exits 4 with `consumed == 0` — in `setup/tests/dotnetgen/contract/test_retry_budget.py` — Owner: @python-tester
- [ ] T052 [US3] Integration test: injected compile error is repaired within budget; an unfixable failure halts at the ceiling and reports every attempt (SC-007), in `setup/tests/dotnetgen/integration/test_repair_loop.py` — Owner: @python-tester

---

## Phase 6: US4 — Choose which model does which job, including local ones (P4)

**Status**: ⬜ Pending (0/8 — T053–T060)

**Goal**: bind each stage to a provider and model independently; the mechanical write stage can run locally at zero marginal cost.

**Independent test**: run one identical feature under three binding configurations and compare cost, wall-clock, and first-attempt build-green (SC-008).

- [ ] T053 [P] [US4] Anthropic adapter with cache-read/cache-write token reporting, in `setup/src/cabal/dotnetgen/providers/anthropic.py` — Owner: @python-architect — Parallel: yes
- [ ] T054 [P] [US4] Google adapter with usage reporting normalised to the provider interface, in `setup/src/cabal/dotnetgen/providers/google.py` — Owner: @python-architect — Parallel: yes
- [ ] T055 [US4] Per-stage binding resolution with configured fallback on provider failure or rate limiting (FR-027), in `setup/src/cabal/dotnetgen/providers/config.py` — Owner: @python-architect
- [ ] T056 [US4] `providers --check` probing each bound provider for reachability without running a pipeline, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T057 [US4] Local-endpoint support for Ollama and LM Studio through `base_url`, with cost accounted as zero (SC-008), in `setup/src/cabal/dotnetgen/providers/openai_compatible.py` — Owner: @python-architect
- [ ] T058 [US4] Unit tests for binding resolution, fallback selection, and clear surfacing of an unreachable provider, in `setup/tests/dotnetgen/unit/test_provider_routing.py` — Owner: @python-tester
- [ ] T059 [US4] Integration test binding stages across all three auth modes — subscription CLI-shell, API key, and local endpoint — asserting each resolves, reports usage, and falls back correctly, in `setup/tests/dotnetgen/integration/test_auth_modes.py` — Owner: @python-tester
- [ ] T060 [US4] Integration test comparing one feature across all-hosted, cheap-hosted-writer, and local-writer configurations for cost and build-green (SC-008), in `setup/tests/dotnetgen/integration/test_stage_routing.py` — Owner: @python-tester

---

## Phase 7: US5 — See exactly what a run cost (P5)

**Status**: ⬜ Pending (0/6 — T061–T066)

**Goal**: every run accounts for all four cost centres, with repair cost separately attributable.

**Independent test**: run one scaffold and one edit; confirm the report covers all four cost centres and reconciles with provider-reported usage (SC-010).

- [ ] T061 [US5] RunRecord ledger reusing `cabal.session_pricing` for per-model cost lookup, in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect
- [ ] T062 [US5] Per-stage token, cached-token, cost and wall-clock capture wired through every provider adapter, in `setup/src/cabal/dotnetgen/ledger.py` and `providers/base.py` — Owner: @python-architect
- [ ] T063 [US5] Derived metrics — `cache_ratio`, `edit_success_rate`, `first_attempt_build_green`, and the repair-versus-initial cost split (FR-029) — in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect
- [ ] T064 [US5] Reconciliation against provider-reported usage with an explicit `reconciled` flag rather than silent trust (SC-010), in `setup/src/cabal/dotnetgen/ledger.py` — Owner: @python-architect
- [ ] T065 [US5] `report` command supporting `--run` and `--last`, in `setup/src/cabal/dotnetgen/cli.py` — Owner: @python-architect
- [ ] T066 [US5] Contract test asserting every `--json` output across all seven commands validates against its schema, in `setup/tests/dotnetgen/contract/test_json_outputs.py` — Owner: @python-tester

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
Phase 1 Setup
  └─> Phase 2 Foundational  (contract tests T006–T008 before T009+)
        ├─> Phase 3 US1 (P1)   ← MVP boundary
        ├─> Phase 4 US2 (P2)   needs T009, T015, T018
        ├─> Phase 5 US3 (P3)   needs T017, T019
        ├─> Phase 6 US4 (P4)   needs T010, T011, T012
        └─> Phase 7 US5 (P5)   needs T011 usage reporting
              └─> Phase 8 Polish
```

**Story independence**: US2 through US5 each depend only on Phase 2, not on each other or on US1 — they can be built in any order once Foundational is complete. US1 is nonetheless the correct first build because it is the MVP and produces the solutions the other stories are exercised against.

**The one hard ordering constraint inside a story**: T046 (parse) → T047 (classify) → T048 (enforce). Enforcing a budget on an unclassified failure is the runaway loop this feature exists to prevent.

## Parallel execution examples

**Phase 2** — three contract tests, no shared files:

```text
T006, T007, T008   → @python-tester, sequential dispatch (one agent, no race)
T018, T019         → @python-architect ×2, Parallel: yes, separate worktrees
```

**Phase 3** — the C# stream and the Python stream share nothing:

```text
T023, T024, T025   → @dotnet-architect ×3, Parallel: yes, separate worktrees
T027               → @python-architect, concurrent with the above
```

Constitution cap is four concurrent subagents; the widest batch here is four (three templates plus the registry). Merge every returned worktree branch back into `018-dotnet-codegen` before the phase closes.

**Phase 6** — two independent adapters:

```text
T053, T054         → @python-architect ×2, Parallel: yes, separate worktrees
```

## Implementation strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (T001–T036).** That delivers US1 standalone: a described service becomes a running, tested solution after one approval. It is demonstrable and valuable with US2–US5 entirely absent.

**Then, in cost-benefit order:**

1. **US2 (Phase 4)** — where per-turn cost actually accumulates. A scaffold happens once; edits happen hundreds of times.
2. **US3 (Phase 5)** — makes the tool safe to run unattended. Until the ceiling is enforced programmatically, treat every run as supervised.
3. **US4 (Phase 6)** — bends the cost curve. Only meaningful once US2 has made cost measurable.
4. **US5 (Phase 7)** — measures the other four. Sequenced last because it reports on them, but note that **SC-002, SC-005, SC-008 and SC-010 cannot be verified until it exists** — so US5 is required before any exit-criteria claim.

**Suggested checkpoint**: stop after Phase 4 and use the tool for real work before building Phases 5–7. US2 is where the design's central bet — symbol anchoring plus a cached structural map — either holds or does not, and finding out early is worth more than completeness.
