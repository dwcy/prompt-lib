---
name: pr
description: Create a pull request. Use when the user says "open a PR", "create a pull request", "make a PR for this branch", or a finished branch needs to go to GitHub. Always fetches latest remote main and merges it into the branch first so conflicts surface locally; conflicts are resolved by hand keeping both sides' intent — incoming main changes are never skipped or overridden. Then drafts a PR title and description from the diff and creates it with `gh pr create`. For release-bound branches consider @owasp-security-reviewer and @code-plan-verifier first (see /finishing-a-development-branch).
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(gh *), Read
---

## 1 — Sync with main first

Always fetch the latest main **from the remote** and merge it into the feature branch before creating a PR — local main may be stale, so the fetch is not optional. This catches conflicts now (where you can fix them locally with full context) instead of after the PR is opened.

```bash
git -C <repo> fetch origin --prune
git -C <repo> checkout main
git -C <repo> merge --ff-only origin/main
git -C <repo> checkout <feature-branch>
git -C <repo> merge main --no-edit
```

Interpret the merge result:

- **"Already up to date"** — continue to step 2.
- **Clean merge with a merge commit** — continue to step 2; the merge commit will be part of the PR.
- **Conflicts reported** — STOP and follow the conflict protocol below. Do not push or create the PR until the merge is committed clean and tests pass.
- **Fast-forward of main fails** (someone rewrote main history) — STOP and ask the user.

Never push or open a PR for a branch that hasn't been sync'd against latest remote main.

### Conflict resolution protocol

Incoming main changes are someone's landed work — they are never noise to be cleared away.

1. **List the conflicts:** `git -C <repo> diff --name-only --diff-filter=U`.
2. **Understand BOTH sides of each file before touching it:**
   ```bash
   git -C <repo> diff <file>                                  # combined conflict view
   git -C <repo> log --oneline main..HEAD -- <file>           # what this branch changed
   git -C <repo> log --oneline HEAD..origin/main -- <file>    # what landed on main
   ```
3. **Resolve by hand, preserving the intent of both sides.** Forbidden shortcuts — never do any of these, even to "unblock":
   - `git merge -X ours` / `-X theirs`, or `git checkout --ours` / `--theirs <file>` as a wholesale resolution
   - deleting or skipping incoming hunks you don't fully understand
   - `git merge --abort` and then pushing the un-synced branch anyway
   - force-push or history rewrites to make the conflict disappear
4. **Not sure which side should win, or the two sides genuinely contradict?** STOP and ask the user. Show the conflicting hunks and suggest a manual diff they can run themselves, e.g. `git diff HEAD...origin/main -- <file>` — do not guess.
5. **After resolving:** run the relevant test suite, then commit the merge via the git-identity wrapper (never raw `git commit`, never `--no-verify`): `python ~/.claude/scripts/git-identity.py commit --repo <repo> -m "task: merge origin/main into <feature-branch>"`.

## 2 — Gather context

```bash
git -C <repo> log main..HEAD --oneline
git -C <repo> diff main..HEAD --stat
```

Also `Read` `CLAUDE.md` (project root) if it exists, to pick up scope/voice conventions.

## 3 — Push the branch

Always route git auth through `gh`. A plain `git push` against an HTTPS remote triggers an interactive askpass prompt that fails in a non-interactive shell, even when `gh` is already authenticated.

**First, check auth — this decides the path:**

```bash
gh auth status
```

- **Logged in** → set up the credential helper and push (no need to ask the user):
  ```bash
  gh auth setup-git
  git -C <repo> push -u origin <feature-branch>
  ```
  If the branch already has an upstream, plain `git -C <repo> push` is enough (still after `gh auth setup-git`).
- **Not logged in** → stop and ask the user to run `! gh auth login`. Do not fall back to a raw `git push` that will hang on a credential prompt.

## 4 — Draft and create the PR

**Title** — `type(scope): short description` (max 72 chars, conventional commits format).

**Description** — use this template:

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
gh pr create --title "..." --body "$(cat <<'EOF'
...body here...
EOF
)"
```

Pass the body via a heredoc so multi-line markdown and special characters survive intact.
