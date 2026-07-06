---
name: using-git-worktrees
description: Create, list, switch, or remove a git worktree for multi-session work on one repo. Use when running multiple Claude Code instances in parallel on the same repository, or when /executing-plans needs an isolated workspace for a feature branch. Subcommands — create (default), list, remove, prune.
argument-hint: create <branch> | list | remove <path> | prune
allowed-tools: Bash(git *), Read, Glob
---

## Why

When two or more Claude Code sessions touch the same checkout, they fight for `.git/index.lock`, clobber each other's working-tree state, and produce noisy mid-write diffs. A worktree gives each session its own checkout backed by the same `.git` repository — independent file state, independent branch, shared history.

This skill is the user-facing primitive. The orchestrator daemon uses its own `WorktreeManager` (`services/orchestrator/src/orchestrator/worktree.py`) for the same isolation reason; the conventions match (sibling layout, refuse-on-uncommitted) so both layers behave consistently.

---

## Subcommands

- `/using-git-worktrees` or `/using-git-worktrees create <branch>` → create or switch (default)
- `/using-git-worktrees list` → list all worktrees
- `/using-git-worktrees remove <path>` → remove one
- `/using-git-worktrees prune` → drop stale refs to deleted worktrees

---

## Pre-flight (every subcommand)

Refuse to operate when the current working directory is itself inside a worktree — the user should run this from the **main checkout** so the sibling-layout convention holds. Detect via:

```bash
git rev-parse --git-dir
git rev-parse --git-common-dir
```

If those two paths differ, the cwd is a linked worktree. Stop and tell the user:

> You are inside a worktree. Run this from the main checkout.

---

## /using-git-worktrees create `<branch>`

### Step 1 — Resolve names

```bash
git rev-parse --show-toplevel
```

- `<repo>` = basename of toplevel
- `<branch>` = the user-provided argument (refuse if missing, empty, or `main`/`master`)
- `<branch-slug>` = `<branch>` with `/` replaced by `-`
- `<target>` = `../<repo>-<branch-slug>` (sibling directory)

### Step 2 — Verify the branch exists or offer to create it

```bash
git show-ref --verify --quiet refs/heads/<branch>
```

- Exit code `0` → branch exists. Use it.
- Exit code `1` → branch missing. Ask: "Create new branch `<branch>` off the current HEAD?" Wait for confirmation, then `git branch <branch>`.

### Step 3 — Add the worktree

```bash
git worktree add <target> <branch>
```

If `<target>` already exists, fall through to `list` semantics — show the existing worktree and tell the user where it is.

### Step 4 — Tell the user how to switch

The skill cannot `cd` for the user across processes, so print:

> Worktree ready at `<target>`.
> To switch: `cd <target>`
> To run a second Claude Code session there: open a new terminal, `cd <target>`, then start `claude`.

---

## /using-git-worktrees list

```bash
git worktree list
```

Render as a small table with columns: path · branch · HEAD (short SHA). Mark the current worktree if any.

---

## /using-git-worktrees remove `<path>`

### Step 1 — Safety: refuse on uncommitted changes

```bash
git -C <path> status --porcelain
```

If output is non-empty, stop and tell the user:

> `<path>` has uncommitted changes. Commit or stash them first, or rerun with `--force` if you really want to discard.

If the user explicitly passed `--force`, skip this check.

### Step 2 — Remove

```bash
git worktree remove <path>
```

Or, with `--force`:

```bash
git worktree remove --force <path>
```

### Step 3 — Confirm

```bash
git worktree list
```

Show the user that the worktree is gone.

---

## /using-git-worktrees prune

```bash
git worktree prune --verbose
```

This drops administrative refs to worktrees whose directory was deleted out from under git (e.g. by `rm -rf`).

---

## Rules

- Refuse if `<branch>` is `main` or `master` — those belong in the main checkout.
- Always sibling-layout (`../<repo>-<slug>`), never nested under the main checkout.
- Never `cd` for the user — print the path and let them switch.
- Never `git worktree remove --force` without explicit user opt-in.

## Integration

- `/executing-plans` declares this skill as a required workflow dependency. When invoked from there, the caller already validated that we are not on `main`/`master`; this skill still re-checks (cheap and safe).
- `global/hooks/session_start.py` invokes the same `git worktree add` flow programmatically when it detects a second Claude session colliding on a feature branch — sibling layout, branch-slug rule, and target naming all match this skill so manual + automatic creations live alongside each other.
- For orchestrator-daemon use, see `services/orchestrator/src/orchestrator/worktree.py:WorktreeManager` — separate codebase, same convention.
