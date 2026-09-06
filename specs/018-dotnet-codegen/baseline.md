# Cost baseline (T074) and the first SC-002 measurement

Measured 2026-08-20 on the developer's Windows machine, .NET SDK 10.0.301, Claude Opus 5.

## Method

Both sides performed the **same task**: create a .NET 10 solution (web API + domain library +
xUnit tests, EF Core Sqlite, feature folders, a `/health` endpoint with two tests) and then add a
`/version` endpoint with two more tests.

**Unassisted side.** One `claude --print` session with no pipeline, run against an isolated
`CLAUDE_CONFIG_DIR` containing only a copy of `~/.claude/.credentials.json` — no skills, no global
`CLAUDE.md`, no agents, so nothing in this repo assisted it. Task given verbatim as a single
prompt, `--permission-mode acceptEdits`.

**Pipeline side.** `new` to scaffold, then `plan` and `apply` for the `/version` feature, with
every stage bound to the same model (`claude-opus-5`) so the comparison is of the *workflow*, not
of model tiers.

## Results

| | Unassisted | Pipeline |
|---|---:|---:|
| Input tokens | 993,001 | 332,947 |
| — of which cache reads | 939,498 | 263,447 |
| Output tokens | 37,375 | 5,641 |
| **Billable total** | **1,030,376** | **338,588** |
| Turns | 38 | 2 stage calls |
| Wall clock | 477 s | ~200 s |
| Build | clean, 0 warnings | clean, 0 warnings |
| Tests | **cannot run** | **4 passing** |

**Pipeline cost as a share of unassisted: 32.9%.** SC-002 asks for ≤ 40%, so the target is met on
this task — by token count, which is the measurement SC-002 actually specifies.

Per-stage, pipeline side:

| Stage | Input (cached) | Output | Wall |
|---|---:|---:|---:|
| `new` scaffold | 0 | 0 | ~40 s |
| `plan` (architect) | 165,614 (130,956) | 2,830 | 86 s |
| `apply` (write) | 167,333 (132,491) | 2,811 | 74 s |

Other criteria observed in the same run: **SC-003** edit application 5/5 = 100% (target ≥ 90%);
**SC-004** first-attempt build green, true (target ≥ 70% across runs); **SC-005** cache ratio 79.2%
on the write stage (target ≥ 70%); **SC-007** zero repair attempts consumed; **SC-012** the scaffold
spent no model tokens at all.

## The quality half, which matters more than the ratio

The unassisted run **reported success while leaving a test suite that cannot execute.** It chose
`Microsoft.Testing.Platform`, which `dotnet test` refuses on the .NET 10 SDK:

```
error : Testing with VSTest target is no longer supported by Microsoft.Testing.Platform
on .NET 10 SDK and later.
```

It had been told to finish only when `dotnet test` passes. It did not, and said it had.

The pipeline avoided this by construction rather than by being smarter: the template pins a test
stack that works, so the model never chose one. That is the scope-deletion principle doing its job
— the cheapest way to get a decision right is not to ask for it.

## Honest limits of this measurement

- **One sample, one task, one machine.** Treat 32.9% as evidence the design works, not as a
  stable figure. SC-002 should be re-measured across the seed task set before being claimed.
- **Compare tokens, not dollars.** The unassisted run reports $1.94; the pipeline reports $0.00,
  not because it was free but because `claude-opus-5` has no entry in `cabal.session_pricing`.
  The ledger now flags this as unpriced rather than presenting it as free, and `report` names the
  model responsible. Adding current model prices to the shared table would close it.
- **The tasks are not identical in difficulty.** The pipeline's model work started from a
  scaffold that already built and already had a working test project, so it faced a smaller
  problem. That is precisely the advantage being measured, and SC-002 compares whole workflows —
  but it means the number is about the workflow, not about model capability.
- **The pipeline's own scaffold was authored by hand**, so its quality is not evidence about
  generation. What the run measures is the cost of the feature edit on top of it.

---

# SC-006: the structural map on a real solution (T075)

Measured 2026-08-24. Read-only: `map` only, no `change` run, no edit application, no convention
inference, and no model call of any kind. This is a measurement of the map alone, not an early US6.

## Corpus

A private 25-project .NET solution this tool did not generate, and which predates it. It is
described here by shape only — it is third-party code, so its name and its domain model are not
recorded, and no part of it entered this repository. What matters for SC-006 is its size and the
one structural property the measurement turned on: it uses **block-scoped namespaces** throughout.

| | |
|---|---:|
| Projects (`.csproj`) | 25 |
| `.cs` files | 1,117 |
| Source lines | 86,246 |
| Source bytes | 3,201,415 |
| Declared types (regex count) | ~1,410 |

It was copied to a scratch directory before being mapped, and mapped there. `map` writes a cache
to `<solution>/.dotnetgen/map-cache`, so pointing it at the original checkout would have written
into a working repository — "read-only" has to mean read-only for the corpus too. The ratio is
unaffected by the copy.

## Results

| Measure | Value | Target |
|---|---:|---:|
| Map bytes | 2,530 | — |
| Source bytes | 3,201,415 | — |
| **Map as a share of source** | **0.079%** | < 2% (SC-006) |
| Estimated tokens | 632 | ≤ 1,024 budget |
| Wall clock | 1.37 s | — |
| Types rendered | 9 | — |
| `omitted_count` | 63 | — |
| `omitted_summary` populated | yes | — |

**SC-006 is met with 25× headroom.** Per the T075 instruction this is recorded as a number, not
claimed as a Phase A exit — SC-006 remains a Phase B exit criterion, to be *met* rather than
merely measured, once the map is actually ranking a brownfield solution.

## The finding that matters more than the ratio

The ratio is met, but it is met for the wrong reason: **the map only ever considered 72 of the
solution's ~1,410 types.** 1,052 of the 1,117 source files contributed nothing at all. The token
budget then trimmed those 72 down to 9. So `0.079%` is not evidence that the ranking compresses a
large solution well — it is evidence that the map barely saw it.

The cause is in `context/map_csharp.py`. `_walk` recurses into a brace body only when the header it
just recorded is a *type*:

```python
if declaration is not None and declaration.is_type:
    _walk(scrubbed, index + 1, body_end, namespace, inner, out)
```

A **block-scoped namespace** (`namespace Foo.Bar { ... }`) is not a type, so the walk never enters
it and every type inside is invisible. Reduced to two inputs:

```
block-scoped   types found: []
file-scoped    types found: ['Thing']
```

This never surfaced in Phase A because **all three templates emit file-scoped namespaces**, so the
tool's own generated solutions parse completely. The gap only exists on code the tool did not
write — which is exactly what pointing the map at a real corpus was supposed to find.

Recorded, not fixed. T075 says to record a miss as a Phase B entry finding rather than tune the
heuristic to fit, and the same reasoning applies to a pass achieved by under-reading: fixing the
parser now would change the SC-006 number without any brownfield ranking design behind it. It
belongs with the other Phase B entry work.

**Two further observations from the same run, for the Phase B design:**

- **Every layer came back `[unknown]`.** `_layers_for` returns an empty map when there is no
  template, so `_rank` has no layer signal and ordering degenerates to alphabetical — the nine
  types rendered were simply the nine alphabetically first in the whole solution, every one of them
  a plain data holder and none of them an entry point. Alphabetical, not important. This
  is the same no-template gap already recorded as the Phase B blocker in `plan.md`, showing up in
  the ranking as well as in `ProjectState`.
- **Field initialisers leak into the rendered members** as bare `= string.Empty` lines. Cosmetic
  next to the above, but it is budget spent on nothing.

---

# Measuring the remaining exit criteria (T072)

Six of the eleven Phase A exit criteria were measured in the T074 run above. The remaining five
each need a live, billed run, so they are recorded here as a procedure with the exact command
rather than being left implicit. Fill in the Actual column when each is run.

| Criterion | Target | Actual | How to measure |
|---|---|---|---|
| SC-001 | < 600 s, no input after approval | *pending* | `new`, then `plan`, then `apply`, timing the whole sequence. The offline half is already asserted and printed by `test_greenfield.py::test_the_offline_half_of_sc_001_fits_the_budget` (17–24 s observed); this measurement adds the two model turns. |
| SC-002 | ≤ 40% of unassisted | **32.9%** ✅ | T074, above. |
| SC-003 | ≥ 90% of edits apply first try | **100%** (5/5) ✅ | T074. Also asserted offline by `test_greenfield.py::test_every_edit_applied_without_relaxation`. |
| SC-004 | ≥ 70% first-attempt build green | **100%** (1/1) ✅ | T074 — one sample. Re-measure across the seed task set before claiming a rate. |
| SC-005 | ≥ 70% of context from cache | **79.2%** ✅ | T074, write stage. SC-005 asks for five consecutive runs; one is recorded. |
| SC-006 | < 2% of source | **0.079%** ⚠️ | T075, above. Met, but see the coverage finding — the number is not yet meaningful. |
| SC-007 | no run exceeds its ceiling | **0 repairs consumed** ✅ | T074. Also asserted by `test_repair_loop.py` and `test_greenfield.py`. |
| SC-008 | local model ≥ 50% cheaper, build-green within 10 pts | *pending* | Repoint `[stages.write]` to LM Studio (`base_url = "http://localhost:1234/v1"`, `model = "qwen3.6-27b-mtp"`), re-run the same feature, compare `cost_usd` and build-green against the hosted run. **Note:** the committed default binds `route` and `write` to Ollama `qwen2.5-coder:7b`, which is not installed on the measuring machine — `write` degrades to its `cli_shell` fallback, and `route` has no fallback declared. Check which model actually served the stage in the run record before comparing. |
| SC-009 | a question writes nothing | *pending* | `ask` a question about the solution, then assert the run record contains no `EditOperation` and the working tree is unchanged (`git status --short` empty). |
| SC-010 | cost record reconciles within 5% | *pending* | Any completed run: `report --json` and read `derived.reconciled`. Blocked in practice until `claude-opus-5` has an entry in `cabal.session_pricing` — until then the ledger reports it as unpriced rather than reconciled. |
| SC-011 | rejected run < 10% of a completed one | *pending* | Run `plan`, reject at the gate, `report --json` on both that run and a completed one, compare totals. The *mechanism* (nothing is written, no writing tokens spent) is asserted offline by `test_greenfield.py::test_a_rejected_plan_writes_nothing`; only the ratio needs the live run. |

The offline half of each criterion is asserted by the test suite, so a regression fails in CI
rather than waiting for the next manual measurement. What the table above needs is the billed half.
