# Implementation Plan: Agent Eval & Regression Harness

**Branch**: `019-agent-eval-harness` | **Date**: 2026-08-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-agent-eval-harness/spec.md`

## Summary

A custom benchmark runner that answers "did this config change actually make the agent better?": it executes a fixed task set from pinned git states in throwaway worktrees, once per (task × config profile × N repetitions) cell, against a baseline and a candidate configuration, then evaluates each run with deterministic code checks, an LLM pairwise judge (both presentation orders), and agent metrics parsed from the CLI's stream-json transcript, and finally reduces everything into a baseline-vs-candidate report. Implementation is a Python package `setup/src/cabal/evals/` (CLI: `python -m cabal.evals`), mirroring the `dotnetgen` package layout. Eval data (tasks, rubrics, config profiles) is versioned under `evals/` at repo root; results are gitignored. Configuration isolation uses `CLAUDE_CONFIG_DIR` pointed at a per-run materialized profile directory so a candidate profile can never leak into the baseline, the user's real `~/.claude/`, or the main working tree.

## Technical Context

**Language/Version**: Python 3.14 (repo standard; stdlib `tomllib` available)
**Primary Dependencies**: stdlib (`subprocess`, `json`, `tomllib`, `pathlib`, `dataclasses`) + `rich` (report table, already a dependency). No new runtime dependencies. `jsonschema` (existing dev dependency) for contract tests.
**Storage**: Filesystem — JSON artifacts per run under `evals/results/<run-id>/…` (gitignored); TOML+markdown task/config/rubric definitions under `evals/` (versioned)
**Testing**: pytest (existing dev group); contract tests under `setup/tests/contract/`, unit/integration under `setup/tests/`
**Target Platform**: Windows-first (this machine), POSIX-compatible paths via `pathlib`; agent CLIs on PATH
**Project Type**: CLI tool (subpackage of the existing `cabal` package, standalone `__main__`)
**Performance Goals**: A 5-task × 2-config × 3-run matrix completes unattended (SC-003); per-run agent timeout default 15 min, per-check timeout default 5 min; harness overhead per run (worktree create/collect/remove) < 10 s
**Constraints**: Zero writes outside worktrees / per-run config dirs / results dir (FR-015, SC-005); no pushes, no commits on user branches; subscription-auth CLIs only (no API key required for v1); incremental, resumable results (FR-011)
**Scale/Scope**: O(10) tasks, 2 configs per invocation, N=3–5 repetitions → ≤ ~100 agent runs per matrix; artifacts are MBs, not GBs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol is implemented.` The harness *consumes* the Claude Code CLI's documented `stream-json` output schema (an external interface we parse, not implement); the parser conforms to the schema already encoded in `setup/src/cabal/dotnetgen/providers/cli_shell.py` / `usage.py` and is covered by contract tests against recorded fixtures.
- **Gate 2 — Subagent Delegation**: Delegation table below maps every phase to an owner from `.specify/memory/agents.md`. ✅
- **Gate 3 — Contract Tests Before Implementation**: The protocol-like surfaces are the artifact schemas (`metrics.json`, `comparison.json`, `report.json`), the task/profile file formats, and the `AgentAdapter` interface. JSON Schemas live in `contracts/`; contract tests (`setup/tests/contract/test_evals_artifacts.py`, `test_evals_definitions.py`) MUST be written and observed failing before runner/judge implementation tasks. ✅ (ordering enforced in tasks.md)
- **Gate 4 — Reversible Config Changes**: `N/A — no files under global/ are touched.` The harness lives in `setup/src/cabal/evals/` and `evals/`; per-run config dirs are synthesized copies, never the deploy source. Rollback = delete the feature branch.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A — v1 adds no new skill or agent.` Entry point is the `cabal.evals` CLI. A thin `/eval` skill is explicitly deferred; if added later it must pass `/review-conflicts` first.
- **Gate 6 — Parallel Isolation**: `N/A — all implementation dispatch is sequential single-writer.` (Note: the harness *itself* creates a worktree per run — that is the product behavior, not subagent dispatch; runs execute sequentially in v1.)

No violations → Complexity Tracking table left empty.

## Subagent Delegation

*Per `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Package structure, runner core, worktree lifecycle, adapters, judge client | `@python-architect` | Python service/CLI structure, subprocess orchestration design |
| Contract tests + unit/integration tests (pytest, recorded stream-json fixtures) | `@python-tester` | Every Python test task goes to the tester |
| Artifact/definition JSON Schemas (`contracts/`) | `@api-designer` | Interface contract design (file formats are the harness's public contract) |
| Seed eval data (`evals/tasks/`, `evals/rubrics/`, config profiles), `.gitignore`, docs, CLAUDE.md marker upkeep | `main` | Cross-cutting repo glue and authored content, no specialist owner |
| Post-implementation plan-compliance audit | `@code-plan-verifier` | Read-only fresh-eyes gate before commit |

### Parallel Execution Map

`N/A` — tasks are dispatched sequentially (single writer at a time). If `/speckit-tasks` later marks any two writing tasks `Parallel: yes`, each concurrent writer gets `isolation: "worktree"` per Gate 6.

## Project Structure

### Documentation (this feature)

```text
specs/019-agent-eval-harness/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (JSON Schemas + adapter contract)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
setup/src/cabal/evals/           # implementation package (mirrors dotnetgen layout)
├── __init__.py
├── __main__.py                  # python -m cabal.evals → cli.main
├── cli.py                       # subcommands: validate | run | judge | report
├── definitions.py               # load/validate Task, ConfigProfile, Rubric from evals/ tree
├── matrix.py                    # cell enumeration, resume logic, run-id, incremental writes
├── worktree.py                  # git worktree add/collect-diff/remove lifecycle
├── profile.py                   # materialize per-run CLAUDE_CONFIG_DIR from a profile
├── adapters/
│   ├── __init__.py
│   ├── base.py                  # AgentAdapter protocol + AgentRunResult
│   └── claude_code.py           # one-shot `claude -p` headless adapter (stream-json)
├── checks.py                    # deterministic checks: test/build/lint runners + diff scope
├── metrics.py                   # stream-json transcript → tool calls, tokens, turns, time
├── judge.py                     # pairwise judge: both-orders, rubric prompt, JSON verdict
└── report.py                    # aggregate → rich table + report.json/report.md

evals/                           # versioned eval data (benchmark-as-code)
├── eval.config.toml             # defaults: N, timeouts, judge model, adapter
├── tasks/<task-id>/task.toml    # id, repo, ref, checks, expected_files, rubrics
├── tasks/<task-id>/prompt.md    # the agent prompt
├── rubrics/*.md                 # architecture.md, coding-quality.md, instruction-following.md
├── configs/<profile>/profile.toml  + overlay files (CLAUDE.md, skills/, agents/, settings.json)
└── results/                     # gitignored; <run-id>/<task>/<config>/<n>/{patch.diff,output.txt,metrics.json}
                                 #            <run-id>/<task>/comparison.json ; <run-id>/report.{json,md}

setup/tests/
├── contract/
│   ├── test_evals_artifacts.py     # metrics/comparison/report validate against contracts/ schemas
│   └── test_evals_definitions.py   # task.toml / profile.toml / eval.config.toml format contract
├── test_evals_worktree.py          # lifecycle against a scratch git repo
├── test_evals_metrics.py           # recorded stream-json fixtures → metrics
├── test_evals_matrix.py            # enumeration, resume-skips-completed, failure isolation
├── test_evals_judge.py             # both-orders logic, disagreement→tie, judge_error path
└── test_evals_report.py            # aggregation math, variance, failed-run handling
```

**Structure Decision**: Subpackage of the existing `cabal` distribution with its own `__main__` (`python -m cabal.evals`), exactly like `cabal.dotnetgen` — no new project, no new console script. Eval definitions live at repo root `evals/` (the user's requested layout), results are gitignored. Per the python.md size rules, every module above stays under the 200/400 LoC caps by design (that is why runner concerns are pre-split into `matrix` / `worktree` / `profile` / `checks` / `metrics`).

## Design Decisions (Phase 0 summary — full rationale in research.md)

1. **Custom runner, not Promptfoo/LangSmith/SWE-bench** — the unit under test is an agent+repo+config triple, not a prompt; details in research.md R1.
2. **Config isolation via `CLAUDE_CONFIG_DIR`** pointed at a per-run synthesized directory built from the profile overlay (R2). The user's `~/.claude/` is never read or written during a run.
3. **One-shot headless invocation** — `claude -p <prompt> --output-format stream-json --verbose --permission-mode acceptEdits` with cwd = the run's worktree (R3). Persistent sessions (dotnetgen's `ClaudeSession`) are wrong here: each run must be a cold, independent trial.
4. **Worktree per run** — `git worktree add --detach` at the pinned ref; diff collected with `git -C <wt> diff` (+ `add -N` for untracked); `git worktree remove --force` after artifact collection (R4).
5. **Metrics from the stream-json transcript** — tool calls = count of `tool_use` blocks, tokens/cost from the `result` event via the same normalization approach as `dotnetgen.providers.usage.parse_usage`, wall time measured by the harness (R5).
6. **Judge = one-shot `claude -p` with a JSON-only verdict prompt**, both A/B orders, disagreement → tie (R6). Judge model/CLI configurable in `eval.config.toml`.
7. **TOML + markdown definitions, no YAML** — stdlib `tomllib` avoids a new dependency (R7).
8. **Adapter interface now, Claude Code adapter only in v1** — Codex/Gemini deferred behind `adapters/base.py` (R8; US6 is P6).

## Complexity Tracking

*(empty — no constitution gate violations)*
