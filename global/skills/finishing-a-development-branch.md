---
name: finishing-a-development-branch
description: Finish a feature branch — run tests, verify build, create a commit, and offer to open a PR or push. Use after all implementation tasks are done.
allowed-tools: Bash, Read, Glob
---

Announce: "I'm using the finishing-a-development-branch skill."

## Step 1 — Verify tests pass

Detect the test framework and run the full suite:

| Stack | Command |
|---|---|
| .NET | `dotnet test` |
| Bun | `bun test` |
| Node | `npm test` or `npx vitest run` |
| Python | `python -m pytest` |

Stop and report failures. Do not commit with failing tests.

## Step 2 — Verify build

| Stack | Command |
|---|---|
| .NET | `dotnet build --no-restore` |
| Frontend | `bun run build` or `npm run build` |

Stop and report errors.

## Step 3 — Stage and commit

Run in parallel:

```bash
git status --short
git diff --staged
git diff
```

If there are unstaged changes, show them and ask which files to stage. Do not auto-stage everything.

Then invoke the `/git` skill to create the commit — it handles conventional format, branch safety check, agent authorship, and category tags.

## Step 4 — Present completion options

Ask the user:

1. **Open a PR** — run `/pr`
2. **Push only** — `git push -u origin HEAD`
3. **Stay local** — stop here

Never push or create a PR unless the user explicitly chooses it.
