# Contract: Cabal Web Data API

## Scope

The backend exposes read-only JSON endpoints for the local browser UI. It serves static assets and JSON only. No install, update, cleanup, configuration, or file-write operation is part of MVP.

## Transport

- Bind host: `127.0.0.1` by default.
- Content type: `application/json; charset=utf-8` for API responses.
- Static assets: `text/html`, `text/css`, and `application/javascript`.
- Allowed API methods: `GET`, `HEAD`, `OPTIONS`.
- Mutating methods: `POST`, `PUT`, `PATCH`, `DELETE` must return `405`.

## Response Envelope

Every `/api/*` response uses this shape:

```json
{
  "schema_version": "cabal-web.v1",
  "captured_at": "2026-06-29T08:00:00Z",
  "status": "ok",
  "source": "tools",
  "data": {},
  "error": null
}
```

`status` is one of `ok`, `partial`, `stale`, or `error`.

## Endpoints

### `GET /api/health`

Returns backend process health and section availability.

Required `data` fields:

- `app`: `cabal-web`
- `backend_version`: string or null
- `read_only`: true
- `host`: string
- `sections`: array of section health objects
- `diagnostics`: array of diagnostic events

### `GET /api/overview`

Returns first-screen summary metrics.

Required `data` fields:

- `tool_count`
- `tool_status_counts`
- `knowledge_available`
- `knowledge_counts`
- `project_health_counts`
- `diagnostic_count`
- `sections`

### `GET /api/tools`

Returns catalog metadata and current status when available.

Required `data` fields:

- `categories`: array of category objects
- `items`: array of tool item objects
- `status_counts`
- `source_status_counts`
- `install_channel_counts`

Each tool item must include:

- `key`
- `label`
- `category`
- `description`
- `source_url`
- `source_label`
- `source_status`
- `install_channel`
- `platforms`
- `supports_current_platform`
- `status`
- `status_detail`
- `version_provider`
- `backup_policy`
- `badges`
- `safety_notes`

### `GET /api/knowledge`

Returns OKF graph summary and graph data if the bundle exists.

Required `data` fields:

- `available`
- `bundle_path`
- `counts`
- `nodes`
- `edges`
- `diagnostics`

If no graph bundle exists, return `status: "ok"`, `available: false`, empty `nodes` and `edges`, and a diagnostic with severity `info`.

### `GET /api/project-health`

Returns the current project dashboard snapshot. MVP may use the repo root as the selected project.

Required `data` fields:

- `project_path`
- `captured_at`
- `git`
- `github`
- `supabase`
- `vercel`

Each section must include:

- `state`
- `title`
- `summary`
- `facts`
- `links`
- `hint`

### `GET /api/diagnostics`

Returns recent backend and data-source diagnostics.

Required `data` fields:

- `events`: array of diagnostic events
- `counts`: severity counts

## Error Handling

- Unknown API paths return `404` with an error envelope.
- Unexpected exceptions return `500` with an error envelope and redacted message.
- Section-specific failures should prefer `status: "partial"` with diagnostics over failing the entire overview.
- Schema-incompatible source data should return `status: "error"` for that endpoint only.

## Security and Redaction

- All payloads must pass through recursive redaction before JSON serialization.
- Token-shaped values must not appear in response bodies.
- Backend must not expose arbitrary filesystem read endpoints.
- Backend must not accept project paths outside its selected/allowed project scope in MVP.

## Contract Tests

Contract tests must verify:

- Every endpoint returns the envelope shape and `schema_version`.
- Mutating methods return `405`.
- Tool items include required metadata fields.
- Missing OKF graph is a successful empty state.
- Token-shaped test values are redacted from every endpoint.
- Unknown route returns a redacted `404` envelope.
