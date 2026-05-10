---
name: commit
description: Lightweight quick commit — no branch safety check, category tagging, or agent authorship. Generates a conventional commit message from staged changes and commits after confirmation. For the full workflow (branch checks, tagging, agent authorship), use /git commit instead.
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
