---
name: dependency-audit
description: Audit project dependencies for known vulnerabilities. Use before a release, after adding packages, or when the user says "check dependencies", "any vulnerable packages", "npm audit", or asks about supply-chain risk. Detects the ecosystem and runs pnpm audit / bun audit / pip-audit / dotnet list package --vulnerable, then reports findings by severity with upgrade paths. Read-only — reports and recommends; never upgrades without confirmation.
allowed-tools: Bash, Read, Glob, Grep
---

# /dependency-audit — Known-vulnerability scan of project dependencies

Audit-only: run the scanners, aggregate, report. Never modify manifests or lockfiles in this skill — propose the commands and let the user run or confirm them.

## Step 1 — Detect ecosystems

Check for manifests (a repo can have several — audit each):

| Present | Ecosystem | Scanner |
|---|---|---|
| `pnpm-lock.yaml` | Node (pnpm) | `pnpm audit` |
| `bun.lock` / `bun.lockb` | Node (bun) | `bun audit` |
| `package-lock.json` / `yarn.lock` only | Node (npm/yarn) | Stop — per global rules, ask whether to migrate to pnpm/bun before auditing |
| `pyproject.toml` / `requirements*.txt` | Python | `uvx pip-audit` (add `-r requirements.txt` per file if no pyproject) |
| `*.csproj` / `packages.lock.json` | .NET | `dotnet list package --vulnerable --include-transitive` |

If nothing matches, say so and stop.

## Step 2 — Run scanners

- Run each applicable scanner from the repo root; capture full output.
- Node: audit production and dev separately when signal differs (`pnpm audit --prod` first — prod findings outrank dev tooling findings).
- A scanner that is not installed is a finding, not a dead end — report the install command and continue with the others.
- Never run `npm audit fix`, `pnpm update`, or any mutating variant.

## Step 3 — Report

One table, ordered by severity (critical → high → moderate → low):

| Severity | Package | Installed | Vulnerability | Fixed in | Direct or transitive |

Below the table:
- **Upgrade paths** — the exact command per fix (`pnpm up <pkg>@<version>`, `uv add <pkg>==<version>`, csproj version bump). Group fixes that must move together.
- **Transitive findings** — name the direct dependency that pulls the vulnerable package in; overrides (`pnpm.overrides`) only as a last resort, flagged as tech debt.
- **No findings** — say so explicitly per ecosystem, with the scanner and date, so the clean result is auditable.

## Step 4 — Hand-offs

- Fixes require code changes (major-version bumps with breaking API) → the matching stack architect
- Findings in auth/session/input-handling paths → recommend @owasp-security-reviewer for the surrounding code
- Running before a release → note this skill inside the /finishing-a-development-branch flow
