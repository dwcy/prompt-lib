# Data Model: AI Technology News Feed

## FeedSource

- `id`: stable source identifier
- `name`: display name
- `category`: ai-company, repository, technology, security, package, cloud, or community
- `endpoint`: source URL or feed endpoint
- `format`: rss, atom, json, api, or status
- `enabled`: user selection
- `capabilities`: articles, releases, advisories, incidents, or breaches
- `health`: healthy, degraded, unavailable, or permission_required
- `last_refreshed_at`, `last_success_at`: refresh metadata
- `error_hint`: safe user-facing failure explanation

## FeedItem

- `id`: deterministic identity from canonical URL, otherwise source plus upstream identifier
- `source_id`: owning source
- `category`: normalized category
- `title`, `summary`: display content
- `canonical_url`: external destination
- `published_at`, `updated_at`: normalized timestamps when available
- `author`: optional attribution
- `tags`: normalized labels
- `security`: optional advisory id, package, ecosystem, severity, affected versions, and exploit status
- `service`: optional provider, service, incident state, and status metadata

## UserItemState

- `item_id`: FeedItem identity
- `read`: whether the user has marked it read
- `saved`: whether the user has saved it
- `updated_at`: local state update time

## RefreshResult

- `started_at`, `completed_at`
- `source_results`: one result per source
- `new_item_count`, `updated_item_count`, `duplicate_count`
- `warnings`: non-fatal normalization or source warnings

## Validation rules

- `FeedSource.endpoint` must be an allowed external HTTP(S) endpoint.
- `FeedItem.canonical_url` must remain an HTTP(S) link and must not be executed or embedded as trusted markup.
- Items without titles or usable identities are rejected from the visible feed and counted as source warnings.
- Timestamps are normalized to UTC for sorting and displayed in the user's local time zone.
- Advisory severity and incident state are optional and must not be inferred when absent.
