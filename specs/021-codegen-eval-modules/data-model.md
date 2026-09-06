# Phase 1 Data Model: Codegen & Eval Workspace Modules

**Governing principle** (from [research.md](./research.md) R1): the durable state of a run is its **on-disk artifact tree**. Nothing in this model introduces a second store for run data. The SQLite rows this feature touches are live handles and audit records, not the record of what a run did.

Entities are grouped by where they actually live, because that is what determines their lifetime and who may write them.

---

## Group A — Owned by the subsystems (read-only to this feature)

These already exist on disk. The module reads them and must never write them.

### A1. GenerationRunRecord

**Location**: `<project>/.dotnetgen/runs/<run-id>.json`, conforming to the subsystem's `contracts/run-record.schema.json`.

| Field | Meaning | Notes for the UI |
|---|---|---|
| `run_id` | Identifier | Also the filename stem |
| `request` | The originating prose request | Shown verbatim in run history |
| `template` | Which locked architecture template | One of `clean-arch`, `minimal-service`, `vertical-slice` |
| `stages[]` | Per-stage cost records — see A2 | A stage that did not run appears with explicit zeros, never omitted (FR-018) |
| `outcome` | Terminal state | Maps to the exit taxonomy in A3 |
| `retry_budget` | Repair attempts made and permitted | Drives "halted at ceiling" presentation |

**Validation**: a malformed or partially written record must fail *for that run only* and must not break the history list (spec edge case). Read defensively: a run directory can be observed mid-write.

### A2. StageCost

One entry per pipeline stage within a run.

| Field | Meaning | Why the UI must not simplify it |
|---|---|---|
| `stage` | Pipeline stage name | |
| `provider`, `model` | What served this stage | The evidence for "cheap model routes, expensive model architects" |
| `usage` | Input/output tokens, and cache figures **only when the provider reported them** | `Usage.cache_reported` is false for providers that cannot say. Rendering a zero there would fabricate data (FR-008) |
| `priced` | Whether a price is known at all | **Not persisted today — see the constraint below.** In memory `false` means *unknown*, while a local model costs a real, known zero; conflating them is the specific error the subsystem's ledger was written to prevent |

> **Constraint on `priced` (finding #3, research.md).** `ledger.StageCost` holds `priced` in
> memory, but `to_dict()` never writes it and `run-record.schema.json` sets
> `additionalProperties: false`. A real run record therefore **cannot** distinguish a locally
> hosted model's genuine zero from an unlisted model's unknown price — both land on disk as
> `cost_usd: 0`. Changing that is 018's call, not this feature's (FR-007).
>
> So the module's obligation here is the *negative* one: report the distinction as **unknown**
> (`null`), never as `true`. Inferring "priced" from a bare zero would manufacture a
> measured-free claim the run never made. If the schema later gains the field, the read path
> passes it through unchanged rather than re-deriving it.
>
> The cache half of FR-008 is unaffected: `cached_input_tokens` is not in the schema's
> `required` list, so an unreported figure is genuinely absent rather than a fabricated zero.
| `reported_cost_usd` | Provider's own figure, when given | Reconciled against computed cost within a 5% tolerance |
| `wall_clock_seconds` | Stage duration | |
| *(repair association)* | Whether this spend was initial or repair | Must be presented separately (FR-019) — a pipeline that looks cheap per call but repairs three times is not cheap |

**Derived for display**: total, initial-vs-repair split, and largest-spending stage (SC-004). All derived at read time; none stored.

### A3. RunOutcome (enumeration)

**Authoritative source**: the `outcome` enum in `specs/018-dotnet-codegen/contracts/run-record.schema.json`. It has exactly **four** values. The UI must keep them distinguishable (FR-016, FR-017):

| Persisted outcome | Presentation requirement |
|---|---|
| `completed` | |
| `rejected_at_gate` | A user decision, not a failure. Costs under 10% of a completed run |
| `halted_at_ceiling` | Distinct from a generic failure — repair attempts were exhausted |
| `aborted_environment` | A broken toolchain, **not** a code defect. Consumes zero retry budget — this is what protects the repair budget |

**Do not confuse run outcomes with CLI exit codes.** `exits.py` defines six exit codes, but only four ever become a persisted `outcome`:

- `EXIT_OK` → `completed`; `EXIT_REJECTED_AT_GATE` → `rejected_at_gate`; `EXIT_HALTED_AT_CEILING` → `halted_at_ceiling`; `EXIT_ENVIRONMENT_FAILURE` → `aborted_environment`.
- `EXIT_FAILURE` and `EXIT_USAGE` are process-level results only. A run that exits with either **has no run record to read**, so the module reports it from the job's own failure state, not from an outcome field.

A code defect that the pipeline could not repair surfaces as `halted_at_ceiling`, not as a distinct "failure" outcome. The environment-vs-defect distinction FR-017 requires is therefore `aborted_environment` versus `halted_at_ceiling` — that is the whole of it.

### A4. PendingIntent

**Location**: the subsystem's pending-intent file within the target project.

| Field | Meaning |
|---|---|
| `intent_ref` | Derived from the intent **and** `solution_fingerprint(project)` |
| `fingerprint` | Fingerprint of the solution tree, excluding build output and vendored trees |
| `intent` | The proposed change — the file-by-file plan the user reviews |

**Lifecycle**: created by the architect stage, redeemed exactly once by apply, cleared only on *successful* apply — a failed write leaves the approval intact. **No TTL** (research.md R3). If the project changes, the derived token no longer matches and redemption is refused; this is FR-015, already implemented.

**State transitions**:

```
(none) ──propose──> pending ──redeem+apply ok──> (cleared)
                       │
                       ├──redeem, fingerprint moved──> refused (stays pending)
                       └──reject──────────────────────> (cleared, outcome: rejected at gate)
```

### A5. MatrixRunArtifacts

**Location**: `evals/results/<run-id>/` — gitignored; the definitions that produced it are committed.

```
evals/results/<run-id>/
├── manifest.json              # tasks, baseline/candidate profiles, runs, adapter
├── <task-id>/<profile>/<rep>/
│   ├── metrics.json           # check results + agent metrics for this cell
│   └── comparison.json        # judge verdicts (written by `judge`)
└── report.json / report.md    # reduction (written by `report`)
```

The manifest is what makes resume correct: it records the intended matrix, so completed cells are known by which cell directories exist (FR-036).

### A6. Cell

One task × profile × repetition, executed in a throwaway worktree pinned to a commit.

| Field | Meaning |
|---|---|
| `checks[]` | Deterministic outcomes — kind, passed/failed counts, timeout flag, exit code |
| agent metrics | `tool_calls`, `tokens_total`, `wall_seconds` |
| `unrequested_changes` | Scope violation count |

A check outcome — **including a timeout** — is recorded data, never an exception; the subsystem guarantees `run_checks` cannot abort its cell. The UI inherits this: a timed-out check is a result to display, not an error state.

### A7. ComparisonVerdict

Per baseline/candidate pair, judged twice with A/B swapped.

| Field | Meaning | Presentation requirement |
|---|---|---|
| `winner` | `A`, `B`, or `tie` | |
| `order_agreement` | Whether both presentation orders agreed | `false` ⇒ recorded as a tie. Must never render as a win (FR-038) |
| `judge_error` | Judge call or parse failed | Excluded from win rate, and the exclusion must be visible (FR-039) |

### A8. MatrixReport

Reduction of cells and verdicts into per-metric aggregates.

Metrics, in the subsystem's own order: `task_pass_rate`, `test_pass_rate`, `build_success_rate`, `unrequested_changes`, `tool_calls`, `tokens_total`, `wall_seconds`, `pairwise_win_rate`.

**Aggregation rules the UI must not restate differently** — these are the subsystem's, and re-deriving them in the frontend would breach SC-010:

- Failed runs count **against** `task_pass_rate` but are **excluded** from quality means (FR-040).
- Standard deviation only at n ≥ 3 (FR-041).
- All-null inputs yield a null mean, with `n` reflecting available samples — not zero, and not a hidden row.
- `pairwise_win_rate` excludes ties and judge errors (FR-039).

Every displayed aggregate carries its `n` (SC-009).

### A9. BenchmarkDefinitionTree

**Location**: `evals/` — committed. Tasks, rubrics, and config profiles.

This is the one Group A entity the module **writes** (FR-050–FR-055), under the round-trip constraint in `contracts/definition-roundtrip.md`: unmodelled content is preserved, saving is gated on validation, and the unmodified CLI must accept the result.

---

## Group B — New, owned by this feature

### B1. SupervisedRun

The backend's live handle on a detached process. **Ephemeral by design** — everything durable is in Group A.

| Field | Meaning |
|---|---|
| `job_id` | Existing `jobs` row, for the SSE stream and cancellation |
| `kind` | `codegen.run` or `evals.matrix` |
| `run_id` | Links to the artifact tree — the join between the ephemeral handle and the durable record |
| `pid` | Detached process id, for liveness and cancellation |
| `artifact_root` | Where to read progress and results |
| `exclusive_resource` | `codegen` or `evals` — one run per module (research.md R7) |

**Reconciled state** (derived at read time, never stored — research.md R2):

```
                 process alive? ──yes──> running
                       │
                       no
                       │
        artifacts complete? ──yes──> succeeded / failed  (per artifacts)
                       │
                       no ──────────> interrupted  (resumable if manifest allows)
```

`interrupted` is a presentation state only. It is deliberately **not** a new value in the `jobs` state column, so the existing job state machine and all its other consumers are untouched.

### B2. StageBinding

Current stage → provider/model mapping, read from configuration for the bindings view (US7).

| Field | Meaning |
|---|---|
| `stage` | Pipeline stage |
| `provider`, `model` | What is bound |
| `is_local` | Locally hosted — asked of the provider instance, **never inferred from its name** (a name-based guess reports a hosted run as free) |
| `reachable` | Health of the binding (FR-020) |

### B3. ModuleAvailability

Why a module cannot operate, feeding the existing `ModuleUnavailable` placeholder (FR-002).

| Reason | Trigger |
|---|---|
| `no_project_selected` | Neither module has a target |
| `not_a_dotnet_project` | Codegen only — reported before the user writes a request |
| `subsystem_missing` | CLI or its dependencies unavailable |
| `no_benchmark_tree` | Evals only — a **setup** state with a next step, explicitly distinct from a broken tree |
| `definitions_invalid` | Evals only — an error state, blocking launch (FR-031) |
| `definitions_read_only` | No write permission; authoring controls disabled up front, not at save time |

### B4. Action descriptors

Extending the existing `actions_catalog/` registry. Each carries a params schema, a `prepare` returning an `effect_preview`, an `execute`, and a `compute_digest`.

| Action id | Destructive | Precondition digest bound to |
|---|---|---|
| `codegen.plan` | no | project fingerprint |
| `codegen.approve` | **yes** | the pending intent's `intent_ref` — so the ticket and the subsystem's own gate agree by construction (research.md R3) |
| `codegen.reject` | no | pending intent token |
| `codegen.new_service` | **yes** | resolved destination path + emptiness |
| `evals.launch` | no | definition tree validity + selected profiles |
| `evals.cancel` | **yes** | run id + cancellable state |
| `evals.resume` | no | run id + manifest |
| `evals.definition_save` | **yes** | file path + current content hash (detects external edits, FR-053) |
| `evals.definition_delete` | **yes** | file path + content hash |

`effect_preview`'s existing `files_changed` field carries the codegen plan's intended file list directly — the approval gate needs no new preview shape.

### B5. AuditEntry

Existing `audit` table (FR-006). Every state-changing operation records what ran, against what, when, and its outcome. Gate decisions — approve **and** reject — are audited; a rejection is a decision worth keeping.

---

## Cross-cutting rules

1. **No run data is copied into SQLite.** Anything a user reads about a completed run is read from Group A. This is what makes a CLI-produced run and a workspace-produced run identical (FR-045) and guarantees SC-010 structurally.
2. **Unknown is a value.** `priced: false`, `cache_reported: false`, a null mean, and an absent judge verdict each render as their own thing. Substituting zero is a defect (FR-008).
3. **Aggregation lives in the backend**, reusing the subsystem's reducer. The frontend renders numbers; it never computes a mean, a spread, or a win rate.
4. **Definitions are source; results are output.** The module writes the first under round-trip constraints and never writes the second.
5. **Deleting a definition must not break a stored run** (FR-054). Runs are read against the manifest they recorded at launch, not against the current definition tree.
