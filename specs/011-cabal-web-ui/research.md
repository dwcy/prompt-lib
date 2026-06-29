# Research: Cabal Web UI

## Decision: Use static HTML/CSS/vanilla JavaScript for the frontend

**Rationale**: The user explicitly prefers HTML and vanilla JavaScript. This repo is a configuration/tooling library, not a web product with an existing frontend stack. A static client avoids a Node build pipeline, package lock churn, framework conventions, and extra deployment concerns while still supporting a polished application shell.

**Alternatives considered**:

- React/Vite: rejected because it adds a frontend dependency stack the user did not ask for.
- Generated static HTML only: rejected because the UI must fetch live backend data.
- Textual-only polish: rejected because the requested output is a web UI.

## Decision: Use a small stdlib localhost Python server for MVP

**Rationale**: Cabal is already a Python package and the needed data is available through local Python service modules. A `ThreadingHTTPServer` style backend can serve static files and read-only JSON endpoints with no new hard dependency.

**Alternatives considered**:

- FastAPI/Uvicorn: viable later, but unnecessary for the MVP and would add dependencies.
- Node server: rejected because it duplicates Cabal's Python service access and conflicts with the no-build frontend direction.
- File-only JSON export: rejected because the user asked for a backend-connected app.

## Decision: Make MVP read-only

**Rationale**: Existing Cabal tool rows can install, update, and mutate workstation state. Exposing those actions in a browser requires CSRF, confirmation, provenance, logging, and safety design beyond the user's immediate request to fetch and represent existing data.

**Alternatives considered**:

- Mirror all TUI install buttons immediately: rejected as too risky for a first web surface.
- Hide action metadata entirely: rejected because users still need to understand install channels and safety state.

## Decision: Use versioned JSON envelopes for every response

**Rationale**: The browser can detect stale or incompatible payloads, show section-level failures, and keep rendering other sections. This also gives contract tests a stable surface before implementation.

**Alternatives considered**:

- Return raw model dictionaries: rejected because model internals can change without a browser compatibility story.
- One large `/api/all` response only: rejected because slow probes should not block faster sections.

## Decision: Reuse existing Cabal sources of truth

**Rationale**: `cabal.tool_catalog`, `cabal.tools`, `cabal.models.dashboard`, dashboard services, and `cabal.okf` already own most of the data. The web layer should serialize and compose those surfaces, not fork catalog metadata or invent a parallel backend model.

**Alternatives considered**:

- Maintain separate web catalog JSON: rejected because it would drift from the TUI.
- Parse rendered Textual output: rejected because it is brittle and loses structure.

## Decision: Redact before browser serialization

**Rationale**: Sensitive values should not reach JavaScript, the DOM, browser devtools, or copied text. Existing `redact_secret_text` patterns in `cabal.tool_catalog` provide a starting point, but the web backend needs a central recursive redaction pass for all payloads.

**Alternatives considered**:

- Redact only in the frontend: rejected because secrets would still travel over the local HTTP boundary.
- Trust source services to redact independently: rejected because project dashboard and diagnostics compose multiple data sources.

## Decision: Dark operational UI, dense but restrained

**Rationale**: Cabal is an operational setup and inspection tool. The UI should prioritize scan speed, state comparison, filters, tables, inspectors, and readable status colors rather than a marketing hero or decorative layout.

**Alternatives considered**:

- Hero/landing page first screen: rejected by the user goal and app-design guidance.
- Single-color dark palette: rejected because status-heavy tools need distinct neutral, success, warning, error, and accent families.
