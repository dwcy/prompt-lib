# Cabal Desktop Parity Record

**Feature**: 015-web-ui-overhaul
**Last updated**: 2026-07-19
**Status**: Complete — module parity, safety, performance, regression, and Windows packaging verified

## Evidence

- The frontend registry exposes all 22 required modules with concrete components, grouped navigation, and a searchable keyboard-navigable workspace map.
- The fixture-backed Playwright smoke passes across all 22 modules, including a guarded prepare/execute action, the 390 x 844 responsive frame, and backend disconnect/reconnect signaling.
- The production frontend build completes with module-level lazy loading; the initial application chunk is 240.58 kB (74.50 kB gzip).
- The packaged backend sidecar starts, writes a `cabal-handshake.v1` handshake, reports healthy state for all 22 modules, and shuts down cleanly.
- Browser-mode development starts at `http://localhost:5173/` with Vite hot reload and the authenticated backend proxy.
- `pnpm tauri dev --no-watch` compiled and launched `target/debug/cabal-desktop.exe` against the configured Vite URL, and its verification process tree was shut down cleanly.
- The Windows production build created `Cabal_0.1.0_x64-setup.exe` through the configured NSIS bundle path with the rebuilt 20.0 MiB backend sidecar.
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

## Safety Verification

- Stale precondition digests are rejected by the config integration tests before a deploy can execute.
- Security-fix integration coverage asserts that the reviewed preview command is byte-for-byte identical to the command handed to execution, with the action flowing through the shared audit/job path.
- Redaction contracts cover API envelopes and job streams. The verification pass also found and fixed over-redaction of numeric metrics such as `tokens_in`, `input_tokens`, and `token_count`, while retaining suffix-based credential redaction.
- Destructive action contracts remain prepare-first, digest-bound, and fail closed when preview validation fails.

## Performance Results

Measured by `tests/e2e/performance.e2e.ts` on Windows with Chromium and the real fixture backend:

| Budget | Requirement | Measured | Result |
|--------|-------------|----------|--------|
| Backend warm start | < 3,000 ms | 940.7 ms | Pass |
| 1,000-session interaction | < 200 ms | 30.3 ms | Pass |
| 1,000-node graph interaction | < 200 ms | 18.9 ms | Pass |

## Regression Results

- `uv run pytest`: 1,375 passed, including contract, unit, integration, hooks, and the existing TUI suite.
- `pnpm test`: 51 passed across 17 Vitest files.
- `pnpm test:e2e`: 2 passed, covering the performance fixture and the complete 22-module workspace smoke.
- `pnpm run build`: production TypeScript and Vite build passed.
- Backend sidecar and `pnpm tauri build`: passed; Windows NSIS installer produced.

The in-app interactive browser was unavailable in this environment, so the browser surface was verified through the repository's Chromium Playwright suite and HTTP-backed development flow. The native Tauri development executable itself was launched and its packaging path was independently built.
