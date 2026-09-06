# Phase 1 Data Model: dotnet-codegen

**Feature**: 018-dotnet-codegen | **Date**: 2026-08-14 | **Plan**: [plan.md](./plan.md)

All state is files on disk. Per-project state lives in `.dotnetgen/` inside the generated solution; run history lives under it. No database.

---

## ArchitectureTemplate

The locked project shape. Static data shipped with the tool, not user-authored.

| Field | Type | Rules |
|---|---|---|
| `id` | string | One of exactly `minimal-service`, `vertical-slice`, `clean-arch` (FR-001) |
| `display_name` | string | Shown at project creation |
| `project_layout` | list of ProjectSpec | The `.csproj` set and their reference edges |
| `layer_order` | list of string | Importance ranking for the structural map (research R3) |
| `scaffold_command` | string | The `dotnet new` invocation and post-steps that produce a running solution (FR-003) |
| `conventions_digest` | string | Content hash of the rule files this template pins, for cache-band-2 invalidation |

**Validation**: the set is closed — an unknown `id` is an error, never a fallback. `layer_order` must cover every project in `project_layout`.

## ProjectState

Written once at project creation, then read-only for the project's life.

| Field | Type | Rules |
|---|---|---|
| `template_id` | string | Recorded at creation; **immutable** (FR-001a) |
| `created_at` | timestamp | — |
| `solution_path` | path | — |
| `map_fingerprint` | string | Structural fingerprint; invalidates the cached map (research R5) |
| `recent_types` | list of string | Recency signal for map ranking, bounded length |

**State transitions**: `absent -> created`. There is no `template changed` transition — FR-001c requires refusal, not migration. A request to change it is an error naming the recorded template.

## StructuralMap

Signatures without bodies. Content-addressed so an unchanged solution yields byte-identical output (research R5).

| Field | Type | Rules |
|---|---|---|
| `fingerprint` | string | Must match `ProjectState.map_fingerprint` or the map is stale |
| `entries` | list of SymbolEntry | Ordered by (layer, visibility, recency) |
| `token_budget` | int | Hard cap (FR-006) |
| `omitted_count` | int | Entries dropped by the budget |
| `omitted_summary` | string | What was dropped — required by FR-006; never silently truncate |

### SymbolEntry

| Field | Type | Rules |
|---|---|---|
| `project` | string | Owning `.csproj` |
| `namespace` | string | — |
| `type_name` | string | — |
| `kind` | enum | `class` / `record` / `interface` / `struct` / `enum` |
| `members` | list of MemberSignature | Signature only — **never a body** |
| `visibility` | enum | `public` / `internal` / `protected` / `private` |

## ChangeIntent

Output of the architect stage. Prose, no code (FR-010b, FR-012).

| Field | Type | Rules |
|---|---|---|
| `summary` | string | One paragraph of what changes and why |
| `target_files` | list of path | Files to be touched — named so the gate is reviewable |
| `target_symbols` | list of string | Fully-qualified members to be touched |
| `rationale` | string | Why this approach |
| `must_not_contain_code` | invariant | Rejected if it contains a code fence or C# syntax — enforced, not advised |

**State transitions**: `proposed -> approved` | `proposed -> rejected` | `proposed -> amended`. Only `approved` may proceed to the writing stage (FR-010a). `rejected` and `amended` return to the architect stage having spent zero writing tokens (FR-010c, SC-011).

## EditOperation

The boundary between the writing stage and the applier — the contract SC-003 is measured on. Schema: [`contracts/edit-operation.schema.json`](./contracts/edit-operation.schema.json).

| Field | Type | Rules |
|---|---|---|
| `file` | path | Must exist unless `disposition` is `create-file` |
| `anchor_kind` | enum | `symbol` (preferred, research R1) or `text` (fallback only) |
| `symbol` | string | Fully-qualified `namespace.Type.Member(signature)`. Required when `anchor_kind` is `symbol` |
| `search` | string | Required when `anchor_kind` is `text`; matched via the relaxation ladder |
| `disposition` | enum | `replace` / `insert-into-type` / `delete` / `create-file` |
| `content` | string | Complete new member or file text. Absent for `delete` |
| `line_numbers` | forbidden | **No field exists.** Line numbers are structurally excluded (research 1.2, 1.3) |

**Validation**:

- Exactly one of `symbol` / `search` per operation, matching `anchor_kind`.
- `content` must be a complete, parseable member or file — never a fragment, never a `... unchanged ...` placeholder.
- An operation whose `content` reproduces the existing text unchanged is rejected as a no-op (guards against Cursor's observed "clean up unrelated code" behaviour and against wasted output tokens).

## EditApplication

Result of applying one `EditOperation`. Recorded whether it succeeds or fails, because failed application is a measured cost (FR-018).

| Field | Type | Rules |
|---|---|---|
| `operation` | EditOperation | — |
| `outcome` | enum | `applied` / `applied_after_relaxation` / `failed` |
| `relaxation_level` | int | 0 = exact; higher = looser rung of the ladder |
| `failure_reason` | string | Present when `failed` |

**SC-003 is computed from this entity**: first-attempt success rate counts `applied` at `relaxation_level` 0 and `applied_after_relaxation` together — both landed without costing a repair turn.

## VerificationResult

| Field | Type | Rules |
|---|---|---|
| `classification` | enum | `pass` / `code_defect` / `environment_failure` (FR-022) |
| `diagnostics` | list of Diagnostic | Parsed compiler and test output |
| `exit_code` | int | — |
| `command` | string | The `dotnet` invocation |

### Diagnostic

| Field | Type | Rules |
|---|---|---|
| `id` | string | e.g. `CS0246`, `NU1101`, `MSB3644` |
| `severity` | enum | `error` / `warning` / `info` |
| `file`, `line` | path, int | Line numbers are fine *here* — this is machine output being read, not model output being written |
| `message` | string | — |

**Classification rule** (research R4): `CS*` and test failures are `code_defect`; `NU*`, `NETSDK*` and `MSB*` are `environment_failure`, except `MSB*` raised against a file this run wrote, which is `code_defect`; non-zero exit with zero parsed diagnostics is `environment_failure`.

## RetryBudget

| Field | Type | Rules |
|---|---|---|
| `ceiling` | int | Configurable hard cap, **default 3** (FR-021) |
| `consumed` | int | Incremented **only** on `code_defect` |
| `environment_aborts` | int | Incremented on `environment_failure`; does **not** consume ceiling (FR-022) |

**Invariant**: `consumed <= ceiling`, always. Reaching the ceiling halts the run and reports (FR-021, FR-023, SC-007). An `environment_failure` aborts immediately without consuming.

## StageBinding

| Field | Type | Rules |
|---|---|---|
| `stage` | enum | `route` / `architect` / `write` |
| `provider` | string | Provider identifier |
| `model` | string | Model identifier |
| `fallback` | StageBinding, optional | Used on provider failure (FR-027) |

**Validation**: every stage must resolve to a binding. `verify` has no binding — it runs the .NET toolchain, not a model. That asymmetry is the point: **the verification signal costs nothing.**

## RunRecord

The cost ledger (FR-028). Schema: [`contracts/run-record.schema.json`](./contracts/run-record.schema.json).

| Field | Type | Rules |
|---|---|---|
| `run_id` | string | — |
| `outcome` | enum | `completed` / `halted_at_ceiling` / `aborted_environment` / `rejected_at_gate` |
| `stage_costs` | map of stage to StageCost | Tokens in/out, cached tokens, cost, wall-clock per stage |
| `initial_attempt_cost` | derived | Cost excluding repairs |
| `repair_cost` | derived | Cost of repair attempts only — **separately attributable** (FR-029) |
| `cache_ratio` | derived | Cached input tokens over total input tokens (SC-005) |
| `edit_success_rate` | derived | From `EditApplication` records (SC-003) |
| `retry_budget` | RetryBudget | — |
| `wall_clock_seconds` | float | SC-001 |

**Validation**: `stage_costs` must reconcile with provider-reported usage to within 5% (SC-010). A run whose ledger cannot be reconciled is reported as unreconciled rather than silently trusted.

---

## Entity relationships

```text
ArchitectureTemplate --(chosen once)--> ProjectState
ProjectState --(fingerprint)--> StructuralMap
StructuralMap --(band 3 context)--> ChangeIntent
ChangeIntent --(approved only)--> [EditOperation]
EditOperation --(applied by)--> EditApplication
[EditApplication] --(triggers)--> VerificationResult
VerificationResult --(code_defect)--> RetryBudget.consumed++ --> back to write stage
VerificationResult --(environment_failure)--> abort, budget untouched
StageBinding --(per stage)--> route | architect | write
everything --(accounted in)--> RunRecord
```

The one cycle in this model is `write -> apply -> verify -> write`, bounded by `RetryBudget.ceiling`. **It is the only cycle, and it is bounded** — which is the structural answer to the runaway-debug-loop failure mode in research 1.8.
