# Data Model: Cabal Web UI

## WebEnvelope

Wraps every backend response.

**Fields**

- `schema_version`: string, required. Starts at `cabal-web.v1`.
- `captured_at`: ISO-8601 timestamp, required.
- `status`: `ok | partial | stale | error`, required.
- `data`: object or null, required.
- `error`: DiagnosticEvent or null, required.
- `source`: string, required. Logical backend section such as `tools`, `knowledge`, or `project_health`.

**Validation Rules**

- `schema_version` must be present on every response.
- `data` must be null when `status` is `error`.
- `error` must be null when `status` is `ok`.
- All string fields must be redacted before serialization.

## BackendHealth

Describes the local backend process and data-source readiness.

**Fields**

- `app`: constant `cabal-web`.
- `backend_version`: Cabal package or repo version when available.
- `read_only`: boolean, must be true for MVP.
- `host`: expected local bind host.
- `sections`: list of SectionHealth.
- `diagnostics`: list of DiagnosticEvent.

## SectionHealth

Per-section freshness and availability.

**Fields**

- `section`: `overview | tools | knowledge | project_health | diagnostics`.
- `state`: `ready | loading | stale | unavailable | error`.
- `last_success_at`: ISO-8601 timestamp or null.
- `message`: redacted string or null.
- `retryable`: boolean.

## OverviewSummary

Aggregated first-screen data.

**Fields**

- `tool_count`: integer.
- `tool_status_counts`: map of status key to integer.
- `knowledge_available`: boolean.
- `knowledge_counts`: KnowledgeCounts or null.
- `project_health_counts`: map of availability state to integer.
- `diagnostic_count`: integer.
- `sections`: list of SectionHealth.

## ToolCatalogPayload

Full Tools view data.

**Fields**

- `categories`: list of ToolCategoryView.
- `items`: list of ToolItemView.
- `status_counts`: map of rendered status to integer.
- `source_status_counts`: map of source status to integer.
- `install_channel_counts`: map of install channel to integer.

**Relationships**

- Each ToolItemView references exactly one category by `category`.
- Category counts are derived from item membership.

## ToolCategoryView

Browser-friendly category metadata.

**Fields**

- `name`: display name.
- `slug`: stable slug.
- `keys`: ordered list of tool keys.
- `count`: integer.

## ToolItemView

Serializable tool row.

**Fields**

- `key`: stable catalog key.
- `label`: display label.
- `category`: display category.
- `description`: redacted string.
- `source_url`: URL or null.
- `source_label`: display label.
- `source_status`: `verified | manual_required | unavailable`.
- `install_channel`: package, desktop app, container service, embedded engine, manual, or none.
- `platforms`: list of platform labels.
- `supports_current_platform`: boolean.
- `status`: `installed | missing | update_available | unsupported | manual_required | source_unavailable | loading | error`.
- `status_detail`: redacted string or null.
- `version_provider`: string or null.
- `backup_policy`: string or null.
- `badges`: list of strings.
- `safety_notes`: list of redacted strings.

**Validation Rules**

- `key`, `label`, `category`, and `description` must be non-empty.
- Verified source entries must include `source_url`.
- `status_detail` and `safety_notes` must be redacted.

## KnowledgeGraphPayload

OKF graph data for the Knowledge view.

**Fields**

- `available`: boolean.
- `bundle_path`: repo-relative path or null.
- `counts`: KnowledgeCounts.
- `nodes`: list of KnowledgeNode, possibly empty.
- `edges`: list of KnowledgeEdge, possibly empty.
- `diagnostics`: list of DiagnosticEvent.

## KnowledgeCounts

**Fields**

- `nodes`: integer.
- `edges`: integer.
- `by_type`: map of node type to integer.
- `by_relation`: map of relation kind to integer.

## KnowledgeNode

**Fields**

- `id`: stable node id.
- `label`: display label.
- `type`: concept type.
- `resource`: repo-relative source path.
- `tags`: list of strings.

## KnowledgeEdge

**Fields**

- `id`: stable edge id.
- `source`: source node id.
- `target`: target node id or null.
- `target_ref`: unresolved target reference or null.
- `kind`: relation kind.
- `reason`: redacted explanation.
- `confidence`: explicit, structured, or inferred.
- `evidence`: list of EvidenceItem.

## EvidenceItem

**Fields**

- `resource`: repo-relative path.
- `line`: integer or null.
- `text`: redacted snippet.

## ProjectHealthPayload

Serializable project dashboard state.

**Fields**

- `project_path`: redacted display path.
- `captured_at`: ISO-8601 timestamp.
- `git`: ProjectSection.
- `github`: ProjectSection.
- `supabase`: ProjectSection.
- `vercel`: ProjectSection.

## ProjectSection

**Fields**

- `state`: Cabal availability state.
- `title`: display title.
- `summary`: redacted string.
- `facts`: list of label/value pairs.
- `links`: list of safe label/url pairs.
- `hint`: redacted string or null.
- `enrich_state`: optional availability state.

**Validation Rules**

- Links may include dashboard URLs, but no token query parameters may be present.
- Sections tied to missing services may be marked `not_linked` instead of error.

## DiagnosticEvent

User-visible backend or data-source issue.

**Fields**

- `id`: stable or generated diagnostic id.
- `section`: affected section.
- `severity`: `info | warning | error`.
- `message`: redacted string.
- `details`: redacted string or null.
- `timestamp`: ISO-8601 timestamp.
- `retryable`: boolean.

## FrontendUiState

Browser-only state, not persisted by the backend in MVP.

**Fields**

- `current_view`: Overview, Tools, Knowledge, Project Health, or Diagnostics.
- `search`: current filter string.
- `filters`: selected category/status/source/relation filters.
- `selected_item`: selected tool/node/edge/section id or null.
- `section_states`: map of section to loading/error/stale state.

## State Transitions

- Section load: `idle -> loading -> ready`.
- Section retry after failure: `error -> loading -> ready | error`.
- Backend schema mismatch: `ready -> error` for affected section only.
- Tool status refresh: `loading -> installed | missing | update_available | unsupported | manual_required | source_unavailable | error`.
- Knowledge graph absent: `loading -> ready` with `available=false`, not an error.
