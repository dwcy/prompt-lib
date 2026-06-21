# Quickstart: Project Dashboard Panel

How to exercise the dashboard once implemented. cabal is the Textual wizard under
`setup/src/cabal/`.

## Run cabal

```bash
python setup/settings-configurator-ui.py      # interactive TUI wizard
# or the module entry point:
python -m cabal                                 # from setup/src on PYTHONPATH
```

Pick a project at the gate (Init / Open / Recents). The dashboard renders on the
**HomeScreen** for whatever `selected_project` you choose.

## What you should see

The dashboard panel shows four sections for the selected project:

| Section | Always (CLI/link) | Enriched (token in env) |
|---|---|---|
| **Git** | current branch, local branches, remotes | — |
| **GitHub** | connected?, Actions runs for current branch, open PRs | — (uses `gh` auth) |
| **Supabase** | project ref, last migration, db location, dashboard + Schema Visualizer links | status, region, plan, last backup, github-connected, members |
| **Vercel** | project name, latest deployment, project link | team/plan, region, members |

`Ctrl+D` refreshes the dashboard. Links are clickable (and shown as copyable URLs).

## Token enrichment (optional)

The account-level fields require management/REST API tokens read from the environment
(never written to disk). Provide them in your shell before launching cabal:

```bash
# Supabase plan / region / members / last backup
export SUPABASE_ACCESS_TOKEN=sbp_xxx          # (PowerShell: $env:SUPABASE_ACCESS_TOKEN="sbp_xxx")

# Vercel team / plan / region / members
export VERCEL_TOKEN=xxxxxxxx                   # (PowerShell: $env:VERCEL_TOKEN="xxxxxxxx")
```

Without them, those rows collapse to a hint ("set SUPABASE_ACCESS_TOKEN for plan/
region/members") while the CLI/link fields still render.

## Linking a project (prereqs for Supabase/Vercel sections)

- **Supabase**: the project must be linked (`supabase login` + `supabase link
  --project-ref <ref>`), which writes `supabase/config.toml`. The dashboard reads the
  ref from there.
- **Vercel**: the project must be linked (`vercel link`), which writes
  `.vercel/project.json`. The dashboard reads `projectId`/`orgId` from there.
- **GitHub**: reuses cabal's existing `gh` auth. If unauthenticated, the section links
  to the gh-accounts / device-flow already in cabal.

## Degradation matrix to verify

| Condition | Expected |
|---|---|
| Non-git folder selected | Git section: "not a git repository" |
| `gh` not authenticated | GitHub section: "run `gh auth login`" + link |
| `supabase` CLI absent | Supabase section: "supabase CLI not found" |
| No `.vercel/project.json` | Vercel section: "no linked Vercel project" (collapsed) |
| Token set but invalid | Enriched rows: "token rejected"; baseline rows still shown |
| `selected_project = None` | "select a project to see its dashboard" |

## Run the tests

```bash
# from repo root (pytest discovers tests/ and setup/tests/)
python -m pytest tests/unit/test_dashboard_links.py tests/unit/test_dashboard_git_service.py \
                 tests/unit/test_dashboard_services.py -q
python -m pytest tests/integration/test_dashboard_panel.py -q     # Textual Pilot
python -m pytest tests/contract/test_wizard_public_api.py -q      # public-surface contract
```

Expectations:
- Unit tests stub `subprocess` and management/REST HTTP — **no live network**.
- Integration tests use `App.run_test()` + at least one `await pilot.pause()` per the
  Textual smoke-test rule, covering each `AvailabilityState`.
- A regression check: assert no access token appears in `~/.cabal/cache.json` after a
  refresh (SC-005).

## Manual smoke (real project)

1. Open a project that is a git repo with a GitHub `origin` and `gh` authenticated.
2. Confirm Git shows the branch; GitHub shows the latest Actions run conclusion and
   open PR count without leaving Home.
3. `export SUPABASE_ACCESS_TOKEN=...`, relaunch, open a Supabase-linked project, and
   confirm plan/region/members/last-backup appear and the dashboard + Schema Visualizer
   links open in a browser.
