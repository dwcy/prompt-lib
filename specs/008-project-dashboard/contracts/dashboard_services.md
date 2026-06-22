# Contract: dashboard service modules

Each service is a stateless module of pure functions that take a project `Path` and
return a fully-populated section dataclass. **All subprocess / HTTP I/O is confined
here** (Python size rule: no I/O in the widget). Every function:

- resolves CLI argv[0] via `shutil.which` and guards absence → `NO_CLI`
- uses a bounded timeout; on `TimeoutExpired` → `TIMEOUT`
- never raises to the caller — failures become an `AvailabilityState` + hint
- reads tokens from `os.environ` only; never logs or returns them

## `dashboard_links.py` — link-file parsing + URL derivation (no network)

```python
def find_supabase_ref(project: Path) -> str | None: ...        # parse supabase/config.toml + linked ref
def supabase_dashboard_url(ref: str) -> str: ...               # https://supabase.com/dashboard/project/<ref>
def supabase_schema_url(ref: str) -> str: ...                  # .../project/<ref>/database/schemas
def find_vercel_link(project: Path) -> tuple[str|None, str|None]: ...  # (project_id, org_id) from .vercel/project.json
def parse_github_remote(url: str) -> tuple[str, str] | None: ...# (owner, repo) from HTTPS or SSH form, else None
```

- **C-L1**: `parse_github_remote` handles `https://github.com/o/r`,
  `https://github.com/o/r.git`, and `git@github.com:o/r.git`; returns `None` for
  non-GitHub hosts.
- **C-L2**: All functions are pure (no subprocess/network); unit-testable with temp
  dirs and fixed strings.

## `dashboard_git_service.py`

```python
def collect_git(project: Path) -> GitSection: ...
```

- Runs `git -C <project> ...` (current branch, branch list, `remote -v`).
- Not a repo → `state=NOT_LINKED`, hint "not a git repository".
- No `git` → `state=NO_CLI`.
- Detached HEAD → `detached=True`, `current_branch=<short sha>`.
- Tags `GitRemote.is_github` via `dashboard_links.parse_github_remote`.

## `dashboard_github_service.py`

```python
def collect_github(project: Path, current_branch: str | None, remotes: list[GitRemote]) -> GitHubSection: ...
```

- Chooses the remote: `origin` if GitHub, else first GitHub remote; sets `remote_used`.
- No GitHub remote → `state=NOT_LINKED`. No `gh` → `NO_CLI`. `gh` unauth → `NOT_AUTHED`
  with hint linking the gh-accounts flow.
- `gh run list --branch <b> --json …` → `runs`; empty → OK with empty list (UI shows
  "no workflow runs"). `gh pr list --state open --json …` → `pull_requests`.

## `dashboard_supabase_service.py`

```python
def collect_supabase(project: Path) -> SupabaseSection: ...
```

- Baseline: `find_supabase_ref`; if none → `state=NOT_LINKED`. No `supabase` CLI →
  `NO_CLI` (but if a ref is derivable from config, still emit dashboard/schema URLs).
- Populates `last_migration`, `db_location`, `dashboard_url`, `schema_visualizer_url`.
- Enrich: if `SUPABASE_ACCESS_TOKEN` unset → `enrich_state=TOKEN_MISSING`,
  `enrich_hint` set. If set → GET Supabase Management API for status/region/plan/
  members/backups; 401/403 → `TOKEN_REJECTED`; timeout → `TIMEOUT`.
- **Never** returns the token; `members` carry names/roles only.

## `dashboard_vercel_service.py`

```python
def collect_vercel(project: Path) -> VercelSection: ...
```

- Baseline: `find_vercel_link`; none → `NOT_LINKED`. No `vercel` CLI → `NO_CLI`.
- Populates `project_name`, `latest_deployment_*`, `dashboard_url`.
- Enrich: `VERCEL_TOKEN` unset → `TOKEN_MISSING`; set → GET Vercel REST for team/plan/
  region/members; 401/403 → `TOKEN_REJECTED`; timeout → `TIMEOUT`.

## Orchestrator (used by the widget's workers)

```python
def build_snapshot(project: Path) -> DashboardSnapshot: ...    # calls the 4 collectors, stamps captured_at
```

- **C-S1**: `build_snapshot` never raises; a failing collector yields an `ERROR`
  section, the others still populate.
- **C-S2**: `captured_at` is provided by the caller/clock at build time (workers pass a
  timestamp; not generated inside pure model code).

## Tests (own these in `tests/unit/`)

- `parse_github_remote` over HTTPS/SSH/non-GitHub inputs.
- `collect_git` against canned `git` output via a stubbed runner (monkeypatched
  subprocess) for: normal, detached, not-a-repo, no-git.
- Each collector's `AvailabilityState` branches with the relevant CLI/token stubbed
  present/absent. **No live network** — management/REST calls are monkeypatched.
- Assert no token value appears in any returned dataclass or its `to_cacheable()`.
