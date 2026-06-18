---
name: pr
description: Generate a pull request title and description from branch changes, then create the PR with gh cli
allowed-tools: Bash, Read
---

Gather context:

```bash
git log main...HEAD --oneline
git diff main...HEAD --stat
```

Also read `AGENTS.md` if it exists to understand project conventions.

Generate a PR with:

**Title** — `type(scope): short description` (max 72 chars, conventional commits format)

**Description** using this template:

```markdown
## What

[1–3 sentences on what changed and why]

## Changes

- [bullet list of meaningful changes — not a repeat of commit messages]

## Test plan

- [ ] [specific thing to verify manually or via tests]
- [ ] [another verification step]

## Notes

[Any gotchas, follow-up work, or reviewer hints — omit if nothing to add]
```

Show me the title and description and ask for confirmation, then run:
```bash
gh pr create --title "..." --body "..."
```
