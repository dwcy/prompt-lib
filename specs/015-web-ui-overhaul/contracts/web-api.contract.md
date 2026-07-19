# Contract: Web Data API (cabal-web.v2)

Internal HTTP contract between the frontend/shell and the local backend. Contract tests: `tests/contract/test_webapi_envelope_contract.py`, `tests/contract/test_webapi_modules_contract.py`. Tests MUST be written and observed failing before router implementation (Constitution Gate 3).

## Transport & auth

- Base: `http://127.0.0.1:<ephemeral-port>` — port and bearer token come from the handshake file (see desktop-shell contract).
- Every `/api/*` request requires `Authorization: Bearer <token>`; missing/wrong token → `401` envelope. Static assets (dev only) are exempt.
- Read endpoints are `GET`. User mutations exist ONLY as `POST /api/actions/...` (see action-safety contract). The authenticated `POST /api/system/shutdown` endpoint is reserved for shell lifecycle control; any other `POST/PUT/PATCH/DELETE` → `405`.
- CORS: allowed origins are exactly the Tauri origin (`tauri://localhost` / `http://tauri.localhost`) and the Vite dev origin.

## Envelope

Every non-stream response body is a `SnapshotEnvelope` (data-model.md). Rules:

1. `schema_version` is always `"cabal-web.v2"`. Clients MUST hard-fail render (with refresh prompt) on a different major.
2. `status: error` ⇒ `data: null` and `error` populated; `status: degraded` ⇒ partial `data` plus `error`.
3. Every string in `data`/`error` has passed the shared redaction layer — clients perform NO redaction of their own.
4. Envelopes that can seed a mutation carry `precondition_digest`.
5. HTTP status mirrors envelope: 200 (ok/degraded), 401, 404 (unknown route/resource), 405, 409 (precondition drift), 410 (expired ticket), 422 (params invalid), 500 (error).

## Endpoint catalog

System
- `GET /api/health` — backend version, uptime, ModuleHealth[] for all 22 modules.
- `GET /api/diagnostics?limit&severity` — DiagnosticEvent history (persisted).
- `GET /api/jobs` / `GET /api/jobs/{id}` — Job records (all states).
- `GET /api/project` / recents; `POST /api/actions/project.select/...` switches context.

Overview & dashboard
- `GET /api/overview` — aggregated Home payload (dashboard summary, recent sessions, account, doctor, knowledge availability, security summary, drift flags).
- `GET /api/dashboard?section=git|github|supabase|vercel` — per-section, cache-first with `stale` flag.

Tools
- `GET /api/tools` — catalog metadata (no statuses), category/channel counts.
- `GET /api/tools/status` — bulk async snapshot; `GET /api/tools/{key}/status` — single probe. Every item terminates in a definitive ToolStatus.
- `GET /api/tools/{key}` — full detail incl. versions_available.

Config lifecycle
- `GET /api/config/tree?target=claude|codex` — ConfigComponent[] + DriftReport (with digest).
- `GET /api/config/diff?target&path` — unified diff, redacted.
- `GET /api/config/extras?target` · `GET /api/config/backups?kind` — CleanupExtra[], BackupSet[].
- `GET /api/settings` — SettingEntry[].
- `GET /api/local-config` — LocalConfigAction[] with previews.
- `GET /api/codex/conversion` — CodexConversionRow[].

MCP
- `GET /api/mcp` — McpServerRow[]; `GET /api/mcp/{name}/status` — single re-check.

Knowledge
- `GET /api/knowledge` — availability + counts; `GET /api/knowledge/graph` — full nodes/edges (paginated over ~2k nodes).
- `GET /api/knowledge/search?q&mode=fulltext|semantic` — ranked results; semantic returns `unavailable` status when the optional dependency is absent.
- `GET /api/knowledge/context-pack?budget=tiny|focused|full` — generated pack.
- `GET /api/knowledge/preflight` · `GET /api/knowledge/usage` — reports.

Services
- `GET /api/services` — ServiceRow[] with PrereqCheck[].
- Log streams are SSE (jobs-and-streams contract).

Package security
- `GET /api/security/scan?refresh=bool` — ScanOutcome + SecurityFinding[] (cached unless refresh).

Sessions & account
- `GET /api/sessions?project&sort&cursor` — paginated SessionRecord summaries + totals.
- `GET /api/sessions/{id}?tab=overview|activity|raw|triggers` — lazy tab payloads.
- `GET /api/account` · `GET /api/doctor` · `GET /api/models` · `GET /api/claude-info`.

Environment & identity
- `GET /api/env?scope=curated|system&q` — EnvVariableEntry[] (system scope read-only).
- `GET /api/git/identity` · `GET /api/git/policy`.

Provider & init
- `GET /api/provider` — ProviderState; `GET /api/provider/repos` — RepoListItem[].
- `GET /api/init/templates` · `GET /api/init/plan?dest&name&template` — InitWizardPlan (staged preview).

## Contract test assertions (minimum)

1. Every route above returns a valid v2 envelope; unknown route → 404 envelope.
2. Missing bearer token → 401 on every `/api/*` route.
3. Mutating verbs on read routes → 405.
4. A seeded fake-secret value (token-shaped) placed in any upstream source never appears in any response body.
5. `GET /api/tools/status` on a machine with zero probes still returns definitive states (`missing`/`error`), never `loading`.
6. Pagination: `/api/sessions` honors `cursor` and never returns an unbounded body for 1,000+ fixtures.
7. `precondition_digest` is stable for identical source state and changes when the source changes (tested via config tree fixture).
