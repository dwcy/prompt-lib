# Phase 0 Research: Project Dashboard Panel

Resolves the unknowns in the Technical Context. Each decision records what was
chosen, why, and the alternatives weighed. The recurring constraint is cabal's
existing posture: subprocess CLIs resolved via `shutil.which`, work done in Textual
worker threads, results marshalled back with `call_from_thread`, stale-while-
revalidate cache in `~/.cabal/cache.json`, and graceful degradation everywhere.

## D1 — Data-source strategy (CLI + token-when-present)

**Decision**: Baseline data from local CLIs + link files; enrich from management/REST
APIs only when an access-token env var is present. Decided in planning clarification.

**Rationale**: `git` and `gh` are already first-class in cabal and authenticated.
`supabase` / `vercel` CLIs expose local-dev state (migrations, link, deployments) but
NOT account-level fields (plan, region, members, backups). Those require the
management APIs with a token. Reading tokens from the environment (never persisting)
keeps the security surface minimal and matches the "no secrets in cache" requirement.

**Alternatives**:
- *CLI-only*: simplest, but cannot deliver plan/region/members/last-backup that the
  user explicitly asked for. Rejected.
- *API-first (required tokens)*: richest, but shows nothing without tokens and breaks
  the "works out of the box for git/GitHub" expectation. Rejected.

## D2 — Local git: branches, remotes, current branch

**Decision**: Shell out to `git` with porcelain/plumbing flags, parsed in a service
module. Commands:
- Current branch: `git -C <proj> rev-parse --abbrev-ref HEAD` (`HEAD` → detached; then
  `git -C <proj> rev-parse --short HEAD` for the SHA).
- Local branches: `git -C <proj> branch --format=%(refname:short)`.
- Remotes: `git -C <proj> remote -v` (parse name + fetch URL), or
  `git -C <proj> remote` + `git -C <proj> remote get-url <name>`.

**Rationale**: Matches the existing `_run_*` subprocess pattern (capture_output, text,
bounded timeout, `shutil.which` guard). Plumbing flags give stable machine-readable
output. No third-party git library needed.

**Alternatives**: `dulwich`/`GitPython` — extra dependency, no benefit for read-only
listing. Rejected. Reading `.git/` directly — fragile across worktrees/packed-refs.
Rejected.

## D3 — GitHub Actions runs + PRs via `gh`

**Decision**: Reuse cabal's `gh` integration (same `_run_gh`-style wrapper). Commands:
- Connection: derive owner/repo from the chosen remote URL (HTTPS `https://github.com/
  owner/repo(.git)` or SSH `git@github.com:owner/repo.git`); confirm with
  `gh repo view --json nameWithOwner` when authenticated.
- Actions runs (current branch): `gh run list --branch <branch> --limit 10 --json
  databaseId,name,status,conclusion,headBranch,url,createdAt`.
- Open PRs: `gh pr list --state open --json number,title,author,url --limit 30`.

**Rationale**: `gh` is already authenticated in cabal (GitHubReposScreen,
gh-accounts). `--json` output is parse-stable. Branch-scoped run listing answers the
user's "github actions to that branch". Unauth path links to the existing
gh-device/gh-accounts flow rather than inventing new auth.

**Alternatives**: Direct GitHub REST with a PAT — duplicates auth cabal already owns.
Rejected. GitHub MCP server — was explicitly removed from this repo (commit history);
not available. Rejected.

**Edge handling**: Multiple GitHub remotes → prefer `origin`, else first GitHub
remote, and note which remote was used (per spec edge case). `gh run list` empty →
"no workflow runs" hint, not an empty table.

## D4 — Supabase: link detection, CLI stats, management API

**Decision**: Detect linkage from the project's local Supabase files; read CLI/local
state for the baseline; call the Supabase Management API when
`SUPABASE_ACCESS_TOKEN` is set.

- **Link detection**: presence of `supabase/config.toml` under the project, plus the
  linked project ref. The ref is discoverable from `supabase projects list`/
  `supabase status` when linked, or from the CLI's local link metadata. The service
  parses the ref defensively (config first, CLI fallback).
- **CLI / local baseline**: `supabase migration list` (last applied migration),
  database connection location (local `supabase/config.toml` db settings / linked
  project ref → standard Supabase db host form), and the dashboard URL.
- **URLs (derived, no network)**: dashboard = `https://supabase.com/dashboard/project/
  <ref>`; Schema Visualizer = `https://supabase.com/dashboard/project/<ref>/database/
  schemas` (the hosted schema view for the project). Derivable purely from the ref.
- **Token-enriched (Management API, `GET` only)**: with `SUPABASE_ACCESS_TOKEN`,
  call the Management API (`https://api.supabase.com/v1/...`) for project status,
  region, plan/subscription, members, and backups (`.../projects/<ref>` and the
  backups/members endpoints). `last backup` = most recent entry's timestamp.

**Rationale**: Honors "if we have a supabase cli installed we should be able to get
some stats" while delivering the account-level fields (plan/region/members/backup)
that only the Management API exposes. URL derivation from the ref needs no network, so
the clickable links always render once a ref is known.

**Alternatives**: Scraping the Supabase dashboard HTML — brittle, auth-hostile.
Rejected. Direct Postgres connection for stats — needs DB credentials and is invasive
for a read-only dashboard. Rejected.

**Open detail for Phase 1**: exact Management API endpoint paths/fields are documented
by Supabase; the service isolates them behind a small client so endpoint specifics are
an implementation detail, not a design risk. Token-rejected (401/403) → "token
rejected" hint while CLI/link fields still render.

## D5 — Vercel: link detection, CLI stats, REST API

**Decision**: Symmetric to Supabase.

- **Link detection**: `.vercel/project.json` under the project (contains `projectId`
  and `orgId`). Presence = linked.
- **CLI / local baseline**: `vercel` CLI (resolved via `shutil.which`) for project name
  and latest deployment status (e.g. `vercel ls --json` / `vercel inspect`), plus the
  project/deployment URL.
- **URLs (derived)**: project dashboard URL from org/project slug; latest production
  deployment URL from the CLI/API response.
- **Token-enriched (REST API, `GET` only)**: with `VERCEL_TOKEN`, call
  `https://api.vercel.com/...` (`/v9/projects/<id>`, team/members endpoints) for
  team/plan, region, and members.

**Rationale**: Same trade-off and degradation model as Supabase, reusing the same
service shape. `.vercel/project.json` is the canonical local link Vercel itself writes.

**Alternatives**: Vercel MCP server is available in this environment, but the feature
targets the cabal TUI (no MCP client there) and must work for end users without MCP.
Use it only as a documentation reference, not a runtime dependency. Rejected as a
runtime path.

## D6 — Async loading, caching, and first paint

**Decision**: Mirror `ClaudeStatsPanel` / `EnvPanel` / `UpdatePanel`:
`run_worker(self._fetch_<section>, thread=True, exclusive=True)` per section;
`self.app.call_from_thread(self._set_<section>, data)` to update render on the UI
thread. On mount, load the cached `DashboardSnapshot` for the current project path via
`widget_cache.load_entry("dashboard:<project-path-hash>")` for instant first paint,
then revalidate. Save fresh snapshots with `save_entry`, **stripping any token-derived
secrets** (store only display values, never the token).

**Rationale**: Reuses proven, tested infrastructure (`tests/integration/
test_widget_panels_cache.py` already covers the cache-paint pattern). Per-section
workers mean one slow/failing source never blocks the others (FR-051/FR-053).

**Alternatives**: One mega-worker fetching all four sources — a single slow source
delays the whole panel. Rejected. `asyncio` instead of threads — the existing codebase
standardizes on `run_worker(thread=True)` for blocking subprocess/HTTP; staying
consistent avoids mixing models. Rejected.

## D7 — Clickable links in the TUI

**Decision**: Use Textual action-link markup `[@click=...]label[/]` in `Static`
widgets, with action handlers on the panel/screen that open the URL via the platform
opener (`webbrowser.open`) — consistent with the existing `[@click=screen.readme]`
pattern in `banner.py`. Each external URL also shown as copyable text for terminals
where click-through is unavailable.

**Rationale**: Established cabal pattern; degrades to readable URLs.

**Alternatives**: OSC-8 hyperlink escape sequences — inconsistent terminal support and
not how cabal currently does links. Rejected.

## D8 — HTTP client for management/REST APIs

**Decision**: Use stdlib `urllib.request` for the `GET`-only management/REST calls
(bounded timeout, `Authorization: Bearer <token>` header), isolated inside the
supabase/vercel service modules. Add no new third-party HTTP dependency unless one is
already present in the project's dependency set.

**Rationale**: Keeps the dependency surface minimal (the repo favors stdlib +
Textual/Rich). The calls are simple authenticated JSON GETs; `urllib` is sufficient.

**Alternatives**: `requests`/`httpx` — nicer ergonomics but a new runtime dependency
for a few GET calls. Reconsider only if the project already vendors one. Rejected for
now.

## D9 — Token security

**Decision**: Read `SUPABASE_ACCESS_TOKEN` / `VERCEL_TOKEN` from `os.environ` at fetch
time only. Never write them to `~/.cabal/cache.json`; the cached `DashboardSnapshot`
holds only rendered display values. Token-present is a runtime boolean, not persisted.

**Rationale**: Satisfies FR-054 / SC-005. The cache is plain JSON on disk; secrets must
never land there.

**Alternatives**: Caching the enriched payload including a token for reuse — violates
the no-secret-in-cache rule. Rejected.

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| Data depth / auth model | D1 — CLI + token-when-present |
| Git data acquisition | D2 — `git` plumbing via subprocess service |
| GitHub Actions + PRs | D3 — reuse `gh` with `--json` |
| Supabase stats + links + members/backups | D4 — CLI/link baseline + Management API on token |
| Vercel stats + links + members | D5 — CLI/link baseline + REST API on token |
| Non-blocking load + first paint | D6 — per-section threaded workers + widget cache |
| Clickable links | D7 — Textual `[@click]` + `webbrowser.open` + copyable URL |
| HTTP client | D8 — stdlib `urllib.request`, GET-only, in service modules |
| Token handling | D9 — env-only, never cached |
