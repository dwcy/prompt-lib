---
name: branch-review
description: Review all changes on the current branch against main — code quality, conventions, and potential issues. Use when the user says "review my changes", "review this branch", or wants a quality pass before opening a PR. Pairs with @code-plan-verifier for plan-conformance checks.
allowed-tools: Bash, Read, Glob
---

Gather context:

```bash
git diff main...HEAD
git log main...HEAD --oneline
```

Also read `CLAUDE.md` to understand the project's conventions before reviewing.

Review the changes and structure findings as:

---

### Critical
Issues that must be fixed before merging — bugs, security problems, broken contracts.

### Warning
Things that should be fixed — convention violations, missing tests, risky patterns.

### Suggestion
Optional improvements — readability, minor optimisations, style preferences.

### Positive
Notable things done well — acknowledge good decisions.

---

**Rules:**
- Only include sections that have findings
- Each finding: one line for the problem, one line for why it matters, a concrete fix if applicable
- Reference file names and line numbers where relevant
- End with one-line verdict: `✅ Approve` / `⚠️ Approve with minor changes` / `❌ Needs work`
