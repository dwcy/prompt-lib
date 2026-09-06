# Contract: headless CLI surface

**Feature**: 018-dotnet-codegen | **Consumer**: `global/skills/dotnet-codegen/SKILL.md`

This is a real wire contract, not an internal API: the skill parses `--json` output. Per Constitution Gate 3, contract tests for every command below are written and observed failing before implementation.

Shape mirrors the established pattern in `setup/src/cabal/headless.py` — `argparse`, a `--json` flag, a plan/summary/emit split.

Entry point: `python -m cabal.dotnetgen <command> [options]`

---

## Global options

| Option | Effect |
|---|---|
| `--json` | Emit a single JSON object on stdout, nothing else. Human output goes to stderr. |
| `--project <path>` | Solution root. Defaults to cwd. |
| `--retry-ceiling <n>` | Override the repair ceiling. Default **3** (FR-021). |
| `--dry-run` | Plan only. Never writes, never calls a writing model. |

## `new` — create a project (US1)

```text
python -m cabal.dotnetgen new --template <id> --description <text> [--out <dir>]
```

- `--template` must be one of `minimal-service`, `vertical-slice`, `clean-arch`. An unknown value is exit code 2 with the closed set listed — never a fallback (FR-001).
- Records `ProjectState` with the chosen template, immutably (FR-001a).
- Scaffolds from the pre-built skeleton so the solution builds before any model writes to it (FR-003).
- Then runs the standard pipeline, including the approval gate.

**Exit codes**: `0` completed | `2` bad arguments | `3` halted at retry ceiling | `4` environment failure | `5` rejected at gate.

## `change` — request a change (US2)

```text
python -m cabal.dotnetgen change --request <text>
```

Runs route, architect, gate, write, verify. On a question rather than a change, returns immediately with `outcome: "answered"` and no files written (FR-010, SC-009).

## `plan` — architect stage only (the gate, FR-010a)

```text
python -m cabal.dotnetgen plan --request <text> --json
```

Emits a `ChangeIntent` and stops. **Writes nothing and spends no writing tokens** (FR-010c, SC-011). This is the command the skill calls to present the plan for approval.

```json
{
  "status": "proposed",
  "intent": {
    "summary": "...",
    "target_files": ["src/Orders.Api/Features/Cancel/CancelOrder.cs"],
    "target_symbols": ["Orders.Api.Features.Cancel.CancelOrderHandler.Handle(...)"],
    "rationale": "..."
  },
  "intent_token": "sha256:...",
  "estimated_write_cost_usd": 0.0
}
```

`intent_token` is passed to `apply` so an approval cannot be replayed against a different intent.

## `apply` — execute an approved intent

```text
python -m cabal.dotnetgen apply --intent-token <token>
```

Proceeds unattended through write, verify and repair up to the ceiling (FR-010d). A token that does not match the current solution fingerprint is rejected — stale approvals are refused rather than applied to changed code.

## `map` — inspect the structural map (FR-005, FR-006)

```text
python -m cabal.dotnetgen map [--budget <tokens>] --json
```

```json
{
  "fingerprint": "sha256:...",
  "token_count": 812,
  "budget": 1024,
  "omitted_count": 0,
  "omitted_summary": null,
  "entries": [ { "project": "...", "namespace": "...", "type_name": "...", "kind": "class", "visibility": "public", "members": ["..."] } ]
}
```

`omitted_summary` is non-null whenever `omitted_count > 0`. Silent truncation is a contract violation (FR-006).

## `report` — run history (US5)

```text
python -m cabal.dotnetgen report [--run <id>] [--last <n>] --json
```

Emits `RunRecord` objects per [`run-record.schema.json`](./run-record.schema.json).

## `providers` — inspect and validate stage bindings (US4)

```text
python -m cabal.dotnetgen providers [--check]
```

`--check` probes each bound provider and reports reachability without running a pipeline — the diagnostic for FR-027 before a real run depends on it.

---

## Contract test obligations (Gate 3)

| Test | Asserts |
|---|---|
| Unknown `--template` | Exit 2, closed set listed, no files created |
| `plan` writes nothing | No filesystem mutation; `write` stage cost is zero |
| `plan` then `apply` with a mismatched token | Rejected, exit non-zero, no mutation |
| `--dry-run` on every command | No mutation, no writing-model call |
| `map` over budget | `omitted_count > 0` and `omitted_summary` non-null |
| Retry ceiling reached | Exit 3, `retry_budget.consumed == ceiling`, working tree inspectable |
| Environment failure injected | Exit 4, `retry_budget.consumed == 0` |
| Every `--json` output | Validates against its schema |
| Template change attempt | Refused, names the recorded template (FR-001c) |
