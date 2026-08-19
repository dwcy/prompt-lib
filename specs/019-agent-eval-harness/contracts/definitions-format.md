# Contract: Eval Definition File Formats

The authored surface of the harness. `python -m cabal.evals validate` enforces everything here; contract tests (`setup/tests/contract/test_evals_definitions.py`) pin the format before implementation (Constitution Gate 3).

## Directory layout (repo root)

```text
evals/
├── eval.config.toml
├── tasks/<task-id>/task.toml
├── tasks/<task-id>/prompt.md
├── rubrics/<name>.md
├── configs/<profile-name>/profile.toml
├── configs/<profile-name>/…overlay files…
└── results/            # gitignored, harness-owned
```

`<task-id>` and `<profile-name>`: `^[a-z0-9-]+$`.

## eval.config.toml

```toml
runs_per_cell = 3                 # ≥1
adapter = "claude-code"           # registered adapter name
agent_model = "claude-sonnet-5"   # optional; adapter --model
run_timeout_seconds = 900
check_timeout_seconds = 300
results_dir = "evals/results"

[judge]
model = "claude-haiku-4-5-20251001"
diff_char_limit = 20000           # per-file truncation for judge context
```

## tasks/<id>/task.toml

```toml
title = "Add caching to ProductRepository"
repo = "C:/projects/sample-api"   # or repo-root-relative
ref = "eval/task-003-base"        # any commit-ish; must rev-parse in repo
expected_files = ["src/Repositories/**", "tests/**"]   # optional
rubrics = ["architecture", "coding-quality"]           # names in evals/rubrics/
timeout_seconds = 900             # optional override
skip_permissions = false          # optional; true → --dangerously-skip-permissions

[[checks]]
kind = "test"
cmd = ["dotnet", "test", "--nologo"]
parser = "dotnet"                 # pytest | dotnet | exit-code (default)
timeout_seconds = 300

[[checks]]
kind = "build"
cmd = ["dotnet", "build", "--nologo"]
```

`prompt.md` (required, non-empty) is the verbatim agent prompt.

### Validation rules (validate command MUST report file + field on failure)

1. `task.toml` parses as TOML; unknown keys are errors.
2. `repo` exists and is a git repository.
3. `ref` resolves via `git -C <repo> rev-parse --verify <ref>^{commit}`.
4. `checks` has ≥1 entry; every `cmd` is a non-empty argv list.
5. Every `rubrics` entry names an existing `evals/rubrics/<name>.md`.
6. `prompt.md` exists and is non-empty.

## configs/<name>/profile.toml

```toml
description = "Baseline: current deployed global config, no candidate skill"
user_overlay = "user"        # dir copied into per-run CLAUDE_CONFIG_DIR
project_overlay = "project"  # dir copied into the worktree root
settings_file = "settings.json"  # optional; passed as --settings

[env]                        # optional extra env for the agent process
PROMPTLIB_DISABLED_HOOKS = "pretool_branch_guard"
```

### Validation rules

1. `description` required.
2. Every referenced path exists **inside** `evals/configs/<name>/` (no `..`, no absolute paths).
3. At least one of `user_overlay` / `project_overlay` / `settings_file` / `env` present.
4. Baseline and candidate with byte-identical materialized content → warning `no-op comparison` (run proceeds).

## rubrics/<name>.md

Free markdown. Convention: one `## Criteria` section with a bulleted criterion list; the judge prompt embeds the file verbatim and asks for a per-criterion verdict using the bullet labels.

## Results tree (harness-owned output contract)

```text
evals/results/<run-id>/
├── <task-id>/<config-name>/<n>/patch.diff
│                             /output.txt
│                             /transcript.jsonl
│                             /metrics.json        # metrics.schema.json
├── <task-id>/comparison.json                      # comparison.schema.json
├── report.json                                    # report.schema.json
└── report.md
```

- `metrics.json` is written atomically (`.tmp` → rename) and marks its cell complete; resume skips cells with a valid `metrics.json`.
- All three JSON artifacts carry `schema_version: 1`; any breaking change bumps the version and the schemas in this directory.
