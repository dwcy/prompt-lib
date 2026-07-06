---
name: git-restore-identity
description: Clear --local user.name and user.email in the current repo (or one given as an argument). Use as a safety net when a Claude commit crashed mid-flight and the repo's .git/config is stuck on "Claude Agent" / "my@agent.commit". Falls through to your real --global identity.
argument-hint: [repo-path]
allowed-tools: Bash(git *), Bash(python *)
---

Run this in the affected repo:

```bash
REPO="$ARGUMENTS"
python ~/.claude/scripts/git-identity.py restore --repo "${REPO:-$PWD}"
```

The script will:

1. Run `git config --local --unset user.name` and `git config --local --unset user.email` (both safe — no-op if already unset).
2. Print the effective identity now visible to git (your `--global` values).

This **never** touches `--global` config or your snapshot at `~/.claude/identity/git-original.json`.

After running, verify with:

```bash
git -C "${REPO:-$PWD}" config user.name
git -C "${REPO:-$PWD}" config user.email
```

Both should show your real identity, not "Claude Agent" / "my@agent.commit".
