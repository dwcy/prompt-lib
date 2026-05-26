---
name: github-scaffold
description: Scaffold the .github/ folder for a repo — CodeQL workflow, CI workflow, Dependabot config, and CODEOWNERS. Use after `git init`, after `git clone`-ing a bare repo, or when a `/github-audit` says files are missing. Idempotent — never overwrites without confirmation. For repo-level GitHub *settings* (branch protection, secret scanning, Copilot review), use the `@github-config-manager` agent instead.
allowed-tools: Read, Write, Edit, Bash, Glob
---

# What this skill creates

```
.github/
├── workflows/
│   ├── codeql.yml          ← code scanning (CodeQL) — push/PR + weekly cron
│   └── ci.yml              ← repo-specific checks (smoketest, lint, validators)
├── dependabot.yml          ← Dependabot ecosystems (auto-detected from manifests)
└── CODEOWNERS              ← path → reviewer map (commented stub)
```

These are **files in the repo**. They do NOT toggle repo-level GitHub *settings* (secret scanning, push protection, branch protection, Copilot code review) — those live in `gh api repos/...` and belong to `@github-config-manager`.

# Activation flow

1. **Detect repo context.** Run from the repo root. If `.git/` is missing, refuse and tell the user to `git init` first.
2. **Detect manifests** for Dependabot ecosystem selection:
   - `**/pyproject.toml` and `**/requirements*.txt` → `pip` ecosystem (one entry per manifest dir, **not** recursive — Dependabot wants explicit dirs)
   - `**/package.json` (not under `node_modules/`) → `npm` ecosystem
   - `**/Cargo.toml` → `cargo`
   - `**/go.mod` → `gomod`
   - `**/*.csproj`, `**/*.fsproj`, `**/*.sln` → `nuget`
   - `**/composer.json` → `composer`
   - `**/Gemfile` → `bundler`
   - `**/pubspec.yaml` → `pub`
   - `**/Dockerfile`, `**/*.dockerfile` → `docker`
   - Always include `github-actions` at `/` once a `.github/workflows/` exists
3. **Read the user's stack hints** from `CLAUDE.md` to pick a CI test command. If `CLAUDE.md` doesn't exist, ask once: "What command runs your tests locally? (e.g. `pytest`, `pnpm test`, `dotnet test`, `python setup/tools/_smoketest.py`)"
4. **Detect existing `.github/` contents.** For each target file:
   - If absent → create.
   - If present and content-equivalent → silently skip.
   - If present and different → diff and ask before overwriting.
5. **Write files atomically** — never partial. UTF-8, LF line endings (Windows users: git's `core.autocrlf` handles checkout).

# File templates

## `.github/workflows/codeql.yml`

```yaml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "23 4 * * 1"

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  analyze:
    name: Analyze ${{ matrix.language }}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    strategy:
      fail-fast: false
      matrix:
        language: [<DETECTED_LANGUAGES>]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          language: ${{ matrix.language }}
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
```

Replace `<DETECTED_LANGUAGES>` with the matrix from this table — only include languages with source in the repo:

| If repo contains | Include matrix entry |
|---|---|
| `.py` files | `python` |
| `.ts` / `.tsx` / `.js` / `.jsx` files | `javascript-typescript` |
| `.cs` / `.csproj` | `csharp` |
| `.go` / `go.mod` | `go` |
| `.java` / `pom.xml` / `build.gradle` | `java-kotlin` |
| `.kt` (no Java) | `java-kotlin` |
| `.rb` / `Gemfile` | `ruby` |
| `.swift` | `swift` |
| `.rs` / `Cargo.toml` | `rust` (CodeQL Rust support is in beta — note this in the PR description) |
| Any `.github/workflows/*.yml` | `actions` (always include once workflows exist) |

For repos with only configuration / Markdown / shell scripts, **skip CodeQL entirely** and tell the user — the workflow would run with an empty matrix and waste minutes. Recommend running `gitleaks` or `trufflehog` in `ci.yml` instead.

## `.github/workflows/ci.yml`

Project-specific. Default skeleton — replace test command with whatever the user provided (or `CLAUDE.md` documented):

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      # <SETUP_STEPS>  e.g. actions/setup-python@v5, actions/setup-node@v4, pnpm/action-setup@v4
      - name: Run tests
        run: <TEST_COMMAND>
```

If multiple test commands exist (e.g. lint + smoketest + validator), split into discrete steps with `name:` per step — branch protection can require individual step names later.

## `.github/dependabot.yml`

Emit one `updates:` entry per detected manifest directory plus one for github-actions:

```yaml
version: 2
updates:
  # github-actions
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5

  # <REPEAT per detected manifest>
  - package-ecosystem: <ECOSYSTEM>
    directory: <DIR>
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
    groups:
      minor-and-patch:
        update-types: [minor, patch]
```

The `groups: minor-and-patch` block reduces Dependabot PR noise — one PR per ecosystem per week for non-major bumps. Major bumps still get their own PR (they often break things).

## `.github/CODEOWNERS`

Commented stub — let the user fill in. Don't put a default catch-all owner unless the user names one.

```
# CODEOWNERS — see https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
#
# Format: <path-pattern> <owner1> <owner2>
# Owners can be @user, @org/team, or email addresses.
#
# Examples (uncomment and edit):
# *                       @<your-github-username>
# /.github/               @<your-github-username>
# /docs/                  @<your-github-username>
# /services/orchestrator/ @<your-github-username>
```

# Pre-flight checks before writing

- `git rev-parse --git-dir` must succeed → otherwise refuse, ask user to `git init`
- `git config --get remote.origin.url` should contain `github.com` → if not, warn: "These files target GitHub; your remote is not GitHub. Continue anyway?"
- If `.github/workflows/codeql.yml` already exists from the GitHub *Default setup* (UI-managed code scanning), tell the user: "GitHub is already running a managed CodeQL workflow. If we add this file, you'll have two workflows — disable Default setup in *Settings → Code security → Code scanning* before merging."

# After scaffolding

Print a 4-line summary:

```
✓ Created .github/workflows/codeql.yml         (CodeQL: <languages>)
✓ Created .github/workflows/ci.yml             (test: <command>)
✓ Created .github/dependabot.yml               (<N> ecosystems)
✓ Created .github/CODEOWNERS                   (template — edit before committing)

Next:
  1. Review the files (especially CODEOWNERS).
  2. Commit: git add .github && git commit -m "task: scaffold .github/ workflows + dependabot"
  3. Push, then run @github-config-manager to flip the repo-level security toggles
     (secret scanning, branch protection, Copilot code review).
```

# Hard rules

- **Never silently overwrite** an existing file. Diff first; ask.
- **Never include languages CodeQL doesn't actually support** in the matrix. Empty matrix = wasted minutes.
- **Never recommend Default setup AND a committed workflow** at the same time — they conflict; you must pick one.
- **Never write secrets** into workflow files. Workflow inputs that need secrets must reference `${{ secrets.NAME }}` and the secret has to be added separately by the user.
- **`permissions:` block is mandatory** on every workflow — top-level if all jobs share, per-job otherwise. Never omit it; default GitHub Actions permissions are too broad.
- **Pin third-party actions to a SHA** (`uses: foo/bar@abc123...`). For first-party `actions/*` and `github/*` actions, `@v4` etc. is acceptable since GitHub maintains the major tags.
- **`open-pull-requests-limit`** must be set on every Dependabot ecosystem — default of 5 is the floor that keeps the PR list sane.

# Composes well with

- `@init-project` — calls `/github-scaffold` after writing `CLAUDE.md` when the project has a GitHub remote.
- `/github-audit` — read-only counterpart; run it first to see what's missing.
- `@github-config-manager` — handles the *settings* side (branch protection, security toggles, Copilot review) that `/github-scaffold` deliberately does NOT touch.
- `/git` — after scaffolding, the natural next step is committing the files on a feature branch.
