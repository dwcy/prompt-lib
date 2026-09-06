# Contract: Eval Harness Module API

**Surface**: `setup/src/cabal/webapi/routers/evals.py` + `actions_catalog/evals.py`  
**Contract tests**: `tests/contract/test_evals_api.py` — MUST be written and observed failing before implementation (Constitution Gate 3).

The eval CLI has **no `--json` mode** (research.md R5), so every read below is served by reading artifact files or calling the package's own functions directly. No endpoint parses CLI stdout.

---

## Read endpoints

### `GET /api/evals/availability`

`reason` ∈ `available` | `no_project_selected` | `subsystem_missing` | `no_benchmark_tree` | `definitions_invalid` | `definitions_read_only`.

**Contract**: `no_benchmark_tree` (a setup state, with a next step) and `definitions_invalid` (an error) are **distinct values** and must never be collapsed (spec edge case, data-model B3).

### `GET /api/evals/definitions`

The benchmark tree: tasks, rubrics, config profiles.

**Contract**:
- Each entry reports `editable` — false when the file contains content the editor cannot faithfully represent, in which case it opens read-only rather than being silently normalised (research.md R6).
- Each entry reports `uncommitted` (FR-055). The tree is version-controlled; an uncommitted task is not yet a reproducible benchmark.

### `GET /api/evals/definitions/validate`

Runs the subsystem's own validator.

**Contract**:
- Each problem carries the **file** and enough locating detail to fix it on the first attempt (FR-030, SC-006).
- On success, returns counts of what was found — how many tasks, how many profiles (US5 scenario 1).
- Cheap and side-effect-free: safe to call before every launch.

### `GET /api/evals/runs`

Run history from `evals/results/`, newest first.

**Contract**:
- Includes runs produced by the CLI outside the workspace — there is no "launched here" flag, because there is no separate code path (FR-045, research.md R1).
- Each run's state is **reconciled at read time** (data-model B1): process alive → `running`; process gone with complete artifacts → the artifacts' outcome; process gone with incomplete artifacts → `interrupted`.
- `interrupted` runs report `resumable` derived from the **manifest**, never from a job row (research.md R2).
- A partially written run directory yields a `"readable": false` entry rather than breaking the listing.

### `GET /api/evals/runs/{run_id}/report`

The comparison. Served from the subsystem's own reducer.

**Contract** — these are the rules the frontend must never re-derive (SC-010, data-model A8):

- Every aggregate carries the sample count `n` it was computed from (SC-009).
- `stddev` is **absent** for n < 3 — not zero, not null-rendered-as-zero (FR-041).
- Failed cells count against `task_pass_rate` and are excluded from quality means; both facts are represented in the payload, not just the net number (FR-040).
- `pairwise_win_rate` excludes ties and judge errors, and the payload reports **how many pairs were excluded and why**, so the rate cannot be read as covering more evidence than it does (FR-039).
- A verdict with `order_agreement: false` is reported as a **tie** (FR-038).
- When judge results are absent, the deterministic half of the report is still returned — a missing judge degrades the payload, it does not empty it (FR-043).

### `GET /api/evals/runs/{run_id}/cells/{task}/{profile}/{rep}`

One cell's check outcomes and agent metrics (FR-042).

**Contract**: a check that timed out is returned as a **result** with a timeout flag, never as an error — the subsystem guarantees a check outcome cannot abort its cell, and this surface preserves that (data-model A6).

### `GET /api/evals/worktrees`

Temporary worktrees on disk, including orphans from crashed runs (FR-044).

---

## Actions (prepare → execute)

### `evals.launch`

`destructive: false`. Params: `{ "baseline": string, "candidate": string, "tasks": string[], "runs": integer, "adapter"?: string }`.

**Contract**:
- Refused with `409 definitions_invalid` when the tree fails validation, returning the failures as the reason (FR-031).
- On execute, spawns a **detached** process and returns immediately with a job id and run id (research.md R1).
- The response reports the **isolated config directory** the run will use, so the module can show that the user's real agent configuration was never touched (FR-034, SC-011).

### `evals.cancel`

`destructive: true`. Params: `{ "run_id": string }`.

**Contract**: terminates the **process tree** (not just the parent), cleans up temporary worktrees, and leaves partial results readable (FR-035). Idempotent — cancelling a finished run is a no-op, not an error.

### `evals.resume`

`destructive: false`. Params: `{ "run_id": string }`.

**Contract**: already-completed cells are **not re-executed** (FR-036, SC-008). Completion is determined from the manifest and the cell directories on disk, never from a job record.

### `evals.definition_save`

`destructive: true`. Params: `{ "path": string, "content": <definition> }`.

**Contract**:
- Validated **before** writing; an invalid definition is refused with the specific problem and nothing is written (FR-052).
- `compute_digest` binds to the file's **current content hash**, so an external edit since the editor opened the file causes a `409 definition_changed_externally` rather than a silent overwrite (FR-053).
- Round-trip rules in [`definition-roundtrip.md`](./definition-roundtrip.md) apply.

### `evals.definition_delete`

`destructive: true`. Params: `{ "path": string }`.

**Contract**: stored runs referencing the deleted definition **remain readable**, because a run is read against the manifest it recorded at launch (FR-054, data-model cross-cutting rule 5). The effect preview names the affected runs so the user knows what they are decoupling.

### `evals.worktree_cleanup`

`destructive: true`. Params: `{ "path": string }`.

**Contract**: refuses to remove a worktree belonging to a **live** run.

---

## Concurrency

All run-starting actions take `exclusive_resource: "evals"` — separate from `"codegen"`, so the two modules run independently (research.md R7). The post-restart liveness check applies here too.
