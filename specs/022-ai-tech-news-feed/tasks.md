# Tasks: AI Technology News Feed

## Phase 1 — Setup

- [x] T001 Add feature paths and module naming to the implementation context — `.specify/feature.json`, `specs/022-ai-tech-news-feed/`
- [x] T002 [P] Add normalized feed type definitions and source catalog constants — `setup/src/cabal/news_feed.py`
- [x] T003 [P] Add frontend news types and API client — `apps/cabal-desktop/src/api/news.ts`

## Phase 2 — Foundational backend

- [x] T004 Add source adapter normalization, timestamp parsing, deduplication, and per-source failure isolation — `setup/src/cabal/news_feed.py`
- [x] T005 Add feed service with curated AI, repository, Hacker News, security, package, breach, and Azure status sources — `setup/src/cabal/news_feed.py`, `setup/src/cabal/webapi/routers/news.py`
- [x] T006 Add read/saved/source preference persistence using existing web API storage conventions — `setup/src/cabal/webapi/storage.py`, `setup/src/cabal/webapi/routers/news.py`
- [x] T007 [P] Add backend contract fixtures for healthy, malformed, duplicate, unavailable, and permission-gated sources — `setup/tests/test_news_feed.py`

## Phase 3 — User Story 1: Unified feed

- [x] T008 [US1] Add news router endpoints for sources, items, and refresh — `setup/src/cabal/webapi/routers/news.py`
- [x] T009 [US1] Register the news router and module availability key — `setup/src/cabal/webapi/app.py`, `setup/src/cabal/webapi/routers/system.py`
- [x] T010 [US1] Implement feed module shell, loading/empty/error states, and normalized item list — `apps/cabal-desktop/src/modules/news/NewsModule.tsx`
- [x] T011 [US1] Register the News Feed module in navigation and module health metadata — `apps/cabal-desktop/src/modules/registry.ts`
- [x] T012 [US1] Add feed list and item rendering components — `apps/cabal-desktop/src/modules/news/NewsModule.tsx`

## Phase 4 — User Story 2: Security and service health

- [x] T013 [US2] Add advisory, breach, package, and Azure incident metadata rendering — `apps/cabal-desktop/src/modules/news/NewsModule.tsx`
- [x] T014 [US2] Add source health and permission-gated status presentation — `apps/cabal-desktop/src/modules/news/NewsModule.tsx`
- [x] T015 [US2] Add backend tests for security fields, Azure states, and partial refresh behavior — `setup/tests/test_news_feed.py`

## Phase 5 — User Story 3: Curation and reading state

- [x] T016 [US3] Add category/source/read/saved filters and refresh controls — `apps/cabal-desktop/src/modules/news/NewsModule.tsx`
- [x] T017 [US3] Add save/read/source-selection mutations and local query updates — `apps/cabal-desktop/src/api/news.ts`, `apps/cabal-desktop/src/modules/news/NewsModule.tsx`
- [x] T018 [US3] Add persistence and filtering tests — `apps/cabal-desktop/tests/newsModule.test.tsx`

## Phase 6 — Polish

- [x] T019 Add module styles, responsive layout, keyboard focus, and external-link affordances — `apps/cabal-desktop/src/modules/news/NewsModule.css`
- [x] T020 Add frontend and API verification for the acceptance dataset — `apps/cabal-desktop/tests/newsModule.test.tsx`, `setup/tests/test_news_feed.py`
- [ ] T021 Run typecheck, lint, backend tests, and frontend tests; update quickstart if needed — `apps/cabal-desktop/package.json`, `specs/022-ai-tech-news-feed/quickstart.md`

> T021 is intentionally deferred per user instruction; no tests, lint, typecheck, or build commands were run during this implementation pass.

## Dependencies

`T001–T007` → `T008–T012` → `T013–T015` and `T016–T018` → `T019–T021`.

## Implementation strategy

Deliver the unified feed first with fixture-safe source isolation, then add security/status metadata, and finally add user curation and polish. Keep source adapters behind one normalized contract so new feeds do not require UI changes.
