# Contract: Action Safety (prepare/execute)

The ONLY path to any mutation. Contract tests: `tests/contract/test_webapi_action_safety_contract.py` — written first, observed failing (Gate 3). Implements FR-014, FR-016–FR-020.

## Protocol

### 1. Prepare

`POST /api/actions/{action_id}/prepare` with JSON params (validated against the descriptor's `params_schema`; invalid → `422`).

Response: envelope whose `data` is a `ConfirmationTicket`:

```json
{
  "ticket_id": "…",
  "action_id": "config.apply",
  "effect_preview": {
    "summary": "Deploy 3 changed files to ~/.claude",
    "commands": [],
    "files_changed": ["agents/foo.md", "settings.json", "…"],
    "scopes": ["claude"],
    "backup": "settings-backup",
    "removals": []
  },
  "precondition_digest": "sha256:…",
  "expires_at": "…"
}
```

Rules: preview MUST name exact commands/files/scopes (FR-016); destructive actions MUST populate `removals` and `backup` (FR-017); all strings redacted.

### 2. Execute

`POST /api/actions/{action_id}/execute` with `{ "ticket_id": "…" }`.

- Backend recomputes the precondition digest from live state. Mismatch → `409 state_changed`, ticket → `invalidated`, and the response includes a fresh snapshot reference so the client re-renders the preview (FR-014, SC-007).
- Expired ticket → `410 ticket_expired`. Unknown/reused ticket → `404` / `409 ticket_consumed` (single use).
- Success → `202` with `{ "job_id": … }` (long-running) or `200` with result envelope (instant mutations like a settings toggle). Either way an AuditEntry is written (FR-020).

### 3. No other write path

- Registry is closed: an `action_id` not in the registry → `404`. Contract test enumerates the registry and asserts every mutating capability in the spec's module table maps to a descriptor (parity guard).
- No read endpoint may mutate state (contract test: fixture-instrumented services record zero writes across full GET sweep).
- `POST /api/system/shutdown` is the sole control-plane exception. It is authenticated, used only by the desktop shell, and may stop app-owned processes and remove the ephemeral handshake; it does not expose a user feature mutation.

## Registered actions (initial registry)

`project.select` · `tools.install` · `tools.update` · `config.apply` · `config.cleanup` · `config.restore_cleanup` · `config.restore_settings` · `settings.toggle` · `settings.reset_local` · `mcp.activate_global` · `mcp.activate_local` · `mcp.approve` · `mcp.disable` · `local_config.apply_group` · `knowledge.export` · `knowledge.index` · `services.setup` · `services.start` · `services.stop` · `security.apply_fix` · `sessions.delete` · `models.assign` · `env.apply` · `git.identity.set` · `git.policy.set` · `provider.login` · `provider.clone` · `init.apply` · `codex.apply` · `codex.local_apply` · `jobs.cancel`

(Descriptor list is the parity contract for mutations; adding a module mutation without a descriptor is a contract violation.)

## Redaction guarantee

- One shared rule set (`cabal/redaction.py`) applied at the serializer boundary for: envelopes, SSE events, persisted job tails, audit entries, effect previews.
- Frontend performs no redaction (nothing unredacted ever reaches it) — the 011 duplicated-regex pattern is explicitly retired.
- Rule set covers at minimum: known token prefixes, `Bearer …`, `*_TOKEN/SECRET/PASSWORD/API_KEY=` assignments, URL credentials/query secrets, high-entropy strings adjacent to credential keywords.

## Contract test assertions (minimum)

1. Execute without prepare → 404/409; prepare→execute round-trip succeeds and writes exactly one AuditEntry.
2. Digest drift between prepare and execute (fixture mutates source) → `409 state_changed`, no side effect, ticket invalidated.
3. Ticket reuse → `409 ticket_consumed`, no second side effect. Expired → `410`, no side effect.
4. Destructive descriptor without `removals`/backup population fails the registry self-check test.
5. Every registry action's prepare returns non-empty `effect_preview.summary` and passes redaction (seeded secret in params/preview never echoes).
6. GET sweep across all read endpoints performs zero writes (instrumented services).
