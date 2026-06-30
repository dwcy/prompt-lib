# Quickstart: Local Agent Services in the Cabal UI

**Feature**: 014-cabal-services-view

## What this adds

A **Local Agent Services** section in the cabal TUI that shows orchestrator, a2a-bridge, and mcp-bus together — each with its description, run command, source link, and live status — and lets you set up, start, stop, and (for orchestrator) open the dashboard, without remembering CLI commands.

## Try it (maintainer flow)

1. Launch the wizard:
   ```bash
   ./run        # POSIX
   .\run.cmd    # Windows
   ```
2. From the Home screen, open **Local Agent Services**.
3. You should see three rows grouped together:
   - **a2a-bridge** — `a2a-bridge serve` — runnable, port 8765.
   - **orchestrator** — `orchestrator serve` — runnable, depends on a2a-bridge, has a dashboard.
   - **mcp-bus** — `mcp-bus` — info-only (a client-launched MCP server; no Start button).
4. If a service shows **not set up**, trigger **Setup** — cabal runs `uv tool install` from its in-repo path and the status moves to **stopped**.
5. **Start a2a-bridge** → status flips to **running**. **Stop** it → back to **stopped**.
6. **Start orchestrator** with a2a-bridge stopped → you get an actionable **blocked** message ("a2a-bridge not running"). Start a2a-bridge first, then orchestrator.
7. Try **Start a2a-bridge** with `A2A_BEARER_TOKEN` unset → **blocked** with "set A2A_BEARER_TOKEN", not a crash.
8. **Open dashboard** on orchestrator → cabal suspends and runs `orchestrator dash`; exit it to return.

## Acceptance mapping

| Spec | Verify |
|---|---|
| SC-001 | All three services visible with description, command, source, status in one place |
| SC-002 | Start runnable → running; Stop → stopped |
| SC-003 | Missing prereq → actionable message, not stale "running" |
| SC-004 | "not running" → "running" in one action once prereqs met |
| SC-005 | Kill the process externally → next refresh shows stopped |
| SC-006 | Tools & MCP screens (incl. mcp-bus in MCP group) unchanged |

## Run the tests

```bash
# from repo root
python -m pytest tests/test_service_catalog.py tests/test_service_supervisor.py \
                 tests/test_service_prereqs.py tests/test_services_screen.py -q
```

Expected: catalog validation passes; supervisor state machine (start/stop/reconcile/blocked/info-only) passes; prereq messages present; the screen mounts and renders three rows with no Start button on mcp-bus.

## Notes / boundaries

- "Run" is **session-oriented**: cabal starts/stops and tracks services for the current session; there is no auto-restart supervisor and no cross-launch PID persistence (see plan Assumptions).
- Services started by cabal are independent processes — a daemon keeps running if you exit cabal; cabal simply stops tracking it.
- mcp-bus is presented for visibility only; manage its MCP registration in the existing MCP manager.
