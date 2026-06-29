# Contract: Frontend UI

## Scope

The frontend is a static browser application served by the local Cabal web backend. It uses plain HTML, CSS, and JavaScript. It has no framework build step and no runtime dependency on external CDNs.

## Required Views

- Overview
- Tools
- Knowledge
- Project Health
- Diagnostics or Settings

The first screen must be the Overview application dashboard.

## Global UI Behavior

- Navigation must be available without a page reload.
- Each view must own its own loading, error, stale, empty, and retry states.
- A backend failure in one section must not blank the application shell.
- Schema-version mismatch must render a visible diagnostic.
- Search and filters must update counts and visible results.
- Detail inspection must not resize fixed navigation or summary regions.
- All user-visible data must come from backend responses or documented empty states.

## Dark Application Requirements

- Use a dark neutral base with distinct success, warning, error, info, and accent colors.
- Avoid a one-hue palette.
- Keep layout dense and operational: side navigation, compact metrics, tables/lists, inspectors, and graph/list controls.
- Do not include a marketing hero, decorative cards inside cards, gradient-orb decoration, or explanatory onboarding copy as the main first screen.
- Text in controls and panels must not overlap or clip at desktop or narrow widths.

## Tools View

Required controls:

- Search input.
- Category filter.
- Status filter.
- Source/install-channel filter.
- Tool detail inspector.
- Retry or refresh control.

Required visual states:

- installed
- missing
- update available
- unsupported
- manual required
- source unavailable
- loading
- error

## Knowledge View

Required controls:

- Search input.
- Node type filter.
- Relation kind filter.
- Route or relationship inspector.

Required empty state:

- No graph bundle exists.

## Project Health View

Required sections:

- Git
- GitHub
- Supabase
- Vercel

Each section must support `ok`, `not linked`, `not authenticated`, `token missing`, `timeout`, and `error` style states when provided by the backend.

## Accessibility and Interaction

- Primary controls must be keyboard focusable.
- Focus states must be visible.
- Buttons must use clear labels or familiar icons with accessible names.
- Links that leave the local app must be visually distinct and must not include secrets.
- Copying selected text must copy redacted visible text only.

## Frontend Contract Tests

Tests or static checks must verify:

- `index.html` references local `styles.css` and `app.js`.
- No external script, stylesheet, or font CDN is required.
- The app contains named containers for all required views.
- The JavaScript defines fetch paths for required API endpoints.
- The frontend never renders raw known token-shaped fixture values.
- Required empty/error/loading state labels exist in the static assets or render helpers.
