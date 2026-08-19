# Data Model: Agent Eval & Regression Harness

Entities, fields, validation rules, and state transitions. Wire-level schemas live in [`contracts/`](contracts/); this file is the conceptual model they encode.

## Task

One benchmark unit. Source: `evals/tasks/<id>/task.toml` + `prompt.md`.

| Field | Type | Rules |
|---|---|---|
| `id` | string | = directory name; `[a-z0-9-]+`; unique across tasks |
| `title` | string | required, human label |
| `repo` | path | required; absolute or repo-root-relative path to the target git repo |
| `ref` | string | required; commit-ish resolvable in `repo` (validate: `git rev-parse --verify`) |
| `prompt` | markdown | required; body of `prompt.md` (non-empty) |
| `checks` | CheckSpec[] | ≥1 entry |
| `expected_files` | glob[] | optional; empty = scope tracking disabled for the task |
| `rubrics` | string[] | optional; each must name an existing `evals/rubrics/<name>.md` |
| `timeout_seconds` | int | optional; overrides `eval.config.toml` default (900) |
| `skip_permissions` | bool | optional, default false; opts the run into `--dangerously-skip-permissions` |

### CheckSpec

| Field | Type | Rules |
|---|---|---|
| `kind` | enum | `test` \| `build` \| `lint` \| `custom` |
| `cmd` | string[] | required argv; executed with cwd = worktree |
| `parser` | enum | `pytest` \| `dotnet` \| `exit-code` (default) |
| `timeout_seconds` | int | optional, default 300 |

## ConfigProfile

A named, reproducible agent-visible configuration. Source: `evals/configs/<name>/profile.toml` + overlay files in the same directory.

| Field | Type | Rules |
|---|---|---|
| `name` | string | = directory name; `[a-z0-9-]+` |
| `description` | string | required — what this profile is testing |
| `user_overlay` | path | optional dir copied into the per-run `CLAUDE_CONFIG_DIR` (CLAUDE.md, settings.json, skills/, agents/, rules/…) |
| `project_overlay` | path | optional dir copied into the worktree root (e.g. `.claude/`, project CLAUDE.md) |
| `env` | table<string,string> | optional extra env vars for the agent process |
| `settings_file` | path | optional; passed as `--settings` |

Validation: every referenced path exists inside the profile directory (no reaching outside `evals/configs/<name>/`); at least one of `user_overlay`/`project_overlay`/`settings_file`/`env` present.

## EvalConfig

Harness defaults. Source: `evals/eval.config.toml`.

| Field | Type | Rules |
|---|---|---|
| `runs_per_cell` | int | default 3; ≥1 |
| `adapter` | string | default `claude-code`; must be a registered adapter |
| `agent_model` | string | optional; passed to the adapter (`--model`) |
| `run_timeout_seconds` | int | default 900 |
| `check_timeout_seconds` | int | default 300 |
| `judge.model` | string | required for judge phase |
| `judge.diff_char_limit` | int | per-file truncation threshold, default 20000 |
| `results_dir` | path | default `evals/results` |

## Run

One agent execution for a (task, profile, repetition) cell. Persisted as the cell directory `results/<run-id>/<task>/<config>/<n>/`.

| Field | Type | Notes |
|---|---|---|
| `task_id`, `config_name`, `repetition` | keys | cell identity |
| `status` | enum | see state machine below |
| `failure_reason` | string? | machine-readable (`agent_timeout`, `agent_crash`, `worktree_error`, `check_timeout`, …); null when `completed` |
| `started_at` / `finished_at` | ISO 8601 | harness clock |
| `wall_seconds` | float | agent subprocess duration |
| `artifacts` | — | `patch.diff`, `output.txt`, `transcript.jsonl`, `metrics.json` |

### Run state machine

```
pending → running → completed
                  ↘ failed(reason)
resume rule: cell with valid metrics.json (status completed|failed) → skipped, never re-run
```

A `failed` run still writes `metrics.json` (with nulls where data is missing) so the matrix stays resumable and countable.

## Metrics (per run, `metrics.json`)

| Group | Fields | Rules |
|---|---|---|
| identity | `task_id`, `config_name`, `repetition`, `run_id`, `adapter` | required |
| outcome | `status`, `failure_reason` | required / nullable |
| agent | `tool_calls_total`, `tool_calls_by_name`, `num_turns`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`, `wall_seconds` | numeric or `null` = unavailable — never fake 0 |
| diff | `files_changed`, `insertions`, `deletions`, `unrequested_changes_count`, `unrequested_files[]`, `empty_diff` | required (0 is meaningful here) |
| checks | CheckResult[] | one per CheckSpec, in order |

### CheckResult

| Field | Type | Rules |
|---|---|---|
| `kind`, `cmd` | echo of spec | required |
| `status` | enum | `passed` \| `failed` \| `timeout` \| `error` |
| `exit_code` | int? | null on timeout |
| `passed_count` / `failed_count` | int? | only for `pytest`/`dotnet` parsers |
| `duration_seconds` | float | required |

## Comparison (per task, `comparison.json`)

| Field | Type | Rules |
|---|---|---|
| `task_id` | string | required |
| `baseline_config` / `candidate_config` | string | required |
| `pairs` | PairVerdict[] | one per repetition pairing |

### PairVerdict

| Field | Type | Rules |
|---|---|---|
| `repetition` | int | pairing index (baseline i vs candidate i) |
| `winner` | enum | `baseline` \| `candidate` \| `tie` \| `judge_error` |
| `confidence` | float? | 0–1; null on tie/judge_error |
| `order_agreement` | bool | false forces `winner: tie` |
| `criteria` | {name, favored, note}[] | per rubric criterion |
| `truncated` | bool | any diff truncated for judge context |

## MatrixReport (per run-id, `report.json` + `report.md`)

| Field | Type | Notes |
|---|---|---|
| `run_id`, `created_at`, `tasks[]`, `configs[]`, `runs_per_cell` | identity | |
| `metrics_rows` | Row[] | one row per metric: task pass rate, test pass rate, unrequested changes, avg tool calls, avg tokens, avg wall time, pairwise win rate (≥6 deterministic rows + win rate — SC-004) |
| Row | `{metric, per_config: {mean, min, max, stddev?, n}}` | variance shown when n≥3 (US5-AS3); failed runs excluded from quality means, included in task pass rate |
| `failures` | {task, config, repetition, reason}[] | full failure inventory |

## Relationships

```
EvalConfig 1─* Task            (matrix input)
EvalConfig 1─2 ConfigProfile   (baseline, candidate per invocation)
Task 1─* Run                   (× config × N)
Run 1─1 Metrics, 1─* CheckResult
Task 1─1 Comparison 1─* PairVerdict  (pairs reference two Runs)
run-id 1─1 MatrixReport        (reduces all of the above)
Rubric *─* Task                (by name)
```
