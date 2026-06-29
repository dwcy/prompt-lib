# Feature Specification: Cabal Web UI

**Feature Branch**: `feat/011-cabal-web-ui`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "create a workingtree and do a web ui for the app, preferred html and vanilla javascript. Make it look like a modern dark themed application that basically connections to the backend to fetch the data we have in a similar but more advanced way to represent the ui."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explore Cabal Data From a Browser (Priority: P1)

As a prompt-lib maintainer, I want a modern dark web interface that loads Cabal data from the local backend so that I can inspect tools, project status, and knowledge data with richer filtering and visual organization than the terminal UI.

**Why this priority**: The browser UI is only valuable if it represents the same live Cabal data and improves the maintainer's ability to scan, compare, and investigate it.

**Independent Test**: Start the local backend, open the web UI, and verify the main dashboard loads live catalog, project, and knowledge summaries without using hardcoded fixture data.

**Acceptance Scenarios**:

1. **Given** the local backend is running, **When** the user opens the web UI, **Then** the dashboard shows current Cabal data with a visible loaded state and capture time.
2. **Given** a backend section is still loading, **When** the dashboard first renders, **Then** the UI remains usable and marks only that section as loading.
3. **Given** a backend section fails, **When** the dashboard receives the error, **Then** the UI shows a section-level error with a retry option and keeps other sections visible.

---

### User Story 2 - Navigate the Tool Catalog Visually (Priority: P1)

As a maintainer reviewing workstation setup, I want to search, filter, group, and inspect tool entries with descriptions, source links, status, install channel, platform support, and version metadata so that I can understand environment readiness faster than in a long terminal list.

**Why this priority**: The Tools catalog is one of Cabal's largest and most actively polished data surfaces; a web view should make it easier to understand at a glance.

**Independent Test**: Load the Tools section, search for several tools, switch categories, open a tool detail panel, and verify that metadata matches the backend catalog.

**Acceptance Scenarios**:

1. **Given** the Tools section is loaded, **When** the user searches by name, category, badge, install channel, or source status, **Then** matching tools remain visible and counts update.
2. **Given** the user selects a tool, **When** the detail panel opens, **Then** it shows the description, status, source link state, install channel, platform support, version metadata availability, and any safety notes known by Cabal.
3. **Given** a tool is unsupported or requires manual source confirmation, **When** it appears in the UI, **Then** the state is clearly distinguished from installed, missing, or update-available states.

---

### User Story 3 - Inspect Knowledge and Project Health (Priority: P2)

As a maintainer, I want the same web interface to show OKF knowledge graph summaries and project dashboard health so that I can connect tool readiness, repo state, and agent/skill relationships in one workspace.

**Why this priority**: Cabal already has data for OKF and project dashboards; the browser UI should make those relationships easier to explore together.

**Independent Test**: Open the Knowledge and Project views, filter graph concepts or project sections, and verify the UI presents the current backend snapshot and links back to relevant source artifacts.

**Acceptance Scenarios**:

1. **Given** an OKF graph bundle exists, **When** the user opens Knowledge, **Then** the UI shows graph counts, route summaries, search, filters, and an inspector for selected concepts or relationships.
2. **Given** no OKF graph bundle exists, **When** the user opens Knowledge, **Then** the UI shows an empty state explaining that export is needed without crashing.
3. **Given** a project dashboard snapshot is available, **When** the user opens Project Health, **Then** Git, GitHub, Supabase, and Vercel sections show availability states without revealing tokens or secrets.

---

### User Story 4 - Use a Polished Dark Application Shell (Priority: P2)

As a daily user, I want the web UI to feel like a focused dark desktop application with clear navigation, dense but readable information, and responsive layouts so that it remains comfortable for repeated setup and inspection work.

**Why this priority**: The user explicitly asked for a modern dark application, and Cabal is an operational tool rather than a marketing site.

**Independent Test**: View the UI at desktop and narrow widths and verify navigation, panels, tables, graphs, buttons, loading states, and detail drawers remain legible and do not overlap.

**Acceptance Scenarios**:

1. **Given** a desktop viewport, **When** the dashboard loads, **Then** the first screen shows navigation, summary metrics, primary data panels, and enough detail to start working without a landing page.
2. **Given** a narrow viewport, **When** the user navigates between sections, **Then** controls and detail panels reflow without text clipping or incoherent overlap.
3. **Given** any interactive control is focused, hovered, disabled, loading, or errored, **When** the user inspects it visually, **Then** the state is distinct and consistent across the application.

### Edge Cases

- Backend is not running, starts slowly, or restarts while the browser is open.
- Some data sources are unavailable because required CLIs, tokens, generated OKF files, or selected project paths are missing.
- A backend response is stale, partially populated, malformed, or produced by an older Cabal version.
- Search or filters produce no matching tools, graph nodes, or dashboard sections.
- Tool status checks are slow and complete after the initial catalog metadata.
- Sensitive values appear in command output, service hints, URLs, environment variables, or cached dashboard payloads.
- The browser blocks a source link or the link target is unavailable.
- A user opens the UI on a machine where the local backend should not be reachable from other devices.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web UI MUST fetch displayed Cabal data from a local backend data surface rather than relying on hardcoded browser-only fixtures.
- **FR-002**: The first screen MUST present the usable application dashboard, not a marketing landing page.
- **FR-003**: The UI MUST provide primary navigation for Overview, Tools, Knowledge, Project Health, and Settings or Diagnostics.
- **FR-004**: The Overview MUST show summary metrics and freshness states for Tools, Knowledge, Project Health, and backend connectivity.
- **FR-005**: The Tools view MUST show catalog categories, tool counts, status counts, search, filters, and per-tool detail inspection.
- **FR-006**: Tool details MUST include label, category, description, source link state, install channel, platform support, status, version metadata state, backup policy when present, and safety notes when present.
- **FR-007**: The Tools view MUST distinguish installed, missing, update available, unsupported, manual-required, source-unavailable, loading, and error states.
- **FR-008**: The Knowledge view MUST show OKF graph availability, node and edge counts, searchable concepts, relation filters, route summaries, and selected item evidence when available.
- **FR-009**: The Project Health view MUST show Git, GitHub, Supabase, and Vercel sections using the same availability concepts already used by Cabal.
- **FR-010**: Each backend-fed section MUST support independent loading, error, stale, and retry states.
- **FR-011**: The web UI MUST redact token-shaped or secret-shaped values before rendering them.
- **FR-012**: The MVP MUST be read-only for workstation-changing actions; any install, update, cleanup, or configuration mutation control MUST be absent or clearly disabled until a separate safety design exists.
- **FR-013**: The application MUST use a dark, operational interface optimized for scanning dense data, comparison, and repeated use.
- **FR-014**: The layout MUST work without incoherent overlap on desktop and narrow mobile-like widths.
- **FR-015**: The UI MUST expose backend diagnostics including backend version, data source health, last refresh time, and failed data source messages.
- **FR-016**: The backend data surface MUST identify payload schema versions so the browser can handle incompatible or stale responses gracefully.
- **FR-017**: The local backend MUST be scoped for local use and MUST NOT expose secrets, write actions, or broad filesystem access through the web UI.
- **FR-018**: Existing Cabal terminal UI behavior MUST remain available while the web UI is added.

### Key Entities

- **Web Dashboard**: The browser application shell with navigation, shared filters, summary metrics, and section-level refresh/error state.
- **Backend Data Surface**: A local read API or equivalent backend endpoint set that serializes Cabal data for the browser.
- **Tool Catalog Item**: A tool entry with metadata, current status, source link state, install channel, version metadata, backup policy, platform support, and safety notes.
- **Knowledge Graph Snapshot**: The current OKF graph availability and, when present, its concepts, relationships, evidence, counts, and source artifact references.
- **Project Health Snapshot**: The Git, GitHub, Supabase, and Vercel availability data for a selected or default project.
- **Refresh State**: Per-section metadata describing whether data is loading, fresh, stale, failed, or unavailable.
- **Diagnostic Event**: A user-visible backend or data-source problem with severity, message, affected section, timestamp, and redacted details.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can open the local web UI and see live backend-fed Overview and Tools data within 3 seconds on the current repo when local probes are warm.
- **SC-002**: Users can find a known tool by search or filter in under 10 seconds without scrolling through every category.
- **SC-003**: 100% of rendered tool detail panels include category, description, status, source state, install channel, and platform support when those fields exist in Cabal.
- **SC-004**: Backend failures in one section do not prevent other sections from rendering in manual verification.
- **SC-005**: No token-shaped values from dashboard, tool, or environment payloads appear in the rendered DOM or copied text during tests.
- **SC-006**: The UI passes manual visual checks at desktop and narrow widths with no overlapping controls, clipped labels, or unreadable state text.
- **SC-007**: Existing Cabal TUI tests continue to pass after the web UI backend/data additions.

## Assumptions

- The web UI is for local maintainer use, not a public hosted service.
- Existing Cabal Python services remain the source of truth for tool catalog, status, OKF, and project dashboard data.
- The first version is read-only because install/update/configuration actions need a separate confirmation and safety model.
- The browser UI should avoid imposing heavyweight setup requirements on maintainers.
- The current generated OKF graph viewer is useful reference material but should not be the only UI surface.
- Project selection can default to the current repo for the first version, with richer multi-project selection deferred if needed.
