# Rubric: Architecture

Judge how well the change fits the project's structure and boundaries. The diff and final output are the evidence; the task prompt states the requirements.

## Criteria

- **Fit**: the change lands in the right module/layer for this codebase; no business logic in entry points, views, or CLI glue.
- **Boundaries**: no new coupling between unrelated modules; dependencies point in the existing direction.
- **Minimal surface**: no new abstractions, indirection, or configuration beyond what the task requires.
- **Consistency**: naming, file placement, and idioms match the surrounding code.
- **Reversibility**: the change is self-contained enough to revert cleanly.
