---
name: commit
description: Generate a conventional commit message from staged changes and create the commit after confirmation
allowed-tools: Bash
---

Run `git diff --staged` to see what is staged.

Then generate a commit message following the **Conventional Commits** format:

```
type(scope): short description

Optional longer body explaining WHY, not WHAT.
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`

**Rules:**
- Subject line max 72 characters
- Subject line is imperative mood ("add" not "added")
- Scope is the module, feature, or layer affected (optional but preferred)
- Body only if the why is non-obvious

Show me the proposed message and ask for confirmation before running `git commit`.
