---
name: github-audit
description: Read-only audit of a repo's GitHub hygiene — checks .github/ folder for required files, checks repo-level settings via `gh api`, reports gaps. Use before opening a PR, before a release, on freshly cloned repos, or whenever you want to know "is this repo configured properly?". Never writes — only reports. To fix gaps, hand off to /github-scaffold (files) or @github-config-manager (settings).
allowed-tools: Read, Bash, Glob, Grep
---

# What this checks

Two halves — same as the file/settings split in the rest of the GitHub bundle:

## A. Files in `.github/`
- `workflows/codeql.yml` (or GitHub-managed Default setup) — code scanning
- `workflows/ci.yml` (or any workflow with `name: CI`) — required for branch protection's status checks
- `dependabot.yml` — version updates
- `CODEOWNERS` — reviewer routing
- `secret_scanning.yml` — optional, only flagged if custom patterns are useful
- `pull_request_template.md` — optional, only suggested if the repo has > 5 contributors

## B. Repo-level settings via `gh api`
- Secret scanning + push protection
- Dependabot alerts + security updates
- Code scanning Default setup vs file-based workflow
- Branch protection rule on default branch (PR required, status checks required, admin enforcement)
- Copilot code review enabled
- Visibility (public / private) and Advanced Security availability — drives what's free vs paid

# How to run the audit

1. Verify prerequisites:
   - `git rev-parse --git-dir` succeeds → otherwise: "Not a git repo, nothing to audit."
   - `gh auth status` succeeds → otherwise: only run the file-half; tell the user "Sign in with `gh auth login` to also audit repo-level settings."
2. Resolve the remote: `gh repo view --json owner,name,visibility,defaultBranchRef -q '.'`. Cache this output — every subsequent check reuses it.
3. Walk the file checks (read-only). Use `Glob` + `Read`. Never modify.
4. Walk the settings checks. One `gh api` call per setting, never batched into shell pipes the user can't audit. Sample calls:

```bash
# Secret scanning + push protection
gh api repos/$OWNER/$REPO --jq '.security_and_analysis'

# Dependabot alerts
gh api repos/$OWNER/$REPO/vulnerability-alerts -i 2>&1 | head -1
# 204 = enabled, 404 = disabled

# Code scanning workflows known to GitHub
gh api repos/$OWNER/$REPO/code-scanning/default-setup --jq '.state' 2>/dev/null

# Branch protection on default branch
gh api repos/$OWNER/$REPO/branches/$DEFAULT_BRANCH/protection 2>/dev/null

# Auto-add Copilot as reviewer (org-level setting; per-repo override lives in repo rules)
gh api repos/$OWNER/$REPO/rules/branches/$DEFAULT_BRANCH --jq '.[] | select(.type=="required_reviewers")' 2>/dev/null
```

5. Compile the report. Format below.

# Report format

Print as a single block — never interleave with shell output. Use checkboxes so a human can scan it in under 10 seconds.

```
GitHub audit — <owner>/<repo>   (<visibility>, default branch: <default_branch>)

Files (.github/)
  [✓] workflows/codeql.yml          (matrix: python, actions)
  [✓] workflows/ci.yml              (job names: test)
  [✓] dependabot.yml                (3 ecosystems: pip x2, github-actions)
  [ ] CODEOWNERS                    — missing; reviewers won't be auto-routed
  [-] secret_scanning.yml           — optional; not flagged (no custom patterns needed)

Settings (gh api)
  [✓] Secret scanning               enabled
  [✓] Push protection               enabled
  [✓] Dependabot alerts             enabled
  [ ] Dependabot security updates   disabled — vuln PRs won't be auto-opened
  [✓] Code scanning                 file-based (codeql.yml)
  [ ] Branch protection on main     not configured
  [-] Copilot code review           N/A (no Copilot subscription detected)

Plan context
  Public repo — CodeQL, secret scanning, push protection, Dependabot all FREE.
  Copilot code review / coding agent require Copilot Business or Enterprise.

Suggested next actions
  1. /github-scaffold     — add the missing CODEOWNERS
  2. @github-config-manager — enable Dependabot security updates + set branch protection
```

Legend:
- `[✓]` configured
- `[ ]` missing or disabled — actionable gap
- `[-]` not applicable on this plan / not needed

# Plan-awareness rules (driving the report)

Mirror this table — if the repo is private and the user has no GHAS, certain settings can't be enabled at all. Mark them `[-] N/A on this plan` rather than `[ ] disabled` to avoid sending the user on a paid wild-goose chase.

| Feature | Public free | Private no GHAS | Private + GHAS | Copilot Business+ required |
|---|---|---|---|---|
| Secret scanning + push protection | ✓ | ✗ N/A | ✓ | no |
| CodeQL code scanning | ✓ | ✗ N/A | ✓ | no |
| Dependabot alerts + security updates | ✓ | ✓ | ✓ | no |
| Dependabot version updates | ✓ | ✓ | ✓ | no |
| Copilot Autofix on code scanning | ✓ (free for public) | included with Copilot | included with Copilot | yes |
| Copilot code review as PR reviewer | ✓ if subscription | ✓ if subscription | ✓ if subscription | yes |
| Copilot coding agent (assignable issues) | ✓ if enabled in org | ✓ if subscription | ✓ if subscription | yes |
| Branch protection rules / Rulesets | ✓ | ✓ (rulesets are paid on private) | ✓ | no |

Detect Copilot availability with:

```bash
gh api user/copilot/billing 2>/dev/null   # 200 if user has Individual
gh api orgs/$OWNER/copilot/billing 2>/dev/null  # 200 if org has Business/Enterprise
```

If both 404, treat Copilot features as N/A.

# Hard rules

- **Read-only.** Never call `gh api ... -X POST/PUT/PATCH/DELETE`. If something is missing, name the skill or agent that fixes it — don't fix it yourself.
- **Never assume a token scope.** If `gh api` returns 403, report `[?] needs `repo` + `security_events` scopes` and move on; don't loop.
- **Never quote private repo content in the report.** The audit goes in chat / PR comments — strip anything that looks like a token or path leaking secrets.
- **Cache the repo metadata** from `gh repo view` once at the top. Subsequent calls reuse it. Don't pound the API.
- **Treat 404 as authoritative**, not as an error. `vulnerability-alerts` returns 404 when alerts are disabled — that's the answer, not a failure.

# Composes well with

- `/github-scaffold` — fixes missing files
- `@github-config-manager` — fixes missing settings (interactive Q&A)
- `/pr` — run `/github-audit` first to make sure the PR will pass branch protection's required checks
- `/finishing-a-development-branch` — natural pre-merge gate
