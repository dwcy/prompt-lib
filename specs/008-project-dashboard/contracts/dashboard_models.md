# Contract: dashboard data models

**Module**: `setup/src/cabal/models/dashboard.py`

Pure data. No I/O, no Textual, no `subprocess`. Importable with zero side effects.

## Public surface

```python
class AvailabilityState(str, Enum): ...   # ok | no_cli | not_linked | not_authed |
                                          # token_missing | token_rejected | timeout | error

@dataclass(frozen=True)
class GitRemote:        name: str; url: str; is_github: bool

@dataclass
class GitSection:
    state: AvailabilityState
    current_branch: str | None = None
    detached: bool = False
    local_branches: list[str] = field(default_factory=list)
    remotes: list[GitRemote] = field(default_factory=list)
    hint: str | None = None

@dataclass(frozen=True)
class WorkflowRun:  name: str; branch: str; status: str; conclusion: str | None; url: str; created_at: str
@dataclass(frozen=True)
class PullRequest:  number: int; title: str; author: str; url: str

@dataclass
class GitHubSection:
    state: AvailabilityState
    connected: bool = False
    owner_repo: str | None = None
    remote_used: str | None = None
    runs: list[WorkflowRun] = field(default_factory=list)
    pull_requests: list[PullRequest] = field(default_factory=list)
    hint: str | None = None

@dataclass(frozen=True)
class ProjectMember:  name: str; role: str | None = None

@dataclass
class SupabaseSection:
    state: AvailabilityState
    enrich_state: AvailabilityState = AvailabilityState.TOKEN_MISSING
    project_ref: str | None = None
    dashboard_url: str | None = None
    schema_visualizer_url: str | None = None
    db_location: str | None = None
    last_migration: str | None = None
    status: str | None = None
    region: str | None = None
    plan_name: str | None = None
    last_backup: str | None = None
    github_connected: bool | None = None
    members: list[ProjectMember] = field(default_factory=list)
    hint: str | None = None
    enrich_hint: str | None = None

@dataclass
class VercelSection:
    state: AvailabilityState
    enrich_state: AvailabilityState = AvailabilityState.TOKEN_MISSING
    project_name: str | None = None
    project_id: str | None = None
    dashboard_url: str | None = None
    latest_deployment_url: str | None = None
    latest_deployment_status: str | None = None
    team_plan: str | None = None
    region: str | None = None
    members: list[ProjectMember] = field(default_factory=list)
    hint: str | None = None
    enrich_hint: str | None = None

@dataclass
class DashboardSnapshot:
    project_path: str
    captured_at: str
    git: GitSection
    github: GitHubSection
    supabase: SupabaseSection
    vercel: VercelSection

    def to_cacheable(self) -> dict: ...   # json-safe dict, NO token fields
    @classmethod
    def from_cached(cls, data: dict) -> "DashboardSnapshot | None": ...  # tolerant of schema drift
```

## Contract guarantees

- **C-M1**: Every dataclass is constructible with only its required `state`/positional
  fields; all optional fields default. A section can always represent "empty but known
  state".
- **C-M2**: `to_cacheable()` output contains no key whose value originated from an
  access token credential — only rendered display values. `json.dumps(to_cacheable())`
  never raises.
- **C-M3**: `from_cached()` returns `None` (not a raise) on malformed/old payloads, so a
  corrupt cache degrades to a cold fetch.
- **C-M4**: Importing the module performs no I/O and pulls in no Textual/subprocess
  modules (keeps it unit-testable and cheap).

## Tests (own these in `tests/unit/`)

- Construct each section in every `AvailabilityState`; assert defaults.
- `to_cacheable()` → `json.dumps` round-trips; assert no token-named keys.
- `from_cached(None)` / `from_cached({"bogus": 1})` → `None`.
