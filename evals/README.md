# Agent Eval & Regression Harness — benchmark data

This tree is benchmark-as-code for `python -m cabal.evals`: it answers *"did my
config change (skill, agent, hook, instruction) actually make the coding agent
better?"* by A/B-running two configuration profiles over the same tasks and
comparing deterministic checks, agent metrics, and an LLM pairwise judge.

Authoritative format spec: [`specs/019-agent-eval-harness/contracts/definitions-format.md`](../specs/019-agent-eval-harness/contracts/definitions-format.md).
Design tree: `specs/019-agent-eval-harness/`.

## Layout

```text
evals/
├── eval.config.toml            # defaults: runs per cell, adapter, timeouts, judge model
├── tasks/<task-id>/task.toml   # target repo, pinned ref, checks, expected_files, rubrics
├── tasks/<task-id>/prompt.md   # the verbatim agent prompt
├── rubrics/<name>.md           # judge criteria (## Criteria bullet list)
├── configs/<profile>/          # profile.toml + overlay files (CLAUDE.md, skills/, …)
└── results/                    # harness output — gitignored, never committed
```

## Workflow

```bash
python -m cabal.evals validate                                   # check this tree
python -m cabal.evals run --baseline baseline --candidate <p> --runs 3
python -m cabal.evals judge <run-id>                             # pairwise, both A/B orders
python -m cabal.evals report <run-id>                            # table + report.json/md
```

Each run executes in a throwaway detached git worktree with a per-run
`CLAUDE_CONFIG_DIR` materialized from the profile — your real `~/.claude/` and
checked-out tree are never touched. Interrupted matrices resume with
`run --resume <run-id>`.

## Authoring rules of thumb

- Pin `ref` to something durable (a commit on a long-lived branch or a tag).
- Give every task at least one deterministic check; keep check commands
  self-contained (the worktree is the cwd; the environment is yours to declare).
- `expected_files` globs power the unrequested-changes metric — declare them
  whenever the task has a bounded scope.
- Run N≥3 repetitions; agent behavior is nondeterministic, single runs prove
  nothing. Deterministic metrics are primary; the judge corroborates.
- Profiles must be hermetic: everything the agent should see goes in the
  overlay dirs; identical baseline/candidate content triggers a no-op warning.
