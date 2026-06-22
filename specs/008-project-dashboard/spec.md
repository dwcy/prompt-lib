# Feature Specification: Project Dashboard Panel

**Feature Branch**: `008-project-dashboard`
**Created**: 2026-06-15
**Status**: Draft
**Input**: User description: "the prompt lib should get a dashboard panel. Based on the current selected project it should display local git branches and remotes. I should be able to see github actions to that branch and list of pr's created. if we have a supabase cli installed we should be able to get some stats from that. and a url to the supabase I can click. I would like to have info like status, database location, last backup, last migration, github connected, link to the Schema visualiser, my plan name, status, region, project access members. Second part is another panel with similar things but vercel."

## Overview

A dashboard surfaced **on the cabal HomeScreen** that, for the currently selected
project (`CabalApp.selected_project`), aggregates at-a-glance status from four
sources: **local git**, **GitHub**, **Supabase**, and **Vercel**. Each source is
rendered as a section inside a single dashboard panel widget. Data is read from
already-authenticated local CLIs (`git`, `gh`, `supabase`, `vercel`) plus each
project's local link files, and — when an access token is present in the
environment — enriched from the Supabase / Vercel management APIs to show fields
the CLIs do not expose (plan, region, members, last backup, connection status).

Everything degrades gracefully: a missing CLI, missing link file, or missing
token collapses that one section to an actionable hint rather than an error.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local git overview for the selected project (Priority: P1)

As a developer who has selected a project in cabal, I want the dashboard to show
that project's local git state — current branch, all local branches, and
configured remotes — so I can orient myself without leaving the wizard.

**Why this priority**: Git is the only source that needs no external account, no
network, and no extra CLI beyond what cabal already requires. It is the always-on
backbone of the dashboard and the minimum viable slice — useful on its own.

**Independent Test**: Select a git project, open Home, and confirm the Git section
lists the current branch (highlighted), the other local branches, and each remote
with its fetch URL. Select a non-git folder and confirm the section shows a
"not a git repository" hint instead of an error.

**Acceptance Scenarios**:

1. **Given** the selected project is a git repository on branch `feature/x`,
   **When** the dashboard renders, **Then** the Git section shows `feature/x` as
   the current branch, lists every local branch, and lists every remote with name
   and URL.
2. **Given** the selected project is not a git repository, **When** the dashboard
   renders, **Then** the Git section shows "not a git repository" and no traceback
   appears.
3. **Given** `git` is not installed, **When** the dashboard renders, **Then** the
   Git section shows a "git CLI not found" hint.

---

### User Story 2 - GitHub actions and pull requests for the project (Priority: P2)

As a developer, I want to see the GitHub Actions workflow runs for the project's
current branch and the open pull requests for the repository, so I can check CI and
review status from the dashboard.

**Why this priority**: GitHub is the most common remote and cabal already ships an
authenticated `gh` integration (GitHubReposScreen, gh-accounts). Reusing that auth
makes this the highest-value cloud section and the natural second slice.

**Independent Test**: With `gh` authenticated and the selected project pointing at a
GitHub remote, confirm the GitHub section lists recent workflow runs for the current
branch (status + conclusion) and open PRs (number, title, author). With `gh`
unauthenticated, confirm a "run gh auth login" hint appears.

**Acceptance Scenarios**:

1. **Given** the project has a GitHub `origin` remote and `gh` is authenticated,
   **When** the dashboard renders, **Then** the GitHub section shows whether GitHub
   is connected, the most recent Actions runs for the current branch (each with
   status/conclusion and a clickable run URL), and the open PRs (number, title,
   author, clickable URL).
2. **Given** the repository has no GitHub Actions workflows, **When** the dashboard
   renders, **Then** the Actions area shows "no workflow runs" rather than an empty
   table with no explanation.
3. **Given** `gh` is installed but not authenticated, **When** the dashboard renders,
   **Then** the GitHub section shows a "not authenticated — run `gh auth login`"
   hint and offers a link to the existing gh-accounts flow.

---

### User Story 3 - Supabase project stats and quick links (Priority: P3)

As a developer using Supabase, I want the dashboard to show my linked Supabase
project's status, database location/connection, last migration, last backup, plan,
region, and access members, with clickable links to the Supabase dashboard and the
Schema Visualizer, so I can monitor the backend without opening a browser first.

**Why this priority**: Supabase is opt-in and only relevant to projects that use it.
It depends on the panel framework established by P1/P2 and on the richest data path
(CLI + link file + management API token), so it lands after the framework is proven.

**Independent Test**: In a project with `supabase/config.toml` and a linked project
ref, with `supabase` installed, confirm the Supabase section shows the local
migration status and a clickable dashboard URL. With `SUPABASE_ACCESS_TOKEN` set,
confirm plan, region, status, members, and last backup also appear. Remove the token
and confirm those fields collapse to a "set SUPABASE_ACCESS_TOKEN for plan/region/
members" hint while the CLI-derived fields remain.

**Acceptance Scenarios**:

1. **Given** the project is linked to a Supabase project and `supabase` is installed,
   **When** the dashboard renders, **Then** the Supabase section shows the project
   ref, last applied migration, database connection location, a clickable dashboard
   URL, and a clickable Schema Visualizer URL.
2. **Given** `SUPABASE_ACCESS_TOKEN` is set, **When** the dashboard renders, **Then**
   the section additionally shows project status, region, plan name, last backup
   timestamp, GitHub-connected status, and the list of project access members.
3. **Given** no Supabase link file exists for the project, **When** the dashboard
   renders, **Then** the Supabase section shows "no linked Supabase project" and is
   visually collapsed.
4. **Given** `supabase` is not installed, **When** the dashboard renders, **Then**
   the section shows a "supabase CLI not found" hint.

---

### User Story 4 - Vercel project stats and quick links (Priority: P3)

As a developer deploying on Vercel, I want a section mirroring the Supabase one for
my linked Vercel project — deployment status, environment, latest production
deployment URL, region, plan/team, and project members — with a clickable link to
the Vercel project dashboard.

**Why this priority**: Symmetric to Supabase, opt-in, and built on the same panel
framework. It rounds out the dashboard but is not required for the MVP.

**Independent Test**: In a project with `.vercel/project.json`, with `vercel`
installed, confirm the Vercel section shows the project name and latest deployment.
With `VERCEL_TOKEN` set, confirm team/plan, region, and members appear; without it,
those collapse to a hint while CLI-derived fields remain.

**Acceptance Scenarios**:

1. **Given** the project is linked to Vercel (`.vercel/project.json`) and `vercel` is
   installed, **When** the dashboard renders, **Then** the Vercel section shows the
   project name, latest production deployment status, and a clickable deployment /
   project URL.
2. **Given** `VERCEL_TOKEN` is set, **When** the dashboard renders, **Then** the
   section additionally shows team/plan, region, and project members.
3. **Given** no `.vercel/project.json` exists, **When** the dashboard renders,
   **Then** the section shows "no linked Vercel project" and is visually collapsed.

---

### User Story 5 - Fast, non-blocking refresh (Priority: P2)

As a user, I want the dashboard to paint instantly from cached values and refresh in
the background so the HomeScreen is never blocked while CLIs and network calls run,
and I want a manual refresh control.

**Why this priority**: The HomeScreen is the landing surface; blocking it on four
sources of subprocess + network I/O would make the whole wizard feel frozen. The
stale-while-revalidate cache already exists (`widget_cache.py`) and the worker
pattern is established — this is a cross-cutting requirement for every section.

**Independent Test**: Open Home with a warm cache and confirm the dashboard paints
immediately with last-known values and a "refreshing…" indicator, then updates when
workers finish. Trigger manual refresh and confirm sections re-fetch.

**Acceptance Scenarios**:

1. **Given** a previously cached dashboard payload, **When** Home mounts, **Then** the
   dashboard paints the cached values within the first frame and shows a refreshing
   indicator until workers complete.
2. **Given** the dashboard is visible, **When** the user triggers refresh, **Then**
   every section re-fetches in background workers without freezing the UI.
3. **Given** a fetch worker raises, **When** it fails, **Then** only that section
   shows an error hint; the other sections and the rest of Home remain functional.

### Edge Cases

- Selected project changes (user opens a different project) → dashboard re-keys its
  cache by project path and re-fetches for the new project.
- A CLI is installed but a sub-command times out (slow network) → the section shows a
  timeout hint, not a hang; workers have bounded timeouts.
- The git repo has a detached HEAD → current branch shows the short SHA with a
  "detached" marker.
- A remote URL is an SSH form (`git@github.com:owner/repo.git`) → GitHub connection
  detection still recognizes it as GitHub and derives the owner/repo.
- Multiple GitHub remotes exist → the section uses `origin` if present, else the
  first GitHub remote, and notes which remote it used.
- A management-API token is present but invalid/expired → the enriched fields show a
  "token rejected" hint while CLI/link-file fields still render.
- `selected_project` is `None` (no project chosen yet) → dashboard shows a "select a
  project to see its dashboard" placeholder.

## Requirements *(mandatory)*

### Functional Requirements

**Project context & layout**

- **FR-001**: The dashboard MUST scope all data to `CabalApp.selected_project`; when
  it is `None`, the dashboard MUST show a select-a-project placeholder.
- **FR-002**: The dashboard MUST render as a panel on the existing `HomeScreen`,
  composed of four labelled sections: Git, GitHub, Supabase, Vercel.
- **FR-003**: The dashboard MUST re-scope (re-key cache and re-fetch) when the
  selected project changes.

**Local git (P1)**

- **FR-010**: The Git section MUST show the current branch, all local branches, and
  all configured remotes (name + URL) for the selected project.
- **FR-011**: The Git section MUST handle non-repository and missing-`git` cases with
  hints, never tracebacks.
- **FR-012**: The Git section MUST represent a detached HEAD as a short SHA with a
  "detached" marker.

**GitHub (P2)**

- **FR-020**: The GitHub section MUST detect whether the project's remotes point at
  GitHub (HTTPS or SSH form) and derive owner/repo.
- **FR-021**: The GitHub section MUST list recent GitHub Actions workflow runs for the
  current branch, each with status, conclusion, and a clickable run URL.
- **FR-022**: The GitHub section MUST list open pull requests for the repository, each
  with number, title, author, and a clickable URL.
- **FR-023**: The GitHub section MUST reuse cabal's existing `gh` authentication and,
  when unauthenticated, link to the existing gh-accounts / device-flow path.

**Supabase (P3)**

- **FR-030**: The Supabase section MUST detect a linked Supabase project from the
  project's local link file (`supabase/config.toml` + the linked project ref).
- **FR-031**: When `supabase` is installed and a project is linked, the section MUST
  show the project ref, last applied migration, and database connection location.
- **FR-032**: The Supabase section MUST render a clickable Supabase dashboard URL and a
  clickable Schema Visualizer URL for the linked project.
- **FR-033**: When `SUPABASE_ACCESS_TOKEN` is present, the section MUST additionally
  show project status, region, plan name, last backup timestamp, GitHub-connected
  status, and project access members, sourced from the Supabase management API.
- **FR-034**: Missing CLI, missing link file, missing token, or rejected token MUST
  each collapse to a specific hint without breaking other fields/sections.

**Vercel (P3)**

- **FR-040**: The Vercel section MUST detect a linked Vercel project from
  `.vercel/project.json`.
- **FR-041**: When `vercel` is installed and a project is linked, the section MUST show
  the project name, latest production deployment status, and a clickable deployment /
  project URL.
- **FR-042**: When `VERCEL_TOKEN` is present, the section MUST additionally show
  team/plan, region, and project members from the Vercel REST API.
- **FR-043**: Missing CLI, missing link file, or missing token MUST collapse to a
  specific hint without breaking other fields/sections.

**Refresh & performance (P2, cross-cutting)**

- **FR-050**: The dashboard MUST paint cached values on mount (stale-while-revalidate
  via the existing widget cache), keyed by project path.
- **FR-051**: All CLI and network I/O MUST run in Textual worker threads; the
  HomeScreen MUST never block on dashboard data.
- **FR-052**: The dashboard MUST offer a manual refresh control that re-fetches all
  sections.
- **FR-053**: Every fetch worker MUST have a bounded timeout and surface a per-section
  error hint on failure without affecting other sections.
- **FR-054**: No access token MUST ever be written to disk by this feature; tokens are
  read from environment variables only and never persisted in the cache.

### Key Entities

- **DashboardSnapshot**: The full per-project payload cached and rendered — composed of
  one GitSection, one GitHubSection, one SupabaseSection, one VercelSection, plus the
  project path it was keyed on and a captured-at timestamp.
- **GitSection**: current branch (name or detached SHA), list of local branches, list
  of remotes (name + URL), availability state (ok / not-a-repo / no-git).
- **GitHubSection**: connected flag, owner/repo, list of workflow runs (name, branch,
  status, conclusion, url), list of open PRs (number, title, author, url), auth state.
- **SupabaseSection**: linked flag, project ref, dashboard URL, schema-visualizer URL,
  last migration, db location; token-enriched fields (status, region, plan, last
  backup, github-connected, members); CLI/token availability state.
- **VercelSection**: linked flag, project name, latest deployment (status, url);
  token-enriched fields (team/plan, region, members); CLI/token availability state.
- **AvailabilityState**: a per-section enum capturing why a section is full / partial /
  empty (ok, no-cli, not-linked, not-authed, token-missing, token-rejected, timeout,
  error) so rendering can show the right hint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a warm cache, the dashboard renders its first paint within one
  frame of HomeScreen mount (no perceptible block), measured by the cached-payload
  test mounting Home without awaiting any worker.
- **SC-002**: For a git project with an authenticated `gh` and a GitHub remote, a user
  can see current branch, open PR count, and latest Actions run conclusion without
  leaving the HomeScreen.
- **SC-003**: Every section renders a meaningful state (data or a specific hint) in all
  availability permutations — no section ever shows a traceback or a bare empty box.
  Verified by integration tests covering each AvailabilityState.
- **SC-004**: Removing or adding the relevant CLI/token changes only the affected
  section; the other three sections and the rest of Home are unaffected.
- **SC-005**: No access token appears in `~/.cabal/cache.json` after any dashboard
  refresh.

## Assumptions

- The user-selected data depth is **CLI + token-when-present**: local CLIs and link
  files provide the baseline; management/REST API tokens (`SUPABASE_ACCESS_TOKEN`,
  `VERCEL_TOKEN`) enrich the data when set. Decided via planning clarification.
- The dashboard lives **on the HomeScreen as a panel** (not a separate full screen and
  not a tabbed screen). Decided via planning clarification.
- All four sources ship in **one feature, phased internally**: Git (P1) and GitHub (P2)
  first, Supabase and Vercel (P3) built on the same panel framework. Decided via
  planning clarification.
- The Supabase ↔ project and Vercel ↔ project linkage is read from each project's local
  link files (`supabase/config.toml`, `.vercel/project.json`); cabal does not create or
  manage those links.
- `gh` authentication is reused from cabal's existing GitHub integration; no new GitHub
  auth flow is introduced.
- "Last backup" and "plan / region / members" for Supabase are only available via the
  management API and therefore require the access token; the CLI alone cannot provide
  them. Same constraint applies to Vercel team/plan/region/members.
- This feature is read-only with respect to the project, GitHub, Supabase, and Vercel —
  it displays state and opens links; it does not deploy, migrate, or mutate anything.
- Schema Visualizer link is the Supabase-hosted database schema visualizer URL derived
  from the project ref; no local diagram is generated.
