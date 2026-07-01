# Internal Interface Contracts: Local Agent Services in the Cabal UI

**Feature**: 014-cabal-services-view
**Date**: 2026-06-30

This feature exposes **no external/wire protocol** — it surfaces and supervises existing local processes from a TUI. Per Constitution Gate 1/Gate 3, there is **no protocol surface requiring conformance or contract tests**. The "contracts" below are the in-process Python module boundaries the rest of the feature (and its unit tests) depend on. They are stable signatures, not HTTP/JSON-RPC schemas.

---

## C1 — `cabal.service_catalog`

```python
SERVICE_DEFINITIONS: tuple[ServiceDefinition, ...]      # exactly the 3 services
SERVICE_BY_KEY: dict[str, ServiceDefinition]

def all_services() -> tuple[ServiceDefinition, ...]: ...
def get_service(key: str) -> ServiceDefinition: ...      # KeyError if unknown
def validate_catalog() -> None: ...                      # raises on invalid seed (see data-model validation rules)
```

**Guarantees**:
- `validate_catalog()` enforces every data-model validation rule; called at import or by a unit test.
- `mcp-bus` has `runnable is False`, `dashboard_command is None`.
- `orchestrator.depends_on == ("a2a-bridge",)`.

## C2 — `cabal.service_prereqs`

```python
def check(key: str) -> list[PrereqResult]: ...
def is_set_up(key: str) -> bool: ...     # console_name resolvable on PATH
```

**Guarantees**:
- `check` returns one `PrereqResult` per required prerequisite for the service; an empty list means "no prerequisites".
- Every `PrereqResult` with `ok is False` carries a non-empty actionable `message` (FR-007).
- `check` performs **no mutation** and never starts a process.

## C3 — `cabal.service_supervisor`

```python
def status(key: str) -> ServiceState: ...                 # reconciled (FR-008)
def statuses() -> dict[str, ServiceState]: ...
def start(key: str) -> ServiceState: ...                  # prereqs checked first (FR-005/FR-007)
def stop(key: str) -> ServiceState: ...                   # only stops what cabal started (FR-006)
def reconcile(key: str) -> ServiceState: ...
```

**State-machine guarantees** (assert in unit tests):
- `start` on a service whose prereqs fail does **not** spawn a process and returns `status == BLOCKED` with `detail` = joined prereq messages.
- `start` on a not-set-up service returns `NOT_SET_UP` (caller must `setup` first).
- After `start` succeeds, `status(key).status == RUNNING` and `started_by_cabal is True`.
- After the underlying process exits, the next `status`/`reconcile` returns `STOPPED` (no stale `RUNNING`).
- `stop` on a non-running or not-cabal-started service is a no-op that returns the current reconciled state (never raises).
- `start`/`stop`/`status` on `mcp-bus` (info-only) return `INFO_ONLY` and never spawn/kill (FR-011).

## C4 — `cabal.installers.orchestrator` / `cabal.installers.a2a_bridge`

```python
def <svc>_install() -> tuple[bool, str]: ...   # (ok, message) — uv tool install/upgrade from in-repo path
def <svc>_status() -> tuple[bool, str]: ...    # (set_up, version-or-detail) via PATH presence
```

**Guarantees**: same `(bool, str)` shape as existing installers (`installers/mcp_bus.py`); a missing `uv` prerequisite yields `(False, <actionable message>)` (FR-009).

## C5 — `cabal.views.services.ServicesScreen` (UI contract)

A Textual `Screen` reached from `HomeScreen`. Contract for the maintainer:

- Renders the three services in one group, each row showing label, description, `run_command`, source link, and current status (FR-001/002/003).
- orchestrator's row shows its dependency on a2a-bridge (FR-004).
- Runnable rows expose **Start**/**Stop**, a **Setup** action when `NOT_SET_UP`, and **Open dashboard** when `dashboard_command` is set (FR-005/006/009/010).
- mcp-bus row is info-only — no Start/Stop (FR-011).
- All process I/O is delegated to `service_supervisor` / `service_prereqs` / installers — the screen performs no `subprocess` calls directly (python.md UI/IO separation).
- A mount-and-render smoke test (`App.run_test()` + `pilot.pause()`) exists per python.md Textual rules.

---

## Test obligations (owned by `@python-tester`)

These are **unit/integration tests**, not protocol contract tests (no wire surface exists):

1. `test_service_catalog.py` — `validate_catalog()` passes; seed invariants (C1 guarantees).
2. `test_service_supervisor.py` — drive the C3 state machine using a dummy long-running child process (e.g. a short Python sleeper): start→RUNNING, stop→STOPPED, external-exit→reconcile→STOPPED, prereq-fail→BLOCKED (no spawn), mcp-bus→INFO_ONLY.
3. `test_service_prereqs.py` — missing `A2A_BEARER_TOKEN` → `ok is False` with message; set → ok.
4. `test_services_screen.py` — Textual smoke test: screen mounts, renders three rows, mcp-bus row has no Start button.
