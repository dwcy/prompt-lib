# Cabal Desktop Parity Record

**Feature**: 015-web-ui-overhaul
**Last updated**: 2026-07-13
**Status**: Implementation walkthrough and browser smoke complete; interactive safety and performance checks deferred

## Evidence

- The frontend registry exposes all 22 required modules with concrete components, grouped navigation, and a searchable keyboard-navigable workspace map.
- The fixture-backed Playwright smoke passes across all 22 modules, including a guarded prepare/execute action, the 390 x 844 responsive frame, and backend disconnect/reconnect signaling.
- The production frontend build completes, with the initial application chunk reduced to about 223 kB through module-level lazy loading.
- The packaged backend sidecar starts, writes a `cabal-handshake.v1` handshake, reports healthy state for all 22 modules, and shuts down cleanly.
- Browser-mode development is live at `http://localhost:5173/` with Vite hot reload and the authenticated backend proxy.
- The retired read-only implementation, launchers, tests, PyInstaller entries, and README references have been removed.

## Module Walkthrough

| # | Module | Implementation evidence | Source walkthrough |
|---|--------|-------------------------|--------------------|
| 1 | Project Gate & Switcher | Recents, folder entry, clone, and new-project routes | Complete |
| 2 | Home Overview | Aggregated operational summary and module links | Complete |
| 3 | Project Dashboard | Git and provider status grouped by source | Complete |
| 4 | Tools Catalog | Search, live filters, detail, version choice, guarded actions | Complete |
| 5 | Global Config Deployment | Target switch, component tree, diffs, extras, guarded apply | Complete |
| 6 | Cleanup & Restore | Grouped cleanup candidates and backup timeline | Complete |
| 7 | Settings Configurator | Inheritance and local override controls | Complete |
| 8 | MCP Connectors | Scope matrix, recheck, activation, and scoped disable | Complete |
| 9 | Local Project Config | Blueprint-style grouped preview and apply flows | Complete |
| 10 | Knowledge & Retrieval | Graph, search, packs, reports, export, doctor, and index | Complete |
| 11 | Agent Services | Readiness, lifecycle controls, logs, and dashboard handoff | Complete |
| 12 | Package Security | Severity findings, scan, and exact-command fix confirmation | Complete |
| 13 | Sessions Dashboard | Totals, hierarchy, activity groups, tabs, and delete flow | Complete |
| 14 | Account & Assistant Info | Credential chain, instruction order, and runtime provenance | Complete |
| 15 | Config Doctor | Triage findings, routes, and rescan | Complete |
| 16 | Model Assignments | Routing topology, filtering, and validated reassignment | Complete |
| 17 | Environment Variables | Curated editor and searchable redacted system snapshot | Complete |
| 18 | Git Identity & Commit Policy | Scoped identity and validated policy editor | Complete |
| 19 | Provider Repos & Clone | Device flow, accounts, repo search, clone, switch, forget | Complete |
| 20 | New Project Wizard | Assembly runway, staged files, MCP editing, and handoff job | Complete |
| 21 | Codex Parity | Deployment, scaffold blueprint, and conversion audit | Complete |
| 22 | Diagnostics & Backend Health | Signal summary, source health, audit history, and live tail | Complete |

## Pending Verification

The following checks belong to the separately deferred verification step and are not recorded as passing:

- T098 manual stale-digest refusal, exact-command confirmation/audit, and seeded-token redaction checks.
- T099 measured warm-start and 1,000-row/1,000-node interaction budgets.
- T102 full backend, frontend, end-to-end, and existing TUI test suites.
- T104 interactive Tauri development-shell walkthrough.

The production Tauri bundle and sidecar packaging path have been built successfully; this does not replace the pending interactive and automated checks above.
