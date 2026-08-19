---
name: dotnet-codegen
description: Fast, cheap C# backend generation through the cabal.dotnetgen pipeline. Use when the user wants to scaffold a new .NET service, add a feature to one the tool generated, inspect what a run cost, or check which model each stage is bound to — "new dotnet service", "add an endpoint", "scaffold a .NET API", "what did that run cost", "which model is writing my code". Drives the CLI and presents its approval gate; never writes C# itself.
allowed-tools: Bash, Read, Glob, Grep
---

# /dotnet-codegen — driver for the .NET generation pipeline

**This skill runs commands and presents their output. It does not generate C#.**

That division is the whole point. The pipeline routes cheap classification away from expensive
reasoning, orders its prompt so the cache survives between turns, anchors edits on symbols so they
survive `dotnet format`, and stops repairing at a hard ceiling. Writing the code here instead would
bypass every one of those and cost the user more for a worse result.

So: never author C# in this skill, never hand-edit a file the pipeline is about to write, and never
work around a refusal. If a command refuses, report the refusal — it is load-bearing.

## The commands

Every command takes `--project <path>` and accepts `--json`. Run with `--json` and parse stdout;
human-readable text goes to stderr, so stdout always holds exactly one object.

| Command | Use it for |
|---|---|
| `new --template <id> --description "..."` | Scaffold a service. Verifies it builds before returning. |
| `map` | Show the solution's structure — signatures only, no bodies. |
| `plan --request "..."` | Propose a change in prose and mint an approval token. Writes no code. |
| `apply --intent-token <token>` | Execute an approved change, verify it, repair under the ceiling. |
| `change --request "..."` | Route first: answers a question outright, or falls through to `plan`. |
| `providers [--check]` | Show each stage's model, and whether it actually answers. |
| `report [--run <id>] [--last N]` | What runs cost, split by stage and by repair. |

Invoke as `python -m cabal.dotnetgen <command>` from the repo, or `cabal-dotnetgen` if installed.

## Exit codes — read these, do not infer from text

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success | Report what happened. |
| 1 | Failure | Show the error. Do not retry blindly. |
| 2 | Usage error | The invocation was wrong; fix the arguments. |
| 3 | Halted at the repair ceiling | **Stop.** Show every attempt from `history`. The tree is left for inspection. |
| 4 | Environment failure | The toolchain or a provider is broken — not the code. Fix the environment. |
| 5 | Refused at the approval gate | The token was wrong or stale. Re-run `plan`; never fabricate a token. |

## The approval gate

`plan` proposes; `apply` executes. They are separate on purpose: the developer approves a
*description* before any writing tokens are spent, and a rejected plan costs under a tenth of a
completed run.

1. Run `plan --request "..." --json`.
2. **Show the user `intent.summary` and the files it names, and ask for approval.** Present the
   prose as written. Do not summarise it away, and do not decide on the user's behalf.
3. Only with an explicit yes, run `apply --intent-token <token from the plan>`.

The token is bound to both the intent and the solution's current state. If files changed after the
plan, `apply` exits 5 and asks for a fresh plan — that is correct, not an obstacle. Re-run `plan`.

## Scaffolding a new service

Ask which template, then pass it. The set is closed and the choice is permanent for that project.

| Template | Shape | Use when |
|---|---|---|
| `minimal-service` | One project, feature folders, no mediator | Small service, few endpoints |
| `vertical-slice` (default) | Feature-folder slices, one handler each | Most services |
| `clean-arch` | Domain / Application / Infrastructure / Api, CQRS | Larger, longer-lived, multiple consumers |

An unknown name is an error listing the set — never substitute a near match. A request that
contradicts the locked template ("use Dapper instead") is refused naming the lock; report that
rather than trying to satisfy it.

## Reporting a halted run

Exit 3 is the case the user most needs explained. Print the `history` lines verbatim — they name
what each attempt tried and what still failed — then the repair count. Say the working tree was
left as the final attempt produced it, so the partial work can be inspected or salvaged.

Do not offer to "just fix it manually" as the first move. The halt is information: three attempts
failed the same way usually means the request or the environment is wrong, not the edit.

## Cost questions

`report --json` breaks a run into per-stage tokens and cost, and separates repair cost from the
initial attempt. Two fields need care when relaying them:

- **`cache_ratio` absent** means the provider does not report caching, not that nothing was cached.
  Say "not reported", never "0%".
- **`reconciled: false`** means the figures could not be tied out against the provider's own usage.
  Present the cost as an estimate and say why.

## Before a first run on a new machine

`providers --check` answers "will this work" in one call, and exits non-zero if any stage is
unusable. It catches the failure that otherwise surfaces halfway through a run — a model that is
bound but not installed. Run it when anything is misconfigured, before debugging further.
