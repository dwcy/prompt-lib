# Phase 0 Research: Cabal Web UI Overhaul

All decisions below resolve the Technical Context for `plan.md`. No NEEDS CLARIFICATION markers remain.

## R1. Desktop shell: Tauri v2 with the backend as a sidecar

- **Decision**: Wrap the web app in Tauri v2 (user-mandated: Tauri, not Electron). The Python backend ships as a PyInstaller-built binary declared in `bundle.externalBin` and spawned via `tauri_plugin_shell`'s sidecar API on startup; the shell kills it on `RunEvent::Exit`. Plugins: `shell` (sidecar), `single-instance` (FR-003), `window-state` (FR-007).
- **Rationale**: Tauri v2 is current stable; sidecars are its first-class mechanism for bundling non-Rust backends. The repo already builds a PyInstaller binary (`setup/build/cabal.spec`), so the packaging pipeline exists. Single-instance and window-state plugins directly satisfy FR-003/FR-007 without custom code.
- **Alternatives considered**: Electron (excluded by user); pywebview (Python-native but weak packaging/updater story, no capability model); Tauri with embedded Rust backend (would force rewriting the entire Cabal service layer in Rust — absurd given FR-009 mandates reusing the Python services).

## R2. Backend framework: FastAPI + uvicorn, replacing the stdlib server

- **Decision**: New backend package `setup/src/cabal/webapi/` built on FastAPI + uvicorn + pydantic v2. The 011 stdlib `http.server` backend (`cabal/web/`) is retired at the end of implementation (superseded, per spec Assumptions).
- **Rationale**: The overhaul needs streamed job output (SSE), ~60 endpoints across 22 modules, request validation, background tasks, and testability (`TestClient`). Hand-rolling that on `BaseHTTPRequestHandler` is more code and more risk than the dependency it avoids. Pydantic schemas double as the single source for envelope/contract shapes.
- **Alternatives considered**: keep stdlib (right call for 011's 6 read-only endpoints; wrong at this scale — no validation, no async streams, no DI); Flask (sync-first, SSE awkward); Django (far too heavy for a local single-user API).

## R3. Frontend stack: repo-standard React 2025 stack

- **Decision**: New app `apps/cabal-desktop/` — Vite + React + TypeScript + Zustand (client state) + TanStack Query (server state, polling, cache invalidation) + Tailwind CSS v4 + Zod (payload parsing at the boundary) + Biome. Package manager: **pnpm** (user-confirmed). TanStack Virtual for large lists (sessions, tools, log panes).
- **Rationale**: This is the house-standard stack with a dedicated specialist (`@react-architect`). 22 stateful modules with independent loading/error/stale states is exactly what TanStack Query models; vanilla JS (the 011 choice) demonstrably did not scale to this surface.
- **Alternatives considered**: keep vanilla JS (rejected — the poor current UI is the evidence); TanStack Start/Router SSR stack (no server-side rendering need in a local desktop app; plain Vite SPA suffices).

## R4. Live updates: SSE + polling, not WebSockets

- **Decision**: Server-Sent Events for unidirectional streams (job output, service logs, diagnostics feed); TanStack Query polling for cheap status refresh (service states, drift flags). No WebSockets.
- **Rationale**: Every streaming need is server→client. SSE works over plain HTTP, reconnects natively via `EventSource`, and is trivial to contract-test. WebSockets add bidirectional plumbing nothing requires.
- **Alternatives considered**: WebSockets (rejected: no client→server streaming need); long-polling everywhere (rejected: log tails would be laggy and chatty).

## R5. Jobs: in-process manager with SQLite persistence

- **Decision**: A `JobManager` in the backend owns every long-running operation (tool installs, deploys, exports, scans, clones, service setup). Each job: id, kind, state machine (`queued → running → succeeded|failed|cancelled`), ring-buffered output, exit info. Jobs and the mutation audit trail (FR-020) persist to SQLite in the platform user-data dir (`platformdirs`), so results survive navigation and backend restarts (FR-013, FR-052).
- **Rationale**: The TUI runs these as fire-and-watch subprocesses per screen; a browser needs a durable, addressable representation. SQLite is already used elsewhere in the product (OKF index, orchestrator log) — no new storage technology.
- **Alternatives considered**: in-memory only (rejected — violates FR-013 result durability and FR-052 diagnostics persistence); task queue (Celery/RQ — rejected, absurd for a single-user local app).

## R6. Action safety: prepare/execute two-phase flow with precondition digests

- **Decision**: Every mutation is a registered `ActionDescriptor`. Flow: `POST /api/actions/{action}/prepare` returns a `ConfirmationTicket` — human-readable effect (exact commands/files/scopes), backup plan, and a **precondition digest** (hash of the snapshot the preview was computed from). `POST /api/actions/{action}/execute` requires the ticket; the backend recomputes the digest and refuses with `409 state_changed` if it drifted (FR-014, SC-007). Executions create Jobs and audit rows.
- **Rationale**: Makes FR-016 structurally impossible to bypass (no execute without a prepared ticket) and gives contract tests a crisp surface. Digest-based re-verification handles the concurrent TUI/web mutation edge case without locks.
- **Alternatives considered**: client-side confirm dialogs only (rejected — a UI convention, not a guarantee); global file locks between surfaces (rejected — TUI would need changes, deadlock-prone).

## R7. Local security: loopback bind + per-launch bearer token + handshake file

- **Decision**: Backend binds `127.0.0.1` on an **ephemeral port** and writes a handshake file (port + random bearer token, owner-only permissions) to the user-data dir. The Tauri shell reads it to configure the webview; a dev browser session reads the same file. All non-static endpoints require the token; mutating endpoints additionally require the prepare/execute flow. CORS locked to the shell origin and localhost dev origin.
- **Rationale**: Satisfies FR-018 (a local process can no longer freely call mutation endpoints — it would need to read the user's own handshake file, which is the same trust boundary as the TUI). The ephemeral port permanently fixes the known 8765 collision with a2a-bridge's default port (spec edge case).
- **Alternatives considered**: fixed port, no auth (011 behavior — acceptable read-only, unacceptable once mutations exist); OS-level named-pipe transport (rejected — breaks the "reachable from local browser" requirement, FR-001).

## R8. Shared service layer: extract, don't duplicate

- **Decision**: Establish `cabal` service modules as the single shared layer both surfaces call (most already exist Textual-free: `*_service.py`, `tool_catalog`, `diff_apply`, `mcp_ops`, `local_setup`, `session_reader`, `okf/*`, `package_security/*`, `service_supervisor`, `cleanup_service`, `model_assignments`, `git_policy`, `claude_settings`, `codex_setup/*`). Where logic currently lives inside Textual screens (e.g. parts of env editing, init-project flow), it is extracted into service modules first; screens become thin callers. Redaction moves to a shared `cabal/redaction.py` consumed by the webapi serializer boundary — the frontend performs **no** redaction of its own (FR-019: one rule set; the browser only ever receives already-redacted payloads).
- **Rationale**: Directly implements FR-009/FR-010/FR-015 and the spec's parity-by-construction assumption. The 011 audit showed drift risk exactly where rules were duplicated (JS redaction regexes vs Python).
- **Alternatives considered**: webapi calls TUI screen methods (rejected — couples HTTP to Textual); duplicate logic per surface (explicitly forbidden by FR-009).

## R9. Knowledge graph visualization: d3-force + canvas

- **Decision**: Force-directed layout via `d3-force` with a custom canvas renderer inside React (pan/zoom, hover, select, filter-highlight). Node/edge counts up to a few thousand render fine on canvas; the inspector panel reads the selected node's evidence from the already-loaded bundle.
- **Rationale**: `d3-force` is small, tree-shakeable, framework-agnostic, and gives full control over the dark-theme rendering; canvas keeps 1k+ nodes at interactive framerates (SC-010).
- **Alternatives considered**: cytoscape.js (capable but a large opinionated dep with its own styling system); sigma.js (WebGL power unneeded at this scale); react-force-graph (drags in three.js).

## R10. Packaging & dev workflow

- **Decision**: Production: PyInstaller builds `cabal-backend` (new spec file alongside `setup/build/cabal.spec`); `pnpm tauri build` bundles it via `externalBin` into a Windows NSIS installer (POSIX targets best-effort). Development: `uvicorn cabal.webapi.app:create_app --reload` + `pnpm dev` (Vite) + `pnpm tauri dev`; the backend's handshake file makes browser-only dev (no Tauri) work identically.
- **Rationale**: Reuses the proven PyInstaller pipeline; keeps browser dev loop fast without the Rust toolchain in the inner loop.
- **Alternatives considered**: bundling a Python interpreter + venv into Tauri resources (fragile, huge); rewriting backend distribution as a `uv tool` prerequisite (worse first-run experience than a self-contained sidecar).

## R11. Terminal-native flows

- **Decision**: Provider device login is embedded (the existing `installers/gh.py` device flow is already programmatic: show code, open browser, poll). Assistant handoff (`claude -p` during init) and spec-workflow init stream their output into a Job pane, cancellable. `orchestrator dash` remains an explicit external-terminal handoff button (FR-044).
- **Rationale**: Matches the spec assumption that full terminal emulation is not required; each flow gets the cheapest faithful representation.
- **Alternatives considered**: embedded xterm.js terminal (heavy, and no in-scope flow actually needs keystroke-level interactivity).

## R12. Legacy web UI retirement

- **Decision**: `setup/src/cabal/web/` (011) stays untouched and runnable until the new workspace reaches module parity for its four views (Overview, Tools, Knowledge, Project Health); a final-phase task then removes the package, its launchers (`run-web-ui*`), and its tests, migrating any still-relevant test assertions to the webapi suites.
- **Rationale**: Spec assumption says superseded, not parallel-maintained; keeping it during the transition preserves a working fallback and lets contract tests be ported rather than rewritten blind.
- **Alternatives considered**: delete up front (rejected — removes the only working web surface during development); keep forever (rejected — two backends violate FR-009's no-duplication rule).
