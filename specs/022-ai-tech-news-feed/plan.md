# Implementation Plan: AI Technology News Feed

**Branch**: `022-ai-tech-news-feed` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

## Summary

Add a curated AI technology news module to the existing Cabal Desktop web UI. A backend source catalog and normalization layer will collect official AI/company news, repository activity, Hacker News, security and package advisories, breach reports, and Azure public status data. The frontend will present a filterable, source-health-aware feed with local read/saved state. Source failures and permission-gated Azure health data remain isolated and explicit.

## Technical Context

**Language/Version**: Python ≥3.14; TypeScript 7 / React 19; existing Tauri v2 shell  
**Primary Dependencies**: Existing FastAPI web API, existing desktop React/Vite stack, existing persistence and query conventions  
**Storage**: Existing application preference/storage conventions; no new database assumed  
**Testing**: pytest; Vitest + React Testing Library; Playwright smoke flow  
**Target Platform**: Windows, macOS, and Linux desktop  
**Project Type**: Desktop web UI with local backend  
**Performance Goals**: First usable feed state within 3 seconds after cached/fixture data is available; filters visibly apply within 250ms; one failed source does not delay healthy results beyond the aggregate timeout  
**Constraints**: External content is untrusted; source endpoints vary in format and availability; no authenticated scraping; Azure private Service Health is permission-gated  
**Scale/Scope**: Initial catalog of roughly 25–40 sources, hundreds of normalized items per refresh, one new frontend module and one backend ingestion/service slice  

## Constitution Check

- **Gate 1 — Spec-First Conformance**: PASS. The feature consumes RSS/Atom/JSON/status sources and exposes an internal API documented in [feed-api.md](./contracts/feed-api.md); adapter and API contracts are defined before implementation. No external protocol is reimplemented.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table below uses only agents from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: PASS when tasks are generated: API response shapes and source-adapter normalization/error isolation tests precede implementation.
- **Gate 4 — Reversible Config Changes**: N/A. No `global/` files are required.
- **Gate 5 — Minimal Skill & Agent Surface**: N/A. No new skill or agent.
- **Gate 6 — Parallel Isolation**: N/A for the initial plan. Backend and frontend work share contracts and will be sequenced unless tasks are later split into isolated worktrees.

## Subagent Delegation

| Phase / concern | Owner | Why |
|---|---|---|
| Source catalog, normalization, refresh isolation | `@python-architect` | Python service and ingestion architecture |
| Backend contract and integration tests | `@python-tester` | pytest and wire-contract coverage |
| Feed module UI and client state | `@react-architect` | Existing Vite + React desktop stack |
| Feed styling and responsive states | `@frontend-css` | CSS-only work follows repository delegation rules |
| Frontend and browser tests | `@frontend-tester` | Vitest, RTL, and Playwright coverage |
| Cross-cutting source curation, docs, and integration | `main` | Product scope and multi-layer coordination |

## Implementation Phases

### Phase 0 — Contracts and source catalog

1. Confirm the existing backend persistence, router registration, module registry, and refresh/query patterns.
2. Define the declarative initial source catalog, including official AI sources, repositories, Hacker News, CISA/NVD/GitHub/OSV/package security, breach reporting, and Azure status.
3. Add contract fixtures for normalized items, source health, duplicate handling, malformed data, and permission-gated Azure status.

### Phase 1 — Backend ingestion and API

1. Implement source definitions and adapter interfaces.
2. Implement RSS/Atom normalization and JSON/status adapters for sources that need them.
3. Add refresh orchestration with per-source timeout, failure isolation, deduplication, timestamp normalization, and safe content handling.
4. Add source/item endpoints and local read/saved/source-selection persistence.
5. Add backend unit, integration, and contract tests.

### Phase 2 — Desktop feed module

1. Register the module and add the API client/query hooks.
2. Build feed cards/list rows with source, category, timestamp, summary, advisory metadata, incident state, read state, saved state, and external-link action.
3. Build category/source filters, refresh status, empty/loading/error states, and source-health visibility.
4. Add styling through the CSS specialist and preserve existing desktop shell conventions.
5. Add frontend and Playwright coverage for filtering, persistence, partial failure, security metadata, and Azure status.

### Phase 3 — Curation and hardening

1. Validate the curated catalog and add/remove sources based on noise, reliability, and attribution quality.
2. Verify accessibility, keyboard navigation, untrusted-content handling, and external-link behavior.
3. Run the acceptance dataset and document how to add future sources.

## Project Structure

```text
setup/src/cabal/
├── news_sources.py                 # source catalog and adapter metadata
├── news_feed_service.py            # refresh, normalize, deduplicate, health
└── webapi/
    ├── routers/news.py             # feed API
    └── actions_catalog/news.py     # refresh/state actions if required

apps/cabal-desktop/src/
├── api/news.ts
└── modules/news/
    ├── NewsModule.tsx
    ├── components/
    ├── hooks/
    └── newsTypes.ts

setup/tests/                        # backend and contract fixtures
apps/cabal-desktop/tests/           # UI and browser tests
```

**Structure Decision**: Extend the existing backend and module registry. Keep provider parsing behind a backend adapter boundary so the web UI consumes one normalized feed contract.

## Complexity Tracking

| Potential complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Multiple source adapters | AI, security, package, breach, status, and community feeds have materially different fields and failure modes | One generic parser cannot represent advisory severity or Azure incident state safely |
| Per-source health and partial refresh | Users need actionable visibility when security or uptime sources fail | All-or-nothing refresh would hide healthy information and obscure operational risk |
