---
name: commit
description: Generate a policy-compliant commit message from staged changes and create the commit via the git-identity wrapper after confirmation
allowed-tools: Bash
---

Run `git diff --staged` to see what is staged.

Then generate a commit message following the commit policy (`~/.claude/git-policy.json`):

```
<type>: <short description>
```

**Types:** `feat`, `task`, `fix`, `refactor`, `test`, `docs`

**Rules:**
- Subject line max 72 characters
- Subject line is imperative mood ("add" not "added"), no trailing period
- Body only if the why is non-obvious — repeat `-m` per paragraph

Show me the proposed message and ask for confirmation, then commit via the git-identity wrapper (never raw `git commit`):

```bash
python ~/.claude/scripts/git-identity.py commit -m "<type>: <subject>"
```
