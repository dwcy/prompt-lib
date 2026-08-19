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
