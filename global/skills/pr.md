---
name: pr
description: Sync the branch with main, then draft a PR title and description from the diff, then create it with `gh pr create`. Always runs the sync step first so merge conflicts surface locally where they can be resolved with full context, not in GitHub's web UI.
allowed-tools: Bash, Read
---

## 1 — Sync with main first

Always pull the latest main into the feature branch before creating a PR. This catches conflicts now (where you can fix them locally with full context) instead of after the PR is opened.

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
- **Conflicts reported** — STOP. Resolve conflicts, run the relevant test suite, then `git commit` the merge. Do not push or create the PR until clean.
- **Fast-forward of main fails** (someone rewrote main history) — STOP and ask the user.

Never push or open a PR for a branch that hasn't been sync'd against latest main.

## 2 — Gather context

```bash
git -C <repo> log main..HEAD --oneline
git -C <repo> diff main..HEAD --stat
```

Also `Read` `CLAUDE.md` (project root) if it exists, to pick up scope/voice conventions.

## 3 — Push the branch

Always route git auth through `gh`. A plain `git push` against an HTTPS remote triggers an interactive askpass prompt that fails in a non-interactive shell, even when `gh` is already authenticated. Run `gh auth setup-git` first so git uses gh's credential helper:

```bash
gh auth setup-git
git -C <repo> push -u origin <feature-branch>
```

If the branch already has an upstream, plain `git -C <repo> push` is enough (still after `gh auth setup-git`).

If `gh auth status` shows you are not logged in, stop and ask the user to run `! gh auth login` — do not fall back to a raw `git push` that will hang on a credential prompt.

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
