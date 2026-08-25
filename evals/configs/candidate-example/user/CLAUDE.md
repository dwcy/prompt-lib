# Global instructions

You are working in a Python repository. Follow existing conventions.

## Code quality

- `from __future__ import annotations` at the top of every new module, plus a one-line module docstring.
- Handle edge cases explicitly; no bare excepts.
- Tests assert behaviour, cover failure modes, and are independent of each other.

## Scope discipline

- Change only what the task asks for — no unrequested refactoring, renames, or drive-by fixes.
- Do not create files beyond those the task names.
