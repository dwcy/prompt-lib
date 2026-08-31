# Phase 0 Research: Environment Variables — Multi-Source Browser

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

Every decision below was verified against this machine or against current vendor documentation,
not recalled. Where a claim was checked live, the check is shown.

---

## R1. Which values can actually be retrieved, per source

**Decision**: Retrievability is a three-state property carried by every entry — `readable`,
`permission_gated`, `never` — and it is decided by the *source*, not by the UI.

| Source | Names | Value | Classification |
|---|---|---|---|
| Repo config file | from disk | from disk | `readable` |
| .NET developer secret store | from disk | from disk | `readable` |
| Azure App Service settings | `az webapp config appsettings list` | returned inline by the same call | `readable` |
| Azure Key Vault secret | `az keyvault secret list` | `az keyvault secret show` | `permission_gated` |
| Vercel (plaintext/encrypted) | REST | REST with decrypt | `permission_gated` |
| Vercel (`type: "sensitive"`) | REST | never returned | `never` |
| GitHub variable | REST | REST | `readable` |
| GitHub secret | REST | **never returned** | `never` |

**Rationale**: The spec's eye control cannot be uniform because the platforms are not uniform.
Making this a first-class declared state (FR-017/FR-018) is what stops a permanently impossible
reveal from rendering as a retryable error.

**Verified live** against `dwcy/prompt-lib` with the current `gh` token (scopes `repo`,
`read:org`): `GET /repos/{owner}/{repo}/environments`, `/actions/variables`, and
`/actions/secrets` all return 200, and the secrets response carries **no** `value` field — names
and timestamps only. That is by design, not a permission shortfall, which is why GitHub secrets
are `never` rather than `permission_gated`.

**Alternatives considered**: Hiding the eye entirely on non-retrievable rows — rejected, because
the absence of a control reads as an oversight and invites bug reports. A disabled control with a
stated reason teaches the constraint instead.

---

## R2. Azure link detection — the precedence ladder

**Decision**: Four signals, first match wins, each carrying its own confidence:

1. `explicit` — a per-project link the user recorded (subscription + resource group).
2. `azd` — `azure.yaml` or a `.azure/` directory; `.azure/<env>/.env` also names the environment.
3. `iac` — `*.bicep` or `*.tf` under `infra/`.
4. `machine_default` — `az account show`. **Lowest confidence, and never presented as a project
   link** (FR-032).

**Rationale**: The requester selected all four. They are not equivalent, so collapsing them into a
boolean would make every project on this machine look Azure-linked — `az account show` currently
returns a real corporate subscription here, and would light up the Azure tab for a repo with no
Azure connection whatsoever. The ladder keeps that signal available while labelling it honestly.

**Verified on this machine**: `az` is installed and signed in (`az account show` returns a
subscription). This repository has **no** `azure.yaml`, `.azure/`, `infra/`, or `*.bicep` — so it
exercises the `machine_default`-only case, which is exactly the one that must not look linked.

**Alternatives considered**: Dropping signal 4 — rejected, the requester asked for it explicitly.
Prompting the user to confirm on first detection — rejected as too intrusive for a read-only
browser; the explicit link (signal 1) already covers correction.

---

## R3. .NET configuration — precedence and key shape

**Decision**: Flatten hierarchical documents to fully-qualified colon-delimited leaf paths
(`Logging:LogLevel:Default`), never list a section that contains only sections, and label each
entry with its layer plus which layer wins. Do **not** compute a merged effective value.

Confirmed precedence, highest to lowest (Microsoft Learn, ASP.NET Core 10 —
*Default app configuration sources*):

1. Command-line arguments
2. Environment variables (not prefixed `ASPNETCORE_` / `DOTNET_`)
3. User secrets (Development environment only)
4. `appsettings.{ENVIRONMENT}.json`
5. `appsettings.json`

Environment variables use `__` as the hierarchy separator, which the platform converts to `:`,
because not every shell accepts a colon in a variable name.

**Rationale**: FR-043 shows the ordering but stops short of a merged value, because the effective
result also depends on which environment the app runs under and on command-line arguments this
module cannot observe. Showing an ordering is a fact; showing a merged value would be a guess
presented with false confidence.

**Also confirmed**: `appsettings.local.json` is **not** a framework convention — only
`appsettings.json` and `appsettings.{ENVIRONMENT}.json` load automatically. The `appsettings*.json`
glob lists it regardless; the module reports what is on disk without claiming the app reads it.

**Alternatives considered**: Computing the effective value for a user-chosen environment —
deferred. It needs an environment picker and still cannot see command-line arguments, so it would
be confidently wrong in exactly the case a developer is debugging.

---

## R4. The .NET developer secret store lives outside the repo

**Decision**: Resolve `<UserSecretsId>` from the project file, then read
`%APPDATA%\Microsoft\UserSecrets\<id>\secrets.json` (Windows) or
`~/.microsoft/usersecrets/<id>/secrets.json` (POSIX). Present it as its own source, badged as
living outside the repository (FR-045), and read **only** stores the selected project declares
(FR-047).

**Rationale**: This is where .NET developers actually keep local secrets — Microsoft's guidance is
explicit that they belong *outside* the project so they cannot be committed. A repo-only scan
would therefore show empty connection strings and nothing else, and a .NET developer would
correctly conclude the screen was broken.

**Verified on this machine**: no `%APPDATA%\Microsoft\UserSecrets` directory exists yet, so the
"declared but never populated" path (FR-046) is the one to build against first and is trivially
testable here.

**Alternatives considered**: Excluding it to keep the scan inside the project boundary — rejected
by the requester after the trade-off was put to them. FR-047 is the compensating control: the id
must come from the selected project, and the module never enumerates the secrets directory.

---

## R5. Fanning out to the collectors without letting one stall the page

**Decision**: The listing route resolves the local sources synchronously (they are file reads and
cost milliseconds), and fans the three external collectors out to a bounded thread pool with a
per-collector timeout. A collector that exceeds its timeout returns `degraded` with a timeout
hint; it never propagates an exception and never delays the response past the cap.

**Rationale**: SC-010 requires first usable content within 3s regardless of how many external
sources are detected or how slow they are, and FR-039 forbids any source blocking render. The
existing collectors are already synchronous, subprocess-driven, and written never to raise, so a
thread pool fits them without rewriting them as async — the work is process and socket waiting,
not CPU.

**Alternatives considered**: One request per source from the frontend — rejected; it multiplies
round trips and moves assembly and ordering into the UI, and the frontend would then have to
reconcile partial failures itself. Making the collectors `async` — rejected; it would mean
rewriting the proven `dashboard_*_service.py` pattern for no gain, since they block on
subprocesses rather than on an event loop.

---

## R6. Reveal is a POST, one entry at a time, always audited

**Decision**: `POST /api/env/reveal` taking a single source/container/entry triple, returning
either a value held only for that response or a stated reason it could not be produced. Every
call writes an audit record naming the entry; the record never contains the value.

**Rationale**: It is a POST rather than a GET despite being a read, because the value must not
land in URLs, browser history, proxy logs, or any query cache. Restricting it to one entry per
call (FR-012) keeps the audit trail meaningful and stops the endpoint becoming a bulk exfiltration
path — which is also why the spec puts bulk reveal and export out of scope.

**Rationale for no caching**: FR-015 forbids persistence beyond the current view, so the frontend
must hold the value in component state and drop it on tab or project change (FR-014), never in the
query cache.

**Alternatives considered**: Returning values inline on the listing route behind a flag — rejected
outright; it defeats the names-first design and would make a single listing request the largest
secret disclosure in the app.

---

## R7. What already exists and is reused rather than rebuilt

Confirmed by reading the tree:

| Need | Existing asset | Reuse |
|---|---|---|
| Vercel/Supabase/GitHub link parsing | `dashboard_links.py` | Extend with the Azure ladder |
| Collector shape (never raises, `AvailabilityState` + hint) | `dashboard_vercel_service.py`, `dashboard_github_service.py` | Copy the pattern |
| Value masking | `redaction.py` | Reuse for the masked display |
| Audit records | `webapi/audit.py` | Reuse for reveal auditing |
| Envelope, precondition digest | `webapi/envelope.py` | Reuse unchanged |
| Frontend table + empty states | `EnvTable.tsx`, `EmptyState.tsx` | Extend |

**Not reusable**: `env_detect.find_env_vars(path)` — despite the promising name it regex-greps
`${VAR}` placeholders out of a *single* file. It answers a different question and is left alone.

---

## Open items deliberately deferred

- **Effective-value computation for .NET** (R3) — needs an environment picker; revisit only if
  users ask for it.
- **Azure Container Apps** — the spec says "application environments"; App Service is the first
  implementation, Container Apps follows the same collector shape if needed.
- **Vercel CLI path** — `vercel` is not installed on this machine, so the REST path with
  `VERCEL_TOKEN` is the primary implementation, matching `dashboard_vercel_service.py`. The CLI
  stays an optional baseline enrichment exactly as it is there.
