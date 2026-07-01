# Data Model: Local Agent Services in the Cabal UI

**Feature**: 014-cabal-services-view
**Date**: 2026-06-30

All entities are in-process Python structures (no database). The "model" is the service registry plus the runtime lifecycle state the supervisor tracks. Mirrors the spec's Key Entities.

---

## Enums

### `ServiceStatus` (`Literal` / `enum.Enum`)

The state a service is shown in. Reconciled on every refresh (FR-008).

| Value | Meaning | Applies to |
|---|---|---|
| `NOT_SET_UP` | Console command not resolvable / not installed | all |
| `STOPPED` | Set up, not currently running | runnable (orchestrator, a2a-bridge) |
| `RUNNING` | Process alive (PID live and/or port open) | runnable |
| `BLOCKED` | Cannot start — a required prerequisite is unmet | runnable |
| `INFO_ONLY` | Presented for visibility; no lifecycle control | info-only services (none currently registered) |

State transitions (runnable services):

```
NOT_SET_UP --(prepare/setup ok)--> STOPPED
STOPPED   --(start, prereqs ok)--> RUNNING
STOPPED   --(start, prereq fail)--> BLOCKED
BLOCKED   --(prereq resolved + start)--> RUNNING
RUNNING   --(stop)--> STOPPED
RUNNING   --(process exits/killed externally; reconcile)--> STOPPED
```

`INFO_ONLY` has no transitions (mcp-bus).

### `InstallKind`

`UV_TOOL` (orchestrator, a2a-bridge) — install via `uv tool install` from the in-repo path.

---

## Entities

### `ServiceDefinition` (frozen dataclass) — the catalog record

| Field | Type | Notes |
|---|---|---|
| `key` | `str` | Stable id: `orchestrator` / `a2a-bridge` |
| `label` | `str` | Display name |
| `description` | `str` | One-line "what it does" (FR-002) |
| `run_command` | `str` | Human-facing command, e.g. `orchestrator serve` (FR-002) |
| `source_url` | `str` | Link to the in-repo source (FR-002) |
| `runnable` | `bool` | True for orchestrator/a2a-bridge; False for mcp-bus (FR-011) |
| `depends_on` | `tuple[str, ...]` | Other service keys this needs running, e.g. orchestrator → `("a2a-bridge",)` (FR-004) |
| `install_path` | `str` | In-repo dir for `uv tool install`, e.g. `services/orchestrator` (FR-009) |
| `console_name` | `str` | Executable name on PATH for set-up/status probe (`orchestrator`, `a2a-bridge`) |
| `prereq_keys` | `tuple[str, ...]` | Names of required prerequisites the prereq module checks (e.g. `A2A_BEARER_TOKEN`, `gh-auth`, `ntfy`, `a2a-peer`) |
| `dashboard_command` | `str \| None` | e.g. `orchestrator dash`; `None` when no native dashboard (FR-010) |
| `log_hint` | `str \| None` | Where to observe recent activity when no dashboard (a2a-bridge) (FR-010) |
| `default_port` | `int \| None` | a2a-bridge claude=8765; used for liveness probe (D2a) |

**Validation rules**:
- `key`, `label`, `description`, `run_command`, `source_url`, `console_name`, `install_path` are non-empty.
- `runnable == False` ⇒ `dashboard_command is None` and the service is never given start/stop (mcp-bus).
- Every key in `depends_on` MUST itself be a defined service key.
- `SERVICE_DEFINITIONS` contains exactly the three services; lookup map `SERVICE_BY_KEY` is keyed by `key`.

### `ServiceState` (runtime, not persisted) — what the supervisor holds

| Field | Type | Notes |
|---|---|---|
| `key` | `str` | FK → `ServiceDefinition.key` |
| `status` | `ServiceStatus` | Current reconciled status |
| `pid` | `int \| None` | PID of the process cabal started this session, if any |
| `started_by_cabal` | `bool` | True only if this session spawned it |
| `detail` | `str` | Human note: version, port, or the blocked reason |

Held in an in-memory `dict[str, ServiceState]` for the cabal session (no cross-launch persistence — see research D2).

### `PrereqResult` — one prerequisite check outcome

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | e.g. `A2A_BEARER_TOKEN`, `gh-auth`, `a2a-peer` |
| `ok` | `bool` | Whether it is satisfied |
| `message` | `str` | Actionable text when `ok is False` (FR-007) |

`check(key) -> list[PrereqResult]`; the supervisor refuses to start when any `ok is False` and surfaces the joined messages → status `BLOCKED`.

### `LifecycleAction` (conceptual; realized as supervisor/installer functions)

| Action | Precondition | Effect |
|---|---|---|
| `setup(key)` | `NOT_SET_UP` | `uv tool install` from `install_path`; on success → `STOPPED` (FR-009) |
| `start(key)` | `STOPPED`/`BLOCKED`, prereqs ok | spawn detached; track pid; → `RUNNING` (FR-005) |
| `stop(key)` | `RUNNING` & `started_by_cabal` | terminate tracked pid; → `STOPPED` (FR-006) |
| `reconcile(key)` | any | re-probe liveness; correct stale `RUNNING` → `STOPPED` (FR-008) |
| `open_dashboard(key)` | `dashboard_command is not None` | `App.suspend()` → run dashboard (FR-010) |

---

## Relationships

```
ServiceDefinition 1 ──< ServiceState (0..1 per session)
ServiceDefinition.depends_on ──> ServiceDefinition.key   (orchestrator → a2a-bridge)
ServiceDefinition 1 ──< PrereqResult (0..n, computed per check)
```

## Seed data (the three services)

| key | runnable | depends_on | console | dashboard | port | prereqs |
|---|---|---|---|---|---|---|
| `a2a-bridge` | yes | — | `a2a-bridge` | — (log hint) | 8765 | `A2A_BEARER_TOKEN`, agent target |
| `orchestrator` | yes | `a2a-bridge` | `orchestrator` | `orchestrator dash` | — | `gh-auth`, `ntfy`, `a2a-peer`, config |
