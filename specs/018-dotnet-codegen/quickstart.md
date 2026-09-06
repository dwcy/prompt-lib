# Quickstart: dotnet-codegen

**Feature**: 018-dotnet-codegen | **Status**: planned, not yet implemented

What using this looks like once Phase A ships. Written to be checked against reality at the end of `/speckit-implement` — if the finished tool does not behave like this, one of them is wrong.

---

## One-time setup

```bash
# Deploy the skill to ~/.claude/
python setup/settings-configurator-ui.py     # or: bash setup/tools/apply-global-claude-settings.sh

# Bind each pipeline stage to a provider/model
python -m cabal.dotnetgen providers --check
```

Stage bindings live in the pipeline's own config, not in `settings.json`. A sensible starting point:

| Stage | Binding | Why |
|---|---|---|
| `route` | cheapest available | Question-vs-change is a classification, not reasoning |
| `architect` | strongest available | This is where correctness is decided |
| `write` | cheap hosted, or local via Ollama / LM Studio | Mechanical transcription of an approved intent (research 1.4, SC-008) |
| `verify` | none | The .NET toolchain is the signal. It costs nothing. |

## Create a service (US1)

```text
/dotnet-codegen new "order service with CRUD over orders and a status webhook"
```

1. Asks which of the three templates to use — **the only architecture question you will ever answer for this project** (FR-001a).
2. Scaffolds a solution that already builds, before any model touches it (FR-003).
3. Presents a plan in prose and stops:

```text
PLAN
  Add Order aggregate with Cancel and status transitions
  Add CRUD endpoints under Features/Orders
  Add webhook receiver validating a shared-secret header
  Files:   6 new, 1 modified
  Symbols: Orders.Domain.Order, Orders.Api.Features.Orders.*
  Estimated write cost: $0.04
  [approve / amend / reject]
```

4. On approval it runs unattended: writes, builds, tests, repairs up to the ceiling.
5. Finishes with a service you can run, and a cost record.

Rejecting here costs **under 10% of a full run** (SC-011) — no code was written.

## Add a feature (US2)

```text
/dotnet-codegen change "add a cancel endpoint that refuses already-shipped orders"
```

Same gate, same unattended tail. The structural map is served from cache unless the solution's shape changed (research R5), so this is where the cost curve flattens.

## Ask a question (SC-009)

```text
/dotnet-codegen "what does CancelOrderHandler do?"
```

Answered directly. The change pipeline never runs; nothing is written (FR-010).

## When it stops

```text
HALTED at retry ceiling (3/3)
  attempt 1  CS0246  missing using for IOrderRepository       -> repaired
  attempt 2  CS1061  Order has no member 'ShippedAt'          -> repaired
  attempt 3  xUnit   CancelOrder_RefusesShipped               -> still failing

Working tree left as-is for inspection.
Initial attempt $0.03 | repairs $0.05 | total $0.08
```

It stops rather than continuing to spend. That is the design (FR-021), and it is the specific failure it exists to avoid — see research 1.8.

An environment failure looks different, and consumes **zero** budget:

```text
ABORTED: environment failure (retry budget untouched, 0/3)
  NU1101  package 'Foo.Bar' not found in any configured source
  This is a toolchain/restore problem, not a code defect.
```

## See what it cost (US5)

```text
python -m cabal.dotnetgen report --last 5 --json
```

```text
run     outcome    stages(in/cached/out)   cache%  edits   retries  wall   cost
r-0005  completed  18k/14k/2.1k            78%     7/7     0        3m12s  $0.06
r-0004  completed  17k/13k/1.8k            76%     4/5     1        4m01s  $0.09
```

`cache%` is SC-005. `edits` is SC-003. Both are read off the ledger, not estimated.

---

## Verifying the phase exit criteria

| Criterion | How to check |
|---|---|
| SC-001 | `report` — `wall_clock_seconds < 600` on a `new` run |
| SC-002 | Compare a `report` total against the same task done in an unassisted session |
| SC-003 | `derived.edit_success_rate >= 0.90` |
| SC-004 | `first_attempt_build_green` across runs `>= 70%` |
| SC-005 | `derived.cache_ratio >= 0.70` over 5+ consecutive runs |
| SC-007 | No record anywhere with `consumed > ceiling` |
| SC-008 | Rebind `write` to a local model, re-run, compare `cost_usd` and build-green |
| SC-009 | A question produces no `EditOperation` records |
| SC-010 | `derived.reconciled == true` |
| SC-011 | A rejected run costs under 10% of a completed one |
| SC-012 | `stage_costs.architect` absent or zero on an existing project |

SC-006 is a **Phase B** criterion — it needs a 20k-line solution the tool did not generate (research R2).
