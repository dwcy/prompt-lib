# Quickstart: Codegen & Eval Workspace Modules

How to get oriented, run what exists today, and verify the feature as it lands.

---

## The one thing to understand first

**The backend does not own these runs.** Runs execute as detached OS processes; the on-disk artifact tree is the source of truth; the job record and SSE stream are a live *view*.

This is not a stylistic preference — see [research.md](./research.md) R1. `JobManager` keeps jobs in an in-memory dict on daemon threads and never rehydrates from SQLite, and the Tauri shell kills a backend it spawned on app exit. An eval matrix runs for hours. A job thread cannot.

Two consequences worth internalising before writing code:

- **Reading a workspace-launched run and a CLI-launched run is the same code path.** There is no "launched here" flag. If you find yourself adding one, something has gone wrong.
- **The frontend never computes an aggregate.** No means, no spreads, no win rates. The subsystem's reducer owns those rules, and SC-010 requires the workspace's numbers to match the CLI's exactly.

---

## Run the subsystems as they are today

Get familiar with what you are wrapping before wrapping it.

```bash
# .NET codegen — stage bindings and recent run history
python -m cabal.dotnetgen providers
python -m cabal.dotnetgen report --last 5

# The approval gate, in two steps. `plan` writes nothing and prints a token.
python -m cabal.dotnetgen plan --request "add a health endpoint"
python -m cabal.dotnetgen apply --intent-token <token>

# Eval harness — validate, then inspect an existing run
python -m cabal.evals validate
python -m cabal.evals report <run-id>
```

Note the asymmetry you will have to live with: `dotnetgen` supports `--json` with a strict channel contract (exactly one object on stdout, all human output on stderr); `cabal.evals` has **no** `--json` mode. That is why the eval module reads artifact files rather than CLI output (research.md R5). It is recorded as a finding against 019, not fixed here.

### Where the artifacts live

```
<project>/.dotnetgen/runs/<run-id>.json     # generation run record + per-stage cost
<project>/…pending intent file…             # the approval gate — a file, no TTL
evals/                                      # definitions: COMMITTED, this feature writes these
evals/results/<run-id>/                     # results: GITIGNORED, read-only to this feature
├── manifest.json                           # what resume reads to know which cells are done
└── <task>/<profile>/<rep>/metrics.json
```

---

## Run the workspace

```bash
./run tauri        # POSIX
.\run.cmd tauri    # Windows
```

Read `apps/cabal-desktop/src/modules/registry.ts` and one existing module (`modules/environment/` is a good shape match) before adding a new one.

---

## Build order

The run-supervision layer comes first, **sequentially**. Both modules depend on it; parallelising work over an unbuilt foundation produces merge conflicts, not speed.

| # | Slice | Story | Independently shippable? |
|---|---|---|---|
| 0 | `run_supervisor.py` — detached launch, liveness, artifact reconciliation | — | No; foundation |
| 1 | Codegen approval gate | US1 (P1) | **Yes** — a complete, useful generator on its own |
| 2 | Eval comparison view | US2 (P1) | **Yes** — works against CLI-produced runs with no launch capability at all |
| 3 | Eval matrix launch + live progress | US3 (P2) | Yes |
| 4 | Codegen per-stage cost | US4 (P2) | Yes |
| 5 | Definition validation | US5 (P2) | Yes |
| 6 | Definition authoring | US6 (P2) | Yes |
| 7 | Stage bindings | US7 (P3) | Yes |
| 8 | Run history + resume | US8 (P3) | Yes |

Slice 2 is the best second move: it needs no process supervision, and it delivers the payload of the entire eval harness against runs that already exist on disk.

---

## Contract tests first (Constitution Gate 3)

Four surfaces. Write these and watch them fail before implementing:

```bash
pytest tests/contract/test_codegen_api.py          # gate shape, digest, cost fidelity
pytest tests/contract/test_evals_api.py            # launch/cancel/resume, comparison payload
pytest tests/contract/test_run_events.py           # reconnect-after-gap correctness
pytest tests/contract/test_definition_roundtrip.py # byte-identical no-op save; CLI accepts our output
```

---

## Verifying the requirements that are easy to get wrong

These are the checks worth running by hand, because a passing unit test can coexist with each of them being broken.

**Nothing is written before approval** (FR-014, SC-003) — the load-bearing safety claim:

```bash
git -C <target-project> status --porcelain > /tmp/before
# ...run codegen.plan from the workspace, stop at the gate...
git -C <target-project> status --porcelain > /tmp/after
diff /tmp/before /tmp/after     # MUST be empty
```

**A stale plan is refused** (FR-015) — already implemented by the subsystem; you are surfacing it, not building it. Reach the gate, touch a source file in the project, then approve. Expect a refusal, not an apply.

**The gate outlives the app.** Reach the gate, fully quit the workspace, reopen. The pending intent is a file with no TTL, so it must still be there and still approvable.

**A run outlives the app** (FR-004/FR-005). Launch a small matrix, quit the workspace mid-run, reopen. The run must still be listed with an accurate state — this is the single test that fails loudest if slice 0 was built as a job thread.

**Resume skips completed cells** (FR-036, SC-008). Interrupt a matrix, resume, and confirm completed cell directories are not rewritten.

**Numbers match the CLI** (SC-010). Open a comparison in the workspace and run `python -m cabal.evals report <run-id>` for the same run. Every aggregate must agree. If they diverge, something is computing in the frontend that should not be.

**Unknown renders as unknown** (FR-008). Find a run with a locally hosted stage and one with an unpriced provider. A local model costs a real, known zero; an unknown price is not zero. If both render as `$0.00`, the distinction the ledger was written to preserve has been destroyed.

**Low-n aggregates claim no spread** (FR-041, SC-009). A metric with n < 3 must show no standard deviation — not a zero, not a blank cell implying zero.

**Ties are ties** (FR-038). A verdict with `order_agreement: false` must never render as a win.

**Eval isolation is visible** (FR-034, SC-011). The module must show the isolated config directory a run used. Independently confirm `~/.claude/` was untouched — that is the property that makes the harness safe to use at all.

---

## Definition authoring: the test that matters

The round-trip guarantee is easy to believe you have and easy not to have:

```bash
# 1. Author a task entirely through the workspace UI, then:
python -m cabal.evals validate    # must pass, with no hand-editing

# 2. Open a hand-written definition in the editor, save without changes:
git diff                          # must be EMPTY — byte-identical
```

A non-empty diff on step 2 means the editor is reformatting, which turns every future review of a benchmark change into noise. See [`contracts/definition-roundtrip.md`](./contracts/definition-roundtrip.md).

---

## When the feature is done

`SC-012`: both subsystems can be removed from the "Shipped in this release, used outside the app" section of `apps/cabal-desktop/src/modules/release-notes/releaseNotes.ts:336`. That copy is what prompted this feature; deleting it is the finish line.
