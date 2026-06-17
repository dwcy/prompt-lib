# Phase 1 Data Model: Project Dashboard Panel

All types are plain `@dataclass` (frozen where practical) in
`setup/src/cabal/models/dashboard.py`. They are pure data — no I/O, no Textual
imports — so they serialize cleanly into `~/.cabal/cache.json` and are unit-testable
in isolation. Service modules build these from CLI/API output; the widget only renders
them. **No field ever holds an access token.**

## Enum: AvailabilityState

Per-section state explaining why a section is full / partial / empty, so rendering
picks the right hint (FR-034, FR-043, SC-003).

```python
class AvailabilityState(str, Enum):
    OK = "ok"                       # data present
    NO_CLI = "no_cli"               # required CLI not found on PATH
    NOT_LINKED = "not_linked"       # no link file / not a repo
    NOT_AUTHED = "not_authed"       # CLI present but not authenticated (gh)
    TOKEN_MISSING = "token_missing" # enrich fields unavailable; no token in env
    TOKEN_REJECTED = "token_rejected" # token present but API returned 401/403
    TIMEOUT = "timeout"             # a sub-command/HTTP call exceeded its budget
    ERROR = "error"                 # any other failure (message carried separately)
```

## GitSection

| Field | Type | Notes |
|---|---|---|
| `state` | `AvailabilityState` | OK / NOT_LINKED (not a repo) / NO_CLI / ERROR |
| `current_branch` | `str \| None` | branch name, or short SHA when detached |
| `detached` | `bool` | True → `current_branch` is a SHA |
| `local_branches` | `list[str]` | all local branch names |
| `remotes` | `list[GitRemote]` | name + fetch URL |
| `hint` | `str \| None` | shown when `state != OK` |

### GitRemote
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | e.g. `origin` |
| `url` | `str` | fetch URL (HTTPS or SSH form) |
| `is_github` | `bool` | derived: host is github.com |

**Validation**: `current_branch` required when `state == OK`. `detached=True` requires
a non-None `current_branch`.

## GitHubSection

| Field | Type | Notes |
|---|---|---|
| `state` | `AvailabilityState` | OK / NOT_AUTHED / NO_CLI / NOT_LINKED (no GitHub remote) / ERROR |
| `connected` | `bool` | a GitHub remote exists AND `gh` confirms access |
| `owner_repo` | `str \| None` | `owner/repo` derived from the chosen remote |
| `remote_used` | `str \| None` | which remote was used (e.g. `origin`) |
| `runs` | `list[WorkflowRun]` | Actions runs for the current branch (most-recent first) |
| `pull_requests` | `list[PullRequest]` | open PRs |
| `hint` | `str \| None` | e.g. "run `gh auth login`" |

### WorkflowRun
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | workflow name |
| `branch` | `str` | head branch |
| `status` | `str` | queued / in_progress / completed |
| `conclusion` | `str \| None` | success / failure / cancelled / None while running |
| `url` | `str` | clickable run URL |
| `created_at` | `str` | ISO-8601 |

### PullRequest
| Field | Type | Notes |
|---|---|---|
| `number` | `int` | PR number |
| `title` | `str` | |
| `author` | `str` | login |
| `url` | `str` | clickable URL |

## SupabaseSection

| Field | Type | Notes |
|---|---|---|
| `state` | `AvailabilityState` | OK / NOT_LINKED / NO_CLI / ERROR (CLI/link baseline) |
| `enrich_state` | `AvailabilityState` | OK / TOKEN_MISSING / TOKEN_REJECTED / TIMEOUT (API tier) |
| `project_ref` | `str \| None` | linked project ref |
| `dashboard_url` | `str \| None` | `https://supabase.com/dashboard/project/<ref>` |
| `schema_visualizer_url` | `str \| None` | `.../project/<ref>/database/schemas` |
| `db_location` | `str \| None` | database connection host, derived as `db.<ref>.supabase.co` (Supabase direct connection host) |
| `last_migration` | `str \| None` | last applied migration id/name |
| `status` | `str \| None` | project status (token-enriched) |
| `region` | `str \| None` | token-enriched |
| `plan_name` | `str \| None` | token-enriched |
| `last_backup` | `str \| None` | ISO-8601, token-enriched |
| `github_connected` | `bool \| None` | token-enriched |
| `members` | `list[ProjectMember]` | token-enriched |
| `hint` | `str \| None` | baseline hint when `state != OK` |
| `enrich_hint` | `str \| None` | e.g. "set SUPABASE_ACCESS_TOKEN for plan/region/members" |

## VercelSection

| Field | Type | Notes |
|---|---|---|
| `state` | `AvailabilityState` | OK / NOT_LINKED / NO_CLI / ERROR |
| `enrich_state` | `AvailabilityState` | OK / TOKEN_MISSING / TOKEN_REJECTED / TIMEOUT |
| `project_name` | `str \| None` | from `.vercel/project.json` / CLI |
| `project_id` | `str \| None` | from `.vercel/project.json` |
| `dashboard_url` | `str \| None` | project URL |
| `latest_deployment_url` | `str \| None` | latest production deployment |
| `latest_deployment_status` | `str \| None` | READY / BUILDING / ERROR / … |
| `team_plan` | `str \| None` | token-enriched |
| `region` | `str \| None` | token-enriched |
| `members` | `list[ProjectMember]` | token-enriched |
| `hint` | `str \| None` | baseline hint |
| `enrich_hint` | `str \| None` | "set VERCEL_TOKEN for team/region/members" |

### ProjectMember (shared)
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | display name or email |
| `role` | `str \| None` | e.g. owner / member / admin |

## DashboardSnapshot (root)

The full per-project payload, cached and rendered.

| Field | Type | Notes |
|---|---|---|
| `project_path` | `str` | the selected project this snapshot is keyed on |
| `captured_at` | `str` | ISO-8601 UTC build time |
| `git` | `GitSection` | |
| `github` | `GitHubSection` | |
| `supabase` | `SupabaseSection` | |
| `vercel` | `VercelSection` | |

**Cache key**: `dashboard:<hash-of-project_path>` in `widget_cache`. On project change,
a different key is read/written (FR-003, FR-050).

**Serialization rule**: sections must round-trip through `json.dumps`/`loads` with no
token fields. Token-derived values are stored only as their rendered display strings
(e.g. `plan_name="Pro"`), never the credential.

## State transitions (per section, at render time)

```
mount → load cached snapshot (if any) → paint cached → start workers
worker ok        → state=OK, fields populated      → repaint section
worker no-cli    → state=NO_CLI, hint set           → repaint section
worker not-linked→ state=NOT_LINKED, hint set        → repaint section (collapsed)
worker not-authed→ state=NOT_AUTHED, hint+link       → repaint section
enrich no-token  → enrich_state=TOKEN_MISSING        → baseline shown + enrich_hint
enrich 401/403   → enrich_state=TOKEN_REJECTED       → baseline shown + reject hint
worker timeout   → state/enrich_state=TIMEOUT        → timeout hint
worker exception → state=ERROR, message in hint      → error hint (other sections intact)
```
