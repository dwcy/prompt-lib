# Data Model: Cabal Web UI Overhaul

Entities the backend exposes and the frontend consumes. Persistence column: `derived` = computed from existing sources on request; `sqlite` = persisted in the new jobs/audit database; `file` = existing on-disk source of truth.

## Cross-cutting envelope types

### SnapshotEnvelope (v2) — `derived`
Wrapper for every non-stream response.

| Field | Type | Notes |
|---|---|---|
| schema_version | string | `"cabal-web.v2"`; frontend refuses unknown majors (FR-011) |
| captured_at | ISO-8601 string | snapshot time |
| status | `ok \| degraded \| error` | module-level health of this payload |
| source | string | data-source identifier (e.g. `tool_catalog`, `okf_bundle`) |
| stale | bool | true when served from cache past freshness window |
| precondition_digest | string \| null | present on snapshots that can seed a mutation (FR-014) |
| data | object \| null | payload |
| error | DiagnosticEvent \| null | populated when status ≠ ok |

### ModuleHealth — `derived`
| Field | Type |
|---|---|
| module | string (one of the 22 module keys) |
| state | `ok \| loading \| degraded \| failed \| unavailable` |
| detail | string (redacted) |
| last_success_at | ISO-8601 \| null |

### DiagnosticEvent — `sqlite` (history) + in-memory feed
| Field | Type | Notes |
|---|---|---|
| id | int | autoincrement |
| severity | `info \| warning \| error` | |
| module | string | affected module key |
| message | string | redacted before persist |
| occurred_at | ISO-8601 | |
| kind | `data_source \| mutation \| backend` | mutation entries mirror AuditEntry (FR-020, FR-052) |

## Safety & execution

### ActionDescriptor — static registry (code)
| Field | Type | Notes |
|---|---|---|
| action_id | string | e.g. `tools.install`, `config.apply`, `sessions.delete` |
| module | string | owning module |
| destructive | bool | drives extra confirmation copy (FR-017) |
| backup_policy | string \| null | named policy when a pre-action backup is taken |
| params_schema | JSON schema | validated at prepare time |

### ConfirmationTicket — `sqlite`, TTL
| Field | Type | Notes |
|---|---|---|
| ticket_id | uuid | single-use |
| action_id | string | FK → ActionDescriptor |
| params | object | validated, frozen at prepare |
| effect_preview | EffectPreview | what the user confirms |
| precondition_digest | string | recomputed at execute; mismatch → 409 (FR-014) |
| created_at / expires_at | ISO-8601 | short TTL; expired tickets are refused |
| state | `pending \| executed \| expired \| invalidated` | state machine below |

**EffectPreview**: `{ summary: string, commands: string[], files_changed: string[], scopes: string[], backup: string | null, removals: string[] }` — every field redacted (FR-016/017).

**Ticket state machine**: `pending → executed` (on execute) · `pending → expired` (TTL) · `pending → invalidated` (digest drift detected at execute). No other transitions; executed/expired/invalidated are terminal.

### Job — `sqlite` + in-memory ring buffer
| Field | Type | Notes |
|---|---|---|
| job_id | uuid | |
| kind | string | action_id or read-side long op (e.g. `knowledge.export`) |
| ticket_id | uuid \| null | null for non-mutating jobs |
| state | `queued \| running \| succeeded \| failed \| cancelled` | FR-013 |
| output_tail | string[] | last N lines persisted; full stream via SSE while live |
| exit_detail | string \| null | redacted failure reason |
| created_at / started_at / finished_at | ISO-8601 | |

**Job state machine**: `queued → running → succeeded | failed` · `queued|running → cancelled` (explicit only). Terminal states persist with output tail (survives navigation and backend restart).

### AuditEntry — `sqlite` (FR-020)
| Field | Type |
|---|---|
| id, action_id, ticket_id, job_id | ids |
| effect_summary | string (redacted) |
| outcome | `succeeded \| failed \| cancelled` |
| performed_at | ISO-8601 |

## Context & module payloads

### ProjectContext — `file` (recents store) + session state
`{ path, name, is_git_repo, recents: RecentProject[], selected_at }` — switching context invalidates all project-scoped module caches (FR-022).

### ToolCatalogItem — `derived` (tool_catalog + probes)
`{ key, label, category, description, source_url, source_state, install_channel, platforms, badges, safety_notes, backup_policy, versions_available[], status: ToolStatus }` where **ToolStatus** = `{ state: installed | update_available | missing | unsupported | manual_required | error, current_version, latest_version, checked_at }`. Statuses stream in per-tool after catalog metadata (FR-025); never a terminal `loading`.

### ConfigComponent / DriftReport — `derived` (diff_apply, codex_setup.diff_apply)
`ConfigComponent { key, group, files: ConfigFile[] }`; `ConfigFile { rel_path, state: new | changed | unchanged | extra, diff_available }`; `DriftReport { target: claude | codex, changed_count, new_count, extras_count, computed_at, digest }` — digest doubles as the deploy action's precondition (FR-008, FR-030).

### CleanupExtra / BackupSet — `derived` + `file`
`CleanupExtra { rel_path, component, classification: stale | unknown }`; `BackupSet { id, kind: cleanup | settings | pre_action, created_at, files_count, restorable }` (FR-031–033).

### SettingEntry — `derived` (claude_settings)
`{ key, description, source: global | local_override | unset, value_state, target_file }` (FR-034).

### McpServerRow — `derived` (mcp_ops)
`{ name, scopes[], status: connected | error | pending | inactive, env_present, command, actions_available[] }` (FR-037/038).

### LocalConfigAction — `derived` (local_setup)
`{ key, label, applicable, preview_items: PreviewItem[], applied_state }`; `PreviewItem { rel_path, state: new | changed | skip, selected }` (FR-035).

### KnowledgeGraphSnapshot — `file` (OKF bundle) + `derived` indexes
`{ available, exported_at, counts { nodes, edges, by_type, by_relation }, nodes: Node[], edges: Edge[] }`; `Node { id, type, label, evidence[], source_refs[] }`; `Edge { from, to, relation }`. Search/semantic/context-pack/preflight/usage results are request-scoped payloads defined in the web-api contract (FR-039–041).

### ServiceRow — `derived` (service_catalog + supervisor)
`{ key, label, state: running | stopped | not_set_up | blocked | info_only, prereqs: PrereqCheck[], pid, started_by_app, log_stream_available, dashboard_handoff }` ; `PrereqCheck { key, ok, message }` (FR-042–044).

### SecurityFinding — `derived` (package_security)
`{ ecosystem, package, kind: vulnerable | outdated | deprecated, severity, current, target, fix_available, fix_command_preview }` + `ScanOutcome { scanned_at, notices[], cached }` (FR-045/046).

### SessionRecord — `file` (transcripts) parsed via session_reader
`{ session_id, project, branch, started_at, duration, parent_id, cost, tokens_in, tokens_out, models: ModelUsage[], activity { skills[], agents[], tool_counts, hook_events }, has_raw_log, triggers[] }` — list endpoint paginates; detail endpoint loads tabs lazily (SC-010, FR-047).

### ModelAssignment — `file` (repo global/ + deployed target)
`{ asset_kind: agent | skill, asset_name, pinned_model, assignable_models[], repo_and_target_in_sync }` (FR-051).

### EnvVariableEntry — `derived` (curated set) / read-only snapshot (system)
`{ name, value_redacted, is_path, source, editable }` (FR-053).

### GitIdentity / CommitPolicy — `file` (gitconfig, git-policy.json)
`GitIdentity { scope: global | local, name, email }`; `CommitPolicy { agent_name, agent_email, allowed_types[], refuse_on_branches[], tag_rules }` (FR-054).

### ProviderState / RepoListItem / CloneRequest — `derived` (gh)
`ProviderState { authenticated, accounts[], active_account }`; `RepoListItem { name, owner, visibility, updated_at }`; device-login flow state machine: `idle → code_issued → polling → authenticated | expired` (FR-055).

### InitWizardPlan — `derived` (init_project_service, gh_templates)
`{ destination, name_valid, template_source: hosted | local, staged_files: PreviewItem[], mcp_config, handoff_prompt_present }` — apply creates a Job (FR-056).

### CodexConversionRow — `derived` (codex_setup.conversion)
`{ asset, state: converted | not_converted | codex_only | stale | unsupported, source_path, output_path }` (FR-036).

## Relationships

- ActionDescriptor 1—N ConfirmationTicket 1—0..1 Job 1—0..1 AuditEntry; AuditEntry rows also surface as DiagnosticEvent(kind=mutation).
- SnapshotEnvelope.precondition_digest links a read snapshot to the ticket that may be prepared from it (same digest namespace as DriftReport.digest and other mutation seeds).
- ProjectContext scopes: Project Dashboard, Sessions (per-project panel), Local Config, Settings (local overrides), Package Security, Init/Provider destination defaults; global modules (Tools, MCP user scope, Config Deployment, Knowledge, Services, Environment) ignore it.
- ModuleHealth aggregates into the shell's connectivity/status strip; every router contributes one row (FR-005, FR-012).
