---
name: git
description: Full git workflow with branch safety, conventional commits authored as my@agent.commit, category tags (ui/dotnet/python/css/html/js/ts), and push guard. Subcommands: commit (default), branch, init.
allowed-tools: Bash, Read, Glob
---

## Subcommands

- `/git` or `/git commit` → commit flow (most common)
- `/git branch <name>` → create and switch to a new branch
- `/git init` → initialise a repo with `main` as the default branch

---

## /git commit

### Step 1 — Branch safety check

```bash
git rev-parse --abbrev-ref HEAD
```

If the current branch is `main` or `master`, **stop immediately**. Do not proceed. Tell the user:

> You are on `main`/`master`. Create a feature branch first with `/git branch <name>`.

### Step 2 — Inspect changes

Run in parallel:

```bash
git status --short
git diff --staged
git diff
```

If nothing is staged, show the unstaged changes and ask the user which files to stage. Do not auto-stage everything.

### Step 3 — Determine commit type

Pick the type that best fits the changes:

| Type | When to use |
|---|---|
| `feat` | New user-facing feature or meaningful capability |
| `task` | Smaller piece of work — scaffolding, wiring, minor addition |
| `fix` | Bug fix |
| `refactor` | Internal restructure with no behaviour change |
| `test` | Adding or updating tests only |
| `docs` | Documentation only |

`task` is a first-class type here for work that is real but smaller than a full `feat`.

### Step 4 — Choose category tags

Ask the user which tags apply to this commit (multi-select, all optional):

```
ui  dotnet  python  css  html  js  ts
```

### Step 5 — Draft the commit

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

**Body (always include — this is the description):**

```
Why this change was made, what problem it solves, or any non-obvious context.
One short paragraph or a tight bullet list. Skip if the subject is truly self-explanatory.

Tags: ui, dotnet   ← append selected tags here as a line
```

### Step 6 — Show and confirm

Display the full proposed commit message. Ask for confirmation before committing.

### Step 7 — Commit with agent authorship

Use `-c` flags to set the author for this commit without touching git config:

```bash
git commit \
  -c user.email="my@agent.commit" \
  -c user.name="Claude Agent" \
  -m "$(cat <<'EOF'
<subject>

<body>

Tags: <selected tags>
EOF
)"
```

### Step 8 — Apply git tags

After a successful commit, apply a lightweight tag per selected category, suffixed with the short commit SHA to avoid conflicts:

```bash
SHA=$(git rev-parse --short HEAD)
git tag "ui-$SHA"       # for each selected tag
git tag "dotnet-$SHA"
# etc.
```

Report which tags were applied.

> **Tag cleanup:** Category tags accumulate over time. Prune old ones periodically:
> ```bash
> for CAT in ui dotnet python css html js ts; do
>   git tag --list "$CAT-*" | sort -r | tail -n +11 | xargs -r git tag -d
> done
> ```

### Step 9 — Never push

Do **not** run `git push` unless the user explicitly says to push. End with:

> Committed. Run `/git push` or `git push` when you're ready to push.

---

## /git branch \<name\>

Branch naming format: `<your-name>/<feat>` or `<your-name>/<feat>-<task>`

Examples:
```
dawid/place-order-api
dawid/authentication-login
dawid/payment-refactor
```

1. Read the user's name from git config:
   ```bash
   git config user.name
   ```
   If not set, ask for their first name.

2. If the user provided a full branch name, use it as-is.
   If they provided just a description (e.g. "place order api"), convert it:
   - kebab-case the description
   - prefix with their name: `dawid/place-order-api`

3. Check the branch does not already exist:
   ```bash
   git branch --list "<name>"
   ```

4. Create and switch:
   ```bash
   git checkout -b <name>
   ```

5. Confirm the new branch name and current branch.

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
