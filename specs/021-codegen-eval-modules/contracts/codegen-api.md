# Contract: Codegen Module API

**Surface**: `setup/src/cabal/webapi/routers/codegen.py` + `actions_catalog/codegen.py`  
**Contract tests**: `tests/contract/test_codegen_api.py` — MUST be written and observed failing before implementation (Constitution Gate 3).

All responses use the existing `cabal.webapi.envelope` shape. All mutations go through the existing prepare/execute ticket protocol — this surface introduces no second approval mechanism.

---

## Read endpoints

### `GET /api/codegen/availability`

Returns why the module can or cannot operate.

```json
{ "available": false, "reason": "not_a_dotnet_project", "detail": "No .csproj or .sln under the selected project" }
```

`reason` ∈ `available` | `no_project_selected` | `not_a_dotnet_project` | `subsystem_missing`.

**Contract**: never returns 500 for an unavailable subsystem. Unavailability is data (FR-002).

### `GET /api/codegen/runs`

Run history, newest first, read from `<project>/.dotnetgen/runs/`.

**Contract**:
- A malformed run record yields an entry with `"readable": false` and an error string — it MUST NOT fail the whole listing (spec edge case, data-model A1).
- Never paginates away the most recent run.

### `GET /api/codegen/runs/{run_id}`

One run: request, template, outcome, per-stage costs, retry budget.

**Contract**:
- Every pipeline stage appears, including stages that did not run, with explicit zeros (FR-018).
- `priced: false` is preserved and distinguishable from a real zero (FR-008, data-model A2).
- Cache figures are **absent** — not zero — when the provider did not report them.
- Repair spend is a separate field from initial spend (FR-019).
- `outcome` is one of the six values in data-model A3; the environment-failure and retry-ceiling cases are never collapsed into a generic failure (FR-016, FR-017).

### `GET /api/codegen/pending`

The pending intent awaiting a decision, or `null`.

```json
{
  "token": "…",
  "request": "Add a webhook receiver endpoint",
  "stale": false,
  "intent": { "files": [ { "path": "src/Api/Webhooks/ReceiverEndpoint.cs", "operation": "create" } ] }
}
```

**Contract**:
- `stale: true` when the current solution fingerprint no longer matches the one the token was derived from. Computed, never cached.
- Has **no expiry** (research.md R3). A pending intent survives backend restarts because it is a file.

### `GET /api/codegen/bindings`

Stage → provider/model bindings.

**Contract**: `is_local` is read from the provider instance, **never inferred from the provider's name** — a name-based guess reports a hosted run as free (data-model B2).

---

## Actions (prepare → execute)

### `codegen.plan` — run classify + architect, stop at the gate

`destructive: false`. Params: `{ "request": string, "template"?: string }`.

**Contract**:
- On execute, spawns a **detached** process (research.md R1) and returns a job id plus run id immediately. It MUST NOT block.
- **Writes nothing to the target project.** The contract test asserts the working tree is byte-identical before and after a `codegen.plan` run that reaches the gate (FR-014, SC-003).

### `codegen.approve` — redeem the intent and apply

`destructive: true`. Params: `{ "token": string }`.

**Contract**:
- `compute_digest` binds to the **pending intent token** so the webapi ticket and the subsystem's own gate cannot disagree (data-model B4).
- Execute is refused with `409 intent_stale` when the fingerprint moved. The refusal is an error, never an automatic re-prompt to approve.
- A token already redeemed is refused — approval is not replayable.
- `prepare`'s `effect_preview` populates `files_changed` from the intent's file list, so the confirmation the user sees is the plan itself.
- A **failed apply leaves the pending intent intact**, so the user can retry without re-approving.

### `codegen.reject` — discard the pending intent

`destructive: false`. Params: `{ "token": string }`.

**Contract**: clears the pending intent, records outcome `rejected at gate`, leaves the working tree unmodified, and **writes an audit entry** — a rejection is a decision worth keeping (FR-006, data-model B5).

### `codegen.new_service` — scaffold from a locked template

`destructive: true`. Params: `{ "template": string, "destination": string, "description": string }`.

**Contract**:
- `destination` resolves **relative to the selected project's directory**. After normalisation, any path escaping that directory is refused with `400 destination_outside_project` — the check happens post-normalisation, because a relative path containing `..` passes a naive prefix test (research.md R10, FR-011a).
- An existing, non-empty destination is refused with `409 destination_not_empty` (FR-011b). It is never merged into.
- The effect preview shows the **resolved absolute path**, so the user confirms where the tree actually lands.

---

## Concurrency

All run-starting actions take `exclusive_resource: "codegen"`.

**Contract**:
- A second launch while one is running is refused with `409` naming the blocking job (existing `JobConflict`).
- The refusal also holds after a backend restart, when the in-memory resource lock is gone: the launch path performs the liveness check from research.md R7 before creating the job.

---

## What this contract does not cover

Cost *ceilings*. Budget and retry limits remain configuration owned by the generation subsystem; this surface reports what was spent and whether a ceiling was hit, and never becomes a second place to set one (spec Assumptions).
