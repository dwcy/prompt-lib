# Research: AI Technology News Feed

## R1 — Source ingestion strategy

**Decision**: Support RSS/Atom first, with JSON/API adapters for sources that do not publish a suitable feed. Keep source definitions declarative and isolate provider-specific parsing in adapters.

**Rationale**: RSS/Atom is broadly available, cacheable, inexpensive, and avoids scraping. A small adapter seam covers Hacker News, security datasets, package advisories, and cloud status endpoints without coupling the UI to provider formats.

**Alternatives considered**: Browser scraping was rejected because markup is unstable and may violate provider expectations. One bespoke implementation per source was rejected because it makes adding or disabling sources expensive.

## R2 — Initial source catalog

**Decision**: Start with official publisher feeds for Anthropic, Google/DeepMind, OpenAI, NVIDIA, Microsoft, DeepSeek, Hugging Face, Mistral, AWS AI, and Meta AI; selected arXiv AI/ML feeds; release/activity feeds for popular AI repositories; Hacker News; and official security/status sources.

**Rationale**: Official sources reduce attribution ambiguity. arXiv, repository releases, and Hacker News add technical depth. CISA KEV, NVD, GitHub Advisories, OSV.dev, package advisories, breach reporting, and Azure Status cover actionable operational risk.

**Alternatives considered**: A large uncurated directory was rejected for the first release because it increases noise and source failure handling before the core experience is proven.

## R3 — Failure and trust boundaries

**Decision**: Treat every feed as external, untrusted content. Normalize fields, sanitize display text, preserve source URLs, isolate source failures, and expose source health to the user. Never interpret feed content as application instructions.

**Rationale**: Feeds can be malformed, unavailable, duplicated, redirected, or compromised. The feed is an information surface, not an execution surface.

**Alternatives considered**: Failing the complete refresh when one source fails was rejected because security and news sources have different availability characteristics.

## R4 — Azure health scope

**Decision**: Implement public Azure Status/incident data first. Represent authenticated Azure Service Health as a separate source capability with an explicit unavailable or permission-gated state.

**Rationale**: Public uptime data is useful without credentials; silently pretending that private service-health data is available would mislead users.

**Alternatives considered**: Requiring Azure credentials for the whole feed was rejected because it would make unrelated sources unusable.

## R5 — Local user state

**Decision**: Persist enabled sources, read state, and saved state in the existing application preference/storage conventions, with a stable item identity based on canonical URL plus source fallback.

**Rationale**: Users need continuity across refreshes, while the feed should not require a new account or server-side social model.

**Alternatives considered**: Storing state only in component memory was rejected because it loses the user's reading workflow on reload.
