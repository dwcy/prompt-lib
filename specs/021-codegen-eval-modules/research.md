# Phase 0 Research: Codegen & Eval Workspace Modules

All findings below were verified against the code on disk, not inferred from the specs of 015, 018, or 019. Line references are to the state of `021-codegen-eval-modules` at the time of writing.

---

## R1 — Who owns a running job?

**Decision**: Runs execute as **detached OS processes**. The backend supervises them by reading their on-disk artifacts and checking process liveness — it does not own them on a thread. The `JobManager` job record and its SSE stream become a *live view* over a run, not the run itself.

**Rationale**: The obvious design — wrap each run in `JobManager.create(...)` like every other long operation in the workspace — cannot satisfy the spec, for three independently fatal reasons:

1. **Jobs are memory-only.** `JobManager.__init__` (`setup/src/cabal/webapi/jobs.py:122`) initialises `self._jobs = {}` and never reads from storage. Only *terminal* states are persisted (`finish` → `save_job`). A backend restart therefore loses every in-flight job, and worse, a job that was `running` when the process died stays permanently `running` in the SQLite `jobs` table — the UI would show a phantom run that can never complete.
2. **Work runs on daemon threads.** `create` spawns `threading.Thread(..., daemon=True)`. Daemon threads die with the interpreter, without cleanup.
3. **The shell kills the backend on exit.** `apps/cabal-desktop/src-tauri/src/main.rs:104` kills a backend this shell spawned on `RunEvent::Exit`. Closing the workspace therefore kills any in-process run.

An eval matrix is explicitly a multi-hour operation, and FR-004, FR-005, US3 scenario 4 and US8 scenario 2 all require a run to outlive the window. A job thread cannot do that at any level of effort.

The inversion is cheap because both subsystems already write durable, self-describing artifacts — `.dotnetgen/runs/<run-id>.json` against `contracts/run-record.schema.json`, and `evals/results/<run-id>/` with a manifest plus per-cell `metrics.json`. The truth about a run is already on disk; the backend only has to read it.

**Consequences**:
- FR-045 (browse runs the CLI produced) stops being a separate feature and becomes the *only* code path. A workspace-launched run and a CLI-launched run are indistinguishable to the reader, because both are just artifact trees.
- SC-010 (workspace figures match CLI figures) is structural rather than something to test for drift — both read the same files.
- Cancellation becomes process-tree termination plus worktree cleanup, not thread cooperation. `cabal.evals.proc.kill_process_tree` already exists for exactly this.

**Alternatives considered**:
- *`JobManager` thread per run.* Rejected — fails FR-004/FR-005/FR-036 as shown above.
- *Keep the backend alive after the app closes.* Rejected — changes the desktop shell's documented lifecycle contract (`contracts/desktop-shell.contract.md`), affects all 22 existing modules, and leaves an orphaned server the user never asked for.
- *A separate always-on daemon.* Rejected — a third process to install, supervise, and explain, to solve a problem the artifact tree already solves.

---

## R2 — Reconciling state after a restart

**Decision**: On backend startup, reconcile every non-terminal `jobs` row belonging to these two modules against reality: if its recorded process is gone and its artifact tree is incomplete, transition it to a new `interrupted` presentation state. Resumability is then derived from the run's own manifest, never from the job row.

**Rationale**: R1's phantom-`running` problem is not hypothetical — it is the current behaviour for any job alive at a hard shutdown. Since these are the first runs expected to *routinely* outlive the backend, they are the first to need reconciliation. Deriving resumability from the manifest rather than the job row is what makes FR-036 correct: `cabal.evals` already resumes by run id (`cli_run.py:106` loads the manifest when `--resume` is given) and already knows which cells are complete, so the module must not maintain a second, divergent opinion about progress.

**Consequences**: `interrupted` is a *presentation* state derived at read time. It is deliberately not a new value in the `jobs` table's state column, so nothing in the existing job state machine or its consumers changes.

**Alternatives considered**: *Trust the job row and mark stale rows failed.* Rejected — it destroys the resume affordance, which is the point of US8, and would report a run as failed when its artifacts show it three-quarters complete.

---

## R3 — The approval gate does not need the 5-minute ticket TTL

**Decision**: The durable gate is the codegen subsystem's **existing on-disk pending intent**. The webapi confirmation ticket wraps only the short `apply` call, not the human's reading time.

**Rationale**: `cabal/webapi/actions.py:19` sets `TICKET_TTL = timedelta(minutes=5)`. Reading an architecture plan carefully can easily exceed five minutes, and a gate that silently expires mid-review would be a bad feature.

It turns out no new mechanism is needed. `cabal/dotnetgen/intent.py` already implements the gate as a file-backed pending intent with **no TTL**, whose `token` is derived from both the proposed intent *and* `solution_fingerprint(project)` — a fingerprint of the solution tree that deliberately excludes build output and vendored trees. Its module docstring states the design goal outright: approval must not be replayable, and a refused token is an error rather than a prompt to re-approve.

This means:
- **FR-015 (stale plan refusal) is already implemented.** If the project changes after the plan is produced, the fingerprint changes, the derived token no longer matches, and `redeem` refuses. The module surfaces that refusal; it does not build it.
- **US8 scenario 4 (pending plan survives a restart) is already satisfied**, because the pending intent is a file.
- The precondition digest on the webapi ticket should be computed *from the intent token*, so the two mechanisms agree by construction instead of racing.

**Consequences**: The gate can be left open indefinitely, which is the correct behaviour for a human decision. The 5-minute TTL still applies to the execute call, which is the right scope for it.

**Alternatives considered**:
- *Raise `TICKET_TTL` globally.* Rejected — weakens the confirmation guarantee for all 22 existing modules to solve one module's problem.
- *A per-action TTL override.* Rejected as unnecessary once the durable gate was found to already exist; adding one would be a second source of truth about whether an approval is still valid.

---

## R4 — Streaming is for liveness; artifacts are the record

**Decision**: SSE carries progress and a tail of output for the user watching *now*. Nothing that must be readable later comes from the stream.

**Rationale**: `jobs.py` sets `DEFAULT_RING_BUFFER_SIZE = 200` and `OUTPUT_TAIL_LIMIT = 200`. An eval matrix produces far more than 200 lines, so the stream structurally cannot be the record. `sse.py` bounds each response at `JOB_STREAM_SEGMENT_MAX_S = 30.0` and relies on `Last-Event-ID` reconnection, which is correct for liveness across an hours-long run but means a client that was closed missed those frames entirely.

**Consequences**: The comparison view (US2) and cost view (US4) read artifacts, never stream history — which is also why they work identically for CLI-produced runs. Per-cell progress (FR-033) is emitted as structured events, not scraped from log text, so a reconnecting client can rebuild current state from the artifact tree plus the events since its last id.

**Alternatives considered**: *Enlarge the ring buffer for these job kinds.* Rejected — it makes the truncation point larger but not absent, and encourages treating the stream as a record that it can never reliably be.

---

## R5 — How the backend invokes the subsystems

**Decision**: **Import the Python packages directly** for read and validate operations; **spawn a detached process** for the long-running run operations. Do not parse human-readable CLI stdout in either case.

**Rationale**: Both subsystems are Python packages in the same tree as the backend, so reading a run record or validating definitions is a function call — no subprocess, no parsing, no version skew. For runs, R1 already requires a detached process, and the module invokes the same `python -m` entry point a user would.

A relevant gap surfaced here, recorded per FR-007 rather than worked around: **`cabal.evals` has no `--json` flag.** `cabal.dotnetgen` has one, with a strict channel contract (`exits.py`: `--json` puts exactly one object on stdout, every human-readable byte goes to stderr, because the `/dotnet-codegen` skill parses stdout). `cabal.evals.cli` has no equivalent. This is not a blocker — the eval module reads `manifest.json`, `metrics.json`, `comparison.json` and `report.json` directly, which is better than parsing stdout anyway — but it is a real asymmetry between the two CLIs and belongs in the findings log rather than being silently papered over.

**Consequences**: The backend depends on the two packages' *module APIs*, so a change to either's internals can break the module without breaking its CLI. Contract tests (Gate 3) cover the surfaces the module actually depends on, so such a break is caught by tests rather than by a user.

**Alternatives considered**:
- *Always shell out and parse stdout.* Rejected — `cabal.evals` offers no machine-readable output to parse, and doing so for `dotnetgen` would duplicate a schema that already exists as a file on disk.
- *Add `--json` to `cabal.evals` as part of this feature.* Rejected — FR-007 forbids changing the wrapped subsystems here. Recorded as a finding for 019 instead.

---

## R6 — Definition authoring must round-trip

**Decision**: The definition editor reads and writes the existing version-controlled files in place, preserving anything it does not itself model. Saving is gated on validation. A hand-written definition that the editor cannot fully represent opens read-only rather than being silently normalised.

**Rationale**: The user chose full GUI authoring (FR-050–FR-055). The failure mode of every naive config editor is the same: parse into a model, re-serialise, and quietly drop the comments, key order, and unmodelled fields the human put there. Because `evals/` is versioned benchmark-as-code, that damage shows up as noise in a diff and, worse, can change what a benchmark measures.

`DEFAULT_RESULTS_DIR = Path("evals/results")` (`definitions_model.py:25`) is gitignored (`.gitignore:97`) while the definitions themselves are committed — confirming the split the spec assumes: definitions are source, results are output.

**Consequences**: Round-trip fidelity is a contract surface with its own tests (Gate 3, `contracts/definition-roundtrip.md`). The test that matters: write a definition through the module, then validate the tree with the unmodified CLI and confirm it passes unchanged (SC-013). FR-055 (show uncommitted definitions) follows naturally, since the files are git-tracked.

**Alternatives considered**: *Model-and-rewrite without preservation.* Rejected — silently discards hand-written content, which FR-053's spirit and the edge case "a definition in a form the editor cannot represent" both forbid.

---

## R7 — One run at a time, and what happens on a second launch

**Decision**: Use the existing `exclusive_resource` mechanism, one resource name per module, and additionally check for a live detached process at launch — because the in-memory resource lock does not survive a restart.

**Rationale**: `JobManager.create` raises `JobConflict(holder)` when the named resource is held (`jobs.py:151`), which gives the spec's one-run-at-a-time assumption for free and produces a useful error naming the blocking job. But `self._resources` is in-memory, so after a restart the lock is gone while a detached run may still be executing. The liveness check from R1/R2 is what closes that hole.

**Consequences**: The two modules take separate resource names, so a codegen run and an eval matrix can proceed independently, matching the spec's assumption.

---

## R8 — Frontend conventions this must match

**Decision**: Follow the existing module shape exactly — a lazy-loaded module component registered in `modules/registry.ts`, a typed client under `src/api/`, `components/` and `hooks/` siblings, TanStack Query for server state, Zustand for view state, and CSS owned by `@frontend-css`.

**Rationale**: `registry.ts` is a static registry mapping nav grouping, title, delivery phase, and a lazily-imported page component, with `ModuleUnavailable.tsx` as the shared placeholder for modules not yet available. That placeholder is the right vehicle for FR-002 (report the subsystem as unavailable with a reason) — an existing pattern rather than a new one.

Stack as installed: React 19.2, TypeScript 7.0, Vite 8.1, TanStack Query 5.101, Zustand 5.0, Biome 2.5, Vitest 4.1. This matches `@react-architect`'s declared scope exactly, so no frontend agent-routing exception is needed.

---

## R9 — Contract surfaces requiring tests before implementation

Per Constitution Gate 3, these four surfaces get contract tests written and observed failing first:

| Surface | Why it is a contract | File |
|---|---|---|
| Codegen REST + actions | The gate's prepare/execute shape and precondition digest are a safety guarantee, not an implementation detail | `contracts/codegen-api.md` |
| Eval REST + actions | Launch/cancel/resume semantics and the comparison payload | `contracts/evals-api.md` |
| Run progress SSE events | Event grammar must let a reconnecting client rebuild state; the ring buffer guarantees frames are missed | `contracts/run-events.md` |
| Definition round-trip | A module-authored definition must be accepted unchanged by the unmodified CLI (SC-013) | `contracts/definition-roundtrip.md` |

---

## R10 — Greenfield destination safety

**Decision**: New-service creation resolves its destination *relative to the currently selected project's directory*, rejects any path that escapes it after normalisation, and refuses a destination that exists and is non-empty.

**Rationale**: The user scoped greenfield creation to inside the selected project (FR-011a), which removes the need for a filesystem picker and with it a whole class of "wrote a project tree somewhere surprising" failures. The escape check must happen after path normalisation, because a relative destination containing `..` would otherwise satisfy a naive prefix test. The non-empty refusal (FR-011b) is what stops a scaffold from merging into an existing tree — a silent, hard-to-undo outcome.

**Consequences**: The destination is a parameter of the prepare/execute ticket, so its resolved absolute path appears in the effect preview the user confirms — the user sees exactly where the tree will land before approving.

---

## Findings recorded against the wrapped subsystems

Per FR-007, gaps are recorded rather than worked around. Neither blocks this feature:

1. **`cabal.evals` has no `--json` output mode**, while `cabal.dotnetgen` has one with a strict stdout/stderr channel contract. Machine consumers of the eval CLI must read artifact files. → finding for `019-agent-eval-harness`.
2. **`JobManager` never rehydrates from SQLite**, so any job alive at a hard shutdown is stranded in `running` forever. This affects all 22 existing modules, not just these two; this feature works around it locally via R2's reconciliation rather than changing shared behaviour. → finding for `015-web-ui-overhaul`.
