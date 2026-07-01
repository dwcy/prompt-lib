# Research: Local Agent Services in the Cabal UI

**Feature**: 014-cabal-services-view
**Date**: 2026-06-30
**Input**: spec.md + survey of `services/*` and `setup/src/cabal/*`

This feature surfaces and controls three existing local services from the cabal TUI. There is no external protocol to conform to; all decisions are about how cabal presents and supervises locally-installed processes. Each decision below resolves an open design question raised by the spec.

---

## D1 — Presentation surface: dedicated Services screen vs. extend the Tools catalog

**Decision**: Add a **dedicated `ServicesScreen`** (`setup/src/cabal/views/services.py`), reached from a new "Local Agent Services" section on `HomeScreen`, backed by a new `service_catalog.py`. Reuse the existing presentation conventions (group panel, row layout, status Static, action Buttons, source links) so it reads as a sibling of the Tools view.

**Rationale**:
- The Tools catalog (`tool_catalog.py` / `views/tools.py`) models **install + version-probe only** — its row states are `✓ installed` / `✗ not installed` / `⬇ update available`. Services need a *lifecycle* state machine (not set up → stopped → running → error) plus start/stop actions. Overloading the install-only rows would entangle two different state models in one screen.
- A separate screen keeps FR-012 (no regression to Tools/MCP screens) trivially true — the Tools and MCP code paths are untouched.
- FR-013 (consistency) is satisfied by reusing the *presentation* idioms, not the *install-only* data model.

**Alternatives considered**:
- *Extend the Tools catalog with a "Services" category + lifecycle columns* — rejected: forces lifecycle state into `ToolDefinition`/`_probe_key`, which every other tool would have to ignore; raises regression risk on the shared `ToolsScreen`.
- *Reuse the MCP manager (`views/mcp.py`)* — rejected: that screen manages MCP-server registration, not arbitrary daemon start/stop. mcp-bus already lives there; orchestrator/a2a-bridge are not MCP servers.

---

## D2 — Process supervision model (net-new; nothing exists today)

**Decision**: A `service_supervisor.py` module owns process lifecycle. Start spawns the service via `subprocess.Popen` as an **independent/detached** process (so a daemon survives cabal exit); the supervisor tracks `{service_key: pid}` **in memory for the session**. Stop terminates the tracked process (`Popen.terminate()`, escalating to kill on timeout). Status is derived by reconciling the tracked PID's liveness with a service-appropriate probe.

**Rationale**:
- Cabal has no existing supervision primitive (confirmed: only short-lived foreground `Popen` for `claude`/`git clone`/init). This is net-new and must be self-contained.
- The spec scopes "run" to **session-oriented lifecycle** (start / status / stop), not a persistent auto-restart supervisor (Assumptions). In-memory PID tracking matches that scope and avoids a state-file/PID-registry subsystem.
- Detached start means a long-running daemon (orchestrator poller, a2a-bridge server) keeps running if the maintainer leaves cabal — the sensible default for a service, and it makes the "stop cabal while running" edge case well-defined (the process is independent; cabal simply stops *tracking* it).

**Liveness probes (D2a)**:
- **a2a-bridge** — binds a known local port (claude=8765, gemini=8766). Liveness = the tracked PID is alive **or** the port is accepting connections. The port probe lets status reconcile even for a process cabal didn't start this session.
- **orchestrator** — a poller with no port. Liveness = the tracked PID is alive (`Popen.poll() is None`), reconciled on refresh. If the PID exited, status flips to `stopped` (satisfies FR-008 — no stale "running").
- **mcp-bus** — not supervised (see D4).

**Windows note**: `Popen.terminate()` maps to `TerminateProcess` on Windows; for a clean stop of a child that spawns its own children, use `CREATE_NEW_PROCESS_GROUP` at spawn and escalate `terminate()`→`kill()` after a short grace period. No POSIX-only signals.

**Alternatives considered**:
- *Persist PIDs to a state file for cross-launch ownership* — rejected for this iteration (out of scope per Assumptions; adds a registry to maintain).
- *Run services as foreground workers inside the Textual event loop* — rejected: blocks the UI and dies with the screen; daemons must outlive a screen.

---

## D3 — Prerequisite detection and actionable start failures (FR-007)

**Decision**: A `service_prereqs.py` module exposes a per-service `check(key) -> list[PrereqResult]`. The supervisor calls it **before** starting; if any required prereq is unmet, it does not spawn and returns an actionable message. Probes reuse existing cabal/service mechanics rather than re-implementing them.

**Per-service prerequisites (from the CLI survey)**:
- **a2a-bridge serve** — requires `A2A_BEARER_TOKEN` in the environment and a target agent (`claude`/`gemini`); binds a port. Missing token → exit 2 today, so cabal pre-checks the env var and surfaces "set A2A_BEARER_TOKEN" instead of letting it crash.
- **orchestrator serve** — runs pre-flight checks itself (gh auth, A2A peer agent-card reachable, ntfy health) with deterministic exit codes (2 config / 3 gh / 4 a2a peer). Cabal surfaces these as named prerequisites and, on a non-zero exit, maps the code to a readable cause. Crucially, **orchestrator depends on a2a-bridge being reachable** (FR-004) — the prereq check reports "a2a-bridge not running" when the peer is down.
- **set-up state** — a service is "not set up" when its console command is not resolvable (`shutil.which` / not installed). Setup is offered before run.

**Rationale**: Honors FR-007 (no silent failure) by checking before spawning and by mapping the services' own deterministic exit codes to human messages. Keeps prereq logic out of the view (python.md: side-effecting I/O separate from UI).

---

## D4 — mcp-bus is presented but not start/stop-controlled (FR-011)

> **Update 2026-06-30**: Superseded — mcp-bus is **removed from the Local Agent Services view** entirely (it is already in the Tools **MCP** group, so showing it twice was redundant). The original decision below is kept as design record. The `runnable`/`INFO_ONLY` machinery remains in the supervisor as a general capability.

**Decision**: mcp-bus appears in the Services screen as an **info/visibility row** (description, command, source, availability status) with **no start/stop control**. Its existing place in the Tools **MCP** group (`tool_catalog.py:222`) and its installer (`installers/mcp_bus.py`) are left untouched.

**Rationale**: mcp-bus is a **stdio MCP server** (`mcp.run(transport="stdio")`, no port, no subcommands) launched on demand by its MCP clients (Claude Code), not a standalone daemon. A "start" button would spawn an orphan stdio server with no client attached — misleading. Availability status = installed/resolvable (reuse `mcp_bus_status()` semantics, adjusted since the entry point has no `--version`: detect via `shutil.which("mcp-bus")`). This satisfies FR-011 and the spec's explicit carve-out.

**Note**: `installers/mcp_bus.py` currently calls `mcp-bus --version`, which the entry point does not implement. The Services status probe must not depend on `--version`; it uses presence (`which`) only. (Fixing the installer's version call is optional cleanup, not required by this feature.)

---

## D5 — Setup/installation of a service from cabal (FR-009)

**Decision**: Each runnable service gets a small installer (`installers/orchestrator.py`, `installers/a2a_bridge.py`) modeled on `installers/mcp_bus.py`: `uv tool install`/`upgrade` from the in-repo location (`REPO_DIR/services/<name>`), with a git-subdirectory fallback. orchestrator's installer must ensure its `a2a-bridge` path dependency is satisfied (it declares a2a-bridge as an editable dep).

**Rationale**: Reuses the established managed-tool install pattern (uv tool, local-checkout-first) for consistency and reversibility. Surfaces a clear message when `uv` is missing (same auto-provision/actionable-message contract as other tools, FR-004 analogue).

**Alternatives considered**:
- *Per-service `.venv` activation* — rejected: the services already ship `.venv`s for dev, but a cabal-managed install should expose a console command on PATH like every other managed tool; `uv tool` does exactly that.

---

## D6 — Reaching a service's native dashboard / logs (FR-010)

**Decision**:
- **orchestrator** ships `orchestrator dash` (its own Textual TUI tailing the SQLite event log). Because nesting a second Textual app inside cabal's event loop is fragile, cabal launches `orchestrator dash` by **suspending the cabal app** (`App.suspend()`) and running the dashboard in the foreground, returning to cabal on exit — or, on platforms where that is unreliable, spawns it in a new console window. The plan picks `App.suspend()` as primary.
- **a2a-bridge** has no dashboard; its observability is satisfied by surfacing where its activity/log is (server stdout / known log path).
- **orchestrator** also exposes recent activity via its SQLite event log; cabal can surface the log location / last-N events as a read-only pointer.

**Rationale**: `App.suspend()` is the supported Textual mechanism for handing the terminal to a child full-screen program and is far safer than mounting a nested app. a2a-bridge's lack of a dashboard is handled by the log-pointer branch of FR-010.

---

## D7 — Module decomposition (python.md size discipline)

**Decision**: Split by responsibility so no file mixes UI with side-effecting I/O:
- `service_catalog.py` — `ServiceDefinition` dataclass, `SERVICE_DEFINITIONS`, `ServiceStatus`/`ServiceState` enums, lookups. (library module, data only)
- `service_supervisor.py` — start/stop/reconcile + PID tracking (subprocess I/O).
- `service_prereqs.py` — per-service prerequisite probes (env/port/process/which).
- `installers/orchestrator.py`, `installers/a2a_bridge.py` — uv tool install/upgrade.
- `views/services.py` — `ServicesScreen` (compose + event handlers; delegates all I/O to supervisor/prereqs/installers).
- wiring: `views/home.py` (new section + button), screen registration.

**Rationale**: Directly applies python.md split patterns (service module for subprocess; view + worker separation) and keeps every file under its soft cap with one clear responsibility.

---

## Resolved unknowns

| Spec area | Resolution |
|---|---|
| Meaning of "run" | Session-oriented start/stop + live status (D2); not auto-restart supervisor |
| Where it lives in cabal | New `ServicesScreen` off Home (D1) |
| How status is computed | PID liveness + port/which probe, reconciled on refresh (D2a, FR-008) |
| Prereq handling | Pre-start check, map service exit codes to messages (D3) |
| mcp-bus control | Info-only, no start/stop (D4) |
| Setup mechanism | `uv tool install` from in-repo path (D5) |
| Dashboard access | `App.suspend()` → `orchestrator dash`; log pointer for a2a-bridge (D6) |
| File layout | 6 focused modules + home wiring (D7) |

All `NEEDS CLARIFICATION` from Technical Context are resolved; no blocking unknowns remain.
