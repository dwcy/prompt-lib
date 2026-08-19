# Quickstart: Agent Eval & Regression Harness

Answering "did my new skill actually make Claude better?" in four commands.

## 1. Author the benchmark (once)

```text
evals/
├── eval.config.toml                 # N=3, adapter, judge model
├── tasks/003-refactor-repository/
│   ├── task.toml                    # repo, pinned ref, checks, expected_files, rubrics
│   └── prompt.md                    # "Add caching to ProductRepository following …"
├── rubrics/architecture.md
└── configs/
    ├── baseline/profile.toml        # current config, without the change under test
    │            user/…              # CLAUDE.md, skills/, agents/ snapshot
    └── skills-v2/profile.toml       # baseline + the new skill
                 user/…
```

Pin each task to a stable ref in its target repo (a tag like `eval/task-003-base` beats a raw SHA for readability).

## 2. Validate

```bash
python -m cabal.evals validate
```

Checks every task, rubric, and profile: TOML shape, pinned refs resolve, referenced files exist. Fix everything it reports before burning agent runs.

## 3. Run the matrix

```bash
python -m cabal.evals run --baseline baseline --candidate skills-v2 --runs 3
```

For each (task × config × repetition) cell the harness:

1. creates a detached worktree at the task's pinned ref,
2. materializes the profile into a scratch `CLAUDE_CONFIG_DIR` (your real `~/.claude/` is never touched),
3. runs `claude -p` headlessly with the task prompt (per-run timeout),
4. collects `patch.diff`, `output.txt`, `transcript.jsonl`,
5. runs the task's checks (tests/build/lint) and writes `metrics.json`,
6. removes the worktree.

Failures are recorded and the matrix continues. Interrupted? Resume without re-running completed cells:

```bash
python -m cabal.evals run --resume <run-id>
```

## 4. Judge and report

```bash
python -m cabal.evals judge <run-id>     # pairwise, both A/B orders; re-runnable anytime
python -m cabal.evals report <run-id>    # terminal table + report.json/report.md
```

Example output:

```text
                     baseline    skills-v2
Task pass rate           71%          84%
Test pass rate           89%          96%
Build success            93%         100%
Unrequested changes      4.7          1.3
Avg tool calls            37           29
Avg tokens               62k          55k
Avg wall time           6.8m         4.2m
Pairwise wins              —          78%   (ties excluded)
```

## Ground rules

- Everything under `evals/results/` is gitignored output; tasks/rubrics/configs are versioned benchmark-as-code.
- The harness never commits, never pushes, never writes to `~/.claude/` or your checked-out tree — worktrees and scratch dirs only.
- N≥3 runs per cell; agent behavior is nondeterministic, single runs prove nothing.
- Deterministic metrics are primary; the pairwise judge is corroborating evidence (order-disagreement → tie, judge errors never mask check results).

## Smoke test (after implementation)

```bash
python -m cabal.evals validate
python -m cabal.evals run --baseline baseline --candidate skills-v2 --tasks 003-refactor-repository --runs 1
python -m cabal.evals judge <run-id> && python -m cabal.evals report <run-id>
```

One task × two configs × one run ≈ two agent invocations + two judge calls — cheap end-to-end proof before a full matrix.
