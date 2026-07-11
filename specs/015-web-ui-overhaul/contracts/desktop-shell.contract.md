# Contract: Desktop Shell ↔ Backend Lifecycle

Tauri v2 shell obligations and the handshake protocol. Contract tests: `tests/contract/test_webapi_handshake_contract.py` (backend side, pytest) + Playwright/`tauri dev` smoke for shell behavior. Implements FR-001–FR-003, FR-005, FR-007, SC-009.

## Handshake file

- Written by the backend on successful bind, before serving: `<platform user-data dir>/cabal/webapi-handshake.json`
- Content: `{ "schema": "cabal-handshake.v1", "port": <int>, "token": "<random ≥256-bit>", "pid": <int>, "started_at": "<ISO-8601>" }`
- Permissions: owner-only (0600 equivalent; on Windows, user-scoped ACL). Rewritten atomically each launch; deleted on clean shutdown.
- Backend binds `127.0.0.1` on an OS-assigned ephemeral port (fixes the 8765 collision with a2a-bridge).

## Shell startup sequence

1. `single-instance` plugin guard: second launch focuses the existing window and exits (FR-003).
2. Check for a live backend: read handshake file → `GET /api/health` with token → if healthy, adopt it (do NOT spawn a duplicate — FR-002).
3. Otherwise spawn the `cabal-backend` sidecar (`bundle.externalBin`, `tauri_plugin_shell` sidecar API) with `--project <last>` and wait (bounded, with backoff) for a fresh handshake file; surface a connectivity screen meanwhile (FR-005).
4. Load the frontend with `{ port, token }` injected; webview never hardcodes a port.

## Shutdown sequence (SC-009)

1. On window close / `RunEvent::Exit`: shell calls `POST /api/system/shutdown` (authed) → backend runs `service_supervisor.shutdown_all()` for services it started, flushes SQLite, deletes handshake file, exits.
2. If the backend doesn't exit within the grace window, the shell kills the sidecar process. Adopted (not-spawned) backends are NOT killed — the shell only closes its window.
3. Orphan check on next start: stale handshake (pid dead) → file ignored and replaced.

## Window & recovery behavior

- `window-state` plugin persists size/position; last module + project persist in frontend storage (FR-007).
- Frontend detects backend loss (failed health poll / SSE heartbeat) → non-blocking "reconnecting" state → re-reads handshake on recovery; full state re-sync, no stale-as-fresh rendering (edge case: backend restarts mid-session).
- Dev mode: same contract with no shell — browser reads the handshake file via `pnpm dev` proxy config; behavior identical (FR-001).

## Contract test assertions (minimum)

1. Backend writes a schema-valid handshake atomically before first request is served; port actually bound is the port in the file.
2. Handshake file is owner-restricted; token authenticates and a wrong token is rejected.
3. `POST /api/system/shutdown` stops app-started services, persists pending job rows, removes the handshake file, and exits within the grace window.
4. Stale handshake (dead pid) is detected and replaced on next backend start.
5. Two backend starts in a row do not double-bind or corrupt the SQLite store (second either adopts-and-exits or replaces per stale rules).
