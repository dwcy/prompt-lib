---
name: git
description: Full git workflow — branch safety, staged-file audits (@gitignore-auditor, @secret-auditor), conventional commit through the git-identity wrapper, policy-gated tags, and push guard. Subcommands — commit (default), branch, init.
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(python *), Bash(gh *), Read, Glob
---

## Current state

- Branch: !`git rev-parse --abbrev-ref HEAD`
- Status: !`git status --short`

## Subcommands

- `/git` or `/git commit` → commit flow (most common)
- `/git branch <name>` → create and switch to a new branch
- `/git init` → initialise a repo with `main` as the default branch

All policy values (agent identity, allowed types, branch refusal, tag gating) live in `~/.claude/git-policy.json`. Full mechanics: `docs/git-policy.md` in prompt-lib.

---

## /git commit

### Step 1 — Branch safety check

If the current branch (shown above) is `main` or `master`, **stop immediately**. Do not proceed. Tell the user:

> You are on `main`/`master`. Create a feature branch first with `/git branch <name>`.

The `git-identity` wrapper enforces this too (`policy.refuse_on_branches`), but check up front so the user isn't dragged through the whole flow first.

### Step 2 — Inspect changes

```bash
git diff --staged
git diff
```

If nothing is staged, show the unstaged changes and ask the user which files to stage. Do not auto-stage everything.

### Step 2.5 — Audit staged files for .gitignore worthiness

Once at least one file is staged, invoke the `@gitignore-auditor` subagent to review the staged set for files that look like local-only state, build artifacts, caches, secrets, or IDE/OS junk that should be in `.gitignore` instead.

The auditor is **read-only and advisory** — it does not edit files or run state-changing git commands. It returns a verdict (`CLEAN | WARNINGS | FLAGS`), per-file findings, suggested `.gitignore` lines, and `git rm --cached` commands for files already tracked despite belonging in `.gitignore`.

How to handle the result:

- **CLEAN** — proceed to Step 3.
- **WARNINGS** — surface each warning to the user with the auditor's question. If the user wants to keep the file, proceed; if they want to ignore it, do the `.gitignore` + `git rm --cached` work first, then re-stage and re-run the audit.
- **FLAGS** — show the findings and stop. Do not commit until the user has decided per file. For each FLAG the user accepts: append the suggested line to `.gitignore`, run the suggested `git rm --cached <path>`, then re-stage real changes and continue from Step 2.

The auditor's suggestions are advisory — the user always has the final say.

### Step 2.6 — Audit staged files for secrets

After the gitignore audit (and any resulting `.gitignore` / `git rm --cached` work has settled), invoke the `@secret-auditor` subagent. Read-only, advisory.

The auditor returns:
- Verdict: `CLEAN | SUSPECTED | FOUND`
- Per-finding fields: file, line, detected type, severity (HIGH/MEDIUM/LOW), redacted snippet, recommended action, and a per-finding question to ask the user.

How to handle the result:

- **CLEAN** — proceed to Step 3.
- **SUSPECTED / FOUND** — for **every finding**, ask the user a y/n question of the shape:

  > `secret-auditor flagged a <type> (severity <level>) at <file>:<line>:`
  > `<redacted snippet>`
  > `Recommended action: <action>`
  > `Is this OK to commit? (y/n)`

  Loop one finding at a time. Do not bulk-approve.

  - If the user answers **no**: stop the commit flow. They must edit the file (remove or redact the secret), unstage if they prefer, then re-stage real changes and re-run from Step 2. If the secret has ever been pushed, remind them to rotate it.
  - If the user answers **yes** for a finding: record the explicit approval and continue to the next finding.
  - Once every finding is either resolved or explicitly approved, proceed to Step 3.

  In Step 5 (Show and confirm), include the list of explicitly-approved findings so the user sees the full picture before committing.

### Step 3 — Determine commit type

Pick the type that best fits the changes. Types are enforced by the wrapper against `policy.allowed_types`:

| Type | When to use |
|---|---|
| `feat` | New user-facing feature or meaningful capability |
| `task` | Smaller piece of work — scaffolding, wiring, minor addition |
| `fix` | Bug fix |
| `refactor` | Internal restructure with no behaviour change |
| `test` | Adding or updating tests only |
| `docs` | Documentation only |

`task` is a first-class type here for work that is real but smaller than a full `feat`.

### Step 4 — Draft the commit

**Subject line format:**

```
<type>: <short summary in imperative mood>
```

Examples:
```
feat: add place-order endpoint
task: wire payment service to order handler
fix: handle null reference in user lookup
refactor: extract discount calculation into service
docs: document retry policy for order API
```

Rules:
- Max 72 characters on the subject line
- Imperative mood ("add" not "added", "fix" not "fixed")
- No period at the end

**Body (include when the why is non-obvious):** one short paragraph or a tight bullet list explaining why the change was made or what problem it solves.

### Step 5 — Show and confirm

Display the full proposed commit message. Ask for confirmation before committing.

### Step 6 — Commit through the git-identity wrapper

Never raw `git commit`. The wrapper snapshots the user's real `--global` identity once, applies the agent identity in `--local` scope, commits, and restores — and it enforces type and branch policy:

```bash
python ~/.claude/scripts/git-identity.py commit --repo <repo> -m "<subject>" -m "<body paragraph>"
```

Repeat `-m` per paragraph. Do not add `Co-Authored-By` trailers — the wrapper's identity override replaces that convention.

If the wrapper crashes mid-commit and the identity looks wrong afterwards, repair with `/git-restore-identity` (or `python ~/.claude/scripts/git-identity.py restore`).

### Step 7 — Tags (policy-gated)

Tags are off by default (`policy.tags.agent_may_tag: false`). Do not fall back to raw `git tag`. If the user asks for a tag:

```bash
python ~/.claude/scripts/git-identity.py tag "<name>" -m "<message>" --repo <repo>
```

If the policy gate refuses, report it and point the user at `python ~/.claude/scripts/git-identity.py policy` to change the setting — don't work around it.

### Step 8 — Never push

Do **not** run `git push` unless the user explicitly says to push. End with:

> Committed. Say "push" when you're ready to push.

When the user *does* ask to push, always route git auth through `gh` first — a raw `git push` against an HTTPS remote triggers an interactive askpass prompt that hangs/fails in a non-interactive shell, even when `gh` is authenticated. Check auth status first; that decides the path:

```bash
gh auth status
```

- **Logged in** → `gh auth setup-git` then `git push -u origin <branch>`. Do not ask the user — just push.
- **Not logged in** → stop and ask the user to run `! gh auth login`. Never fall back to a raw `git push`.

---

## /git branch \<name\>

Branch naming format: `<type>/<slug>` — the same `<type>` set as commits, slug in kebab-case, named after the task.

Examples:
```
feat/place-order-api
fix/authentication-login
refactor/payment-service
```

1. If the user provided a full branch name, use it as-is.
   If they provided just a description (e.g. "place order api"), convert it:
   - kebab-case the description
   - prefix with the best-fitting type: `feat/place-order-api`

2. Check the branch does not already exist:
   ```bash
   git branch --list "<name>"
   ```

3. Create and switch:
   ```bash
   git checkout -b <name>
   ```

4. Confirm the new branch name and current branch.

---

## /git init

### Step 1 — Check for existing repo

```bash
git rev-parse --git-dir 2>/dev/null
```

If a repo already exists, report it and stop.

### Step 2 — Initialise with `main`

```bash
git init -b main
```

(`-b main` requires Git 2.28+. If it fails, fall back to `git init && git symbolic-ref HEAD refs/heads/main`.)

### Step 3 — Offer the repo-init template

Ask the user:

> Apply the **dwcy/repo-init** template? It adds:
> - `.editorconfig` — C#, JSON, YAML, web file formatting rules
> - `.gitattributes` — LF line endings everywhere, CRLF for .bat/.ps1
> - `commit-msg` hook — enforces conventional commits at commit time
> - `pre-commit` hook — runs `dotnet format` before every commit
> - `pre-push` hook — runs `dotnet test` before every push
>
> Apply? (y/n)

If **yes**, run Step 4. If **no**, skip to Step 5.

### Step 4 — Apply the template

Templates are stored locally in `~/.claude/git/` — no internet required.

```bash
TEMPLATES="$HOME/.claude/git"
HOOKS_DEST=".git/hooks"

mkdir -p "$HOOKS_DEST"

# Copy hooks
cp "$TEMPLATES/hooks/commit-msg"     "$HOOKS_DEST/commit-msg"
cp "$TEMPLATES/hooks/pre-commit"     "$HOOKS_DEST/pre-commit"
cp "$TEMPLATES/hooks/pre-commit.ps1" "$HOOKS_DEST/pre-commit.ps1"
cp "$TEMPLATES/hooks/pre-push"       "$HOOKS_DEST/pre-push"
cp "$TEMPLATES/hooks/pre-push.ps1"   "$HOOKS_DEST/pre-push.ps1"

# Make shell hooks executable
chmod +x "$HOOKS_DEST/commit-msg" "$HOOKS_DEST/pre-commit" "$HOOKS_DEST/pre-push"

# Copy .editorconfig and .gitattributes
cp "$TEMPLATES/.editorconfig"  .editorconfig
cp "$TEMPLATES/.gitattributes" .gitattributes
```

> **Windows / PowerShell fallback:** If Bash is unavailable, use the Write tool to write each file directly from `~/.claude/git/` to the project. The `task` type is already included in the `commit-msg` hook — no patching needed.

Confirm which files were written and which hooks are now active.

### Step 5 — .gitignore

Check if a `.gitignore` already exists. If not, ask what stack to base it on, then create a minimal one. Do not create it without asking.

### Step 6 — Report

Summarise:
- Current branch: `main`
- Files added (`.editorconfig`, `.gitattributes` if applied)
- Active hooks (if applied)
- No commits yet — ready to stage and commit
