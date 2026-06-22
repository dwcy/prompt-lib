---
name: standup
description: Generate a standup update from recent git activity on the current branch
allowed-tools: Bash
---

Run these commands to gather context:

```bash
git log --oneline --since="yesterday" --author="$(git config user.name)"
git log --oneline -10
git status --short
```

Generate a standup in this format:

**Yesterday**
- [derived from git log — be specific about what was done, not just commit messages]

**Today**
- [ask me what I'm planning to work on today]

**Blockers**
- [ask me if there are any blockers]

Keep each bullet to one line. Be specific — reference feature names, bug IDs, or PR numbers where visible in the log.
