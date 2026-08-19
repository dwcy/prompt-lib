# Rubric: Coding Quality

Judge the craftsmanship of the implementation itself, independent of architectural fit.

## Criteria

- **Correctness**: handles the stated requirements including edge cases and error paths, not just the happy path.
- **Readability**: explicit over clever; a reviewer can follow the code without external context.
- **Error handling**: failures are surfaced with context, never swallowed; no bare excepts or silent fallbacks.
- **No dead weight**: no dead code, commented-out blocks, TODO placeholders, or unused imports.
- **Tests**: tests (when part of the task) assert behaviour and outcomes, cover failure modes, and are independent of each other.
