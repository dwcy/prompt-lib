# Success-criteria measurements (019)

Implementation is complete — 34 of 34 tasks, 164 tests green. **Validation is not.** This file
exists because the task ledger did not distinguish the two, so "all tasks checked" read as
"spec satisfied". It does not.

`plan.md` has no Phase Gating or exit-criteria section, so nothing held the unmeasured criteria
open. This file is that backstop: every criterion, its target, its actual, and the exact command
that produces the actual. A criterion with no actual is not met, however green the suite is.

## Status

| Criterion | Target | Actual | Evidence |
|---|---|---|---|
| SC-001 | A config change's effect is measurable end-to-end with no manual bookkeeping | **met** | T031 ran `validate` → matrix → `judge` → `report` live against the real `claude` CLI |
| SC-002 | Two consecutive runs over the same inputs produce structurally identical artifacts | **partially met** | `setup/tests/contract/test_evals_artifacts.py` asserts the schema and file layout of a single run. Two *real* consecutive runs have never been diffed — see the procedure below |
| SC-003 | 5-task × 2-config × 3-run matrix completes unattended, surviving an injected agent failure without losing the other cells | **not measured** | Never run. T031 executed 1 task × 2 configs × 1 run = 2 cells; SC-003 specifies 30. **Blocked** — see below |
| SC-004 | Report answers "which config won?" with a pairwise win rate plus ≥ 6 deterministic metric rows | **met** | `test_evals_report.py`, `test_evals_metrics.py` |
| SC-005 | Zero writes outside worktrees / results / per-run config dirs during a matrix run | **met** | Confirmed live in T031 (`git status` clean on the main tree, `~/.claude` untouched), plus unit coverage in `test_evals_matrix.py` |

Three of five met, one partial, one unmeasured — and the unmeasured one is the load-bearing claim.

## SC-003 is blocked on benchmark content, not on the harness

The harness supports it. The corpus does not: `evals/tasks/` contains exactly **one** task,
`001-sample-task`. T018 seeded three rubrics and *a* sample task, which is what a smoke test needs
and one fifth of what SC-003 names.

So SC-003 cannot be attempted until four more tasks exist. That is authoring work, not code — see
T035. Note also that `quickstart.md` line 84 references a task id, `003-refactor-repository`, that
was never authored; the smoke test as written would not run today.

Each task is a directory under `evals/tasks/<nnn>-<slug>/` holding `prompt.md` and a `task.toml`
of the shape already established by `001-sample-task`:

```toml
title = "..."
repo = "."
ref = "<commit sha the task starts from>"
expected_files = ["<path>", "..."]
rubrics = ["coding-quality", "instruction-following"]   # from evals/rubrics/

[[checks]]
kind = "test"
cmd = ["python", "-m", "pytest", "<path>", "-q"]
parser = "pytest"
timeout_seconds = 120
```

Pin `ref` to a real commit and choose `expected_files` that do not yet exist at that ref, so the
task is genuinely open when an agent starts it.

## Procedure for the outstanding measurements

Both need a live billed run against the real `claude` CLI, so they are recorded here as a
procedure rather than executed by the suite. Run from the repository root with
`PYTHONPATH=setup/src`.

### SC-003 — the unattended matrix (needs T035 first)

```bash
python -m cabal.evals validate
python -m cabal.evals run --baseline baseline --candidate candidate-example --runs 3
```

With five tasks authored and no `--tasks` filter, this is the full 5 × 2 × 3 = 30 cells. Then,
**while it is running**, injure one cell — kill a single adapter subprocess, or point one task's
`ref` at a nonexistent sha before starting — and confirm afterwards that:

- the run completes without operator input;
- the other 29 cells still produced results;
- the failed cell is recorded as a failure rather than silently absent;
- `python -m cabal.evals run --resume <run-id>` picks up only what is missing.

Record: wall clock, cells completed, cells failed, whether resume was needed, and what the
injected failure was.

### SC-002 — determinism across two real runs

```bash
python -m cabal.evals run --baseline baseline --candidate candidate-example --runs 1
python -m cabal.evals run --baseline baseline --candidate candidate-example --runs 1
diff -r <results-dir>/<run-id-1> <results-dir>/<run-id-2>
```

Model output will differ between runs and is expected to — SC-002 is about *structural* identity,
so compare the schema, the file layout and the set of keys, not the generated text. Record which
paths differ and confirm every difference is content rather than structure.

### SC-005 — re-confirm on the big run

T031 confirmed this on a 2-cell run. Re-check it on the 30-cell run, where parallelism and
per-run config directories are actually exercised:

```bash
git status --short          # main tree must be clean
git -C <each worktree> status --short
```

and confirm `~/.claude` is untouched.

## Honest limits

- **One adapter.** Everything above measures the `claude` CLI adapter. The null-capability path
  proves Codex and Gemini adapters *can* drop in (T029–T030), but neither has been run.
- **`candidate-example` is an example.** It exists to exercise the plumbing, not to represent a
  config change anyone cares about. A win rate measured against it says the harness works, not
  that a real config is better.
- **Judging is model-scored.** SC-004's ≥ 6 deterministic metric rows are reproducible; the
  pairwise win rate is not, and two judge passes over identical artifacts may disagree.
