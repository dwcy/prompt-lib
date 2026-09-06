# Rubric: Instruction Following

Judge how faithfully the agent did what was asked — no more, no less.

## Criteria

- **Scope adherence**: only the requested change was made; no unrequested refactoring, renames, or drive-by fixes.
- **Completeness**: every explicit requirement in the task prompt is implemented; nothing was silently skipped or stubbed.
- **Constraint compliance**: explicit constraints in the prompt (files to touch, patterns to follow, things to avoid) were respected.
- **Communication**: the final output states what was done and flags anything genuinely deferred, without overclaiming.
