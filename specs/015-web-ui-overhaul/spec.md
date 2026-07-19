# Feature Specification: Cabal Web UI Overhaul — Full-Feature Desktop Workspace

**Feature Branch**: `015-web-ui-overhaul`
**Created**: 2026-07-11
**Status**: Draft
**Input**: User description: "we have a web ui for this... but It is really poor and I need you to create a large detailed specification for a web ui containing all the features that we have that we need to add broken down. and how to best implement it with shared backend where relevant." Follow-up constraint: "the web app should be wrapped in a desktop mode but do not use electron but tauri."

## Overview

Cabal today has two user surfaces: a mature terminal application covering roughly twenty feature areas (project selection, configuration deployment, tool installation, MCP connector management, knowledge graph and retrieval, agent services, package security, session analytics, Codex parity, and more), and a first-generation web UI that covers only four of those areas, read-only, with several of its promised capabilities never activated (live tool statuses, visual knowledge graph, persistent diagnostics).

This feature replaces that first-generation web UI with a full-feature workspace: every capability available in the terminal application becomes available in the web UI, including safe, confirmation-guarded actions (installs, deployments, service control, cleanup). The web application is delivered primarily as a locally installed desktop application (native window wrapper — user-mandated technology recorded in Assumptions), while remaining reachable from a local browser for development. Both the terminal surface and the web surface must be fed by one shared backend service layer so data, statuses, action outcomes, and safety rules are identical regardless of which surface the maintainer uses.

The full feature breakdown is organized as feature modules (Section "Feature Module Breakdown") and each module's requirements are grouped under Functional Requirements.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One Desktop Workspace for Everything (Priority: P1)

As a prompt-lib maintainer, I launch a single desktop application and can reach every Cabal feature area from one navigable shell — project selection, overview dashboards, tools, configuration, knowledge, services, sessions, and security — without falling back to the terminal application for missing features.

**Why this priority**: The stated problem is that the current web UI is "really poor" because it covers a fraction of the product. Complete feature reachability is the core value; everything else refines it.

**Independent Test**: Launch the desktop application, walk the navigation, and verify every feature module listed in the Feature Module Breakdown is present, opens, and loads live data (or an honest empty/error state) — no dead links, no "not available in web" placeholders for in-scope modules.

**Acceptance Scenarios**:

1. **Given** the desktop application is installed, **When** the maintainer launches it, **Then** a native window opens showing the project gate (or last project) and a navigation structure exposing all feature modules within two levels of navigation.
2. **Given** no project has been selected yet, **When** the application starts, **Then** the maintainer can pick a recent project, browse for a folder, clone a repository, or start a new project before entering the main workspace — the same gate choices the terminal application offers.
3. **Given** the backend data layer is unavailable or still starting, **When** the window opens, **Then** the shell renders with a clear connectivity state and recovers automatically when the backend becomes reachable, without requiring an application restart.
4. **Given** the maintainer opens any feature module, **When** its data is still loading, **Then** only that module shows a loading state and the rest of the workspace stays interactive.

---

### User Story 2 - Live Environment Readiness and Tool Actions (Priority: P1)

As a maintainer setting up or auditing a workstation, I open the Tools module and see every catalog tool with its real, current status (installed version, update available, missing, unsupported), can filter and search the catalog, and can install or update a tool from the UI with an explicit confirmation and live progress output.

**Why this priority**: Tools is Cabal's largest data surface and the current web UI's single biggest defect — statuses permanently render as "loading" and no actions exist. Fixing this delivers the most visible improvement over both the old web UI and the terminal list.

**Independent Test**: Open Tools, verify statuses resolve to real values (matching what the terminal application reports for the same machine), run one install/update through the confirmation flow, and watch progress stream to completion.

**Acceptance Scenarios**:

1. **Given** the Tools module is open, **When** the catalog loads, **Then** metadata renders immediately and per-tool statuses resolve asynchronously to installed/version, update-available, missing, unsupported, or manual-required — never remaining permanently in a loading state.
2. **Given** a tool with an available update, **When** the maintainer chooses Update, **Then** a confirmation shows exactly what will run and what will change (including any pre-action backup), and nothing executes until confirmed.
3. **Given** a confirmed install/update, **When** it runs, **Then** live output streams into the UI, the action can be observed to completion (success or failure with reason), and the tool's status refreshes automatically afterward.
4. **Given** a tool that supports multiple installable versions, **When** the maintainer opens its detail, **Then** available versions can be chosen before installing.
5. **Given** search or filters (category, status, install channel, badge), **When** applied, **Then** matching results and counts update immediately and an empty result state is clearly shown.

---

### User Story 3 - Configuration Deployment and Drift Management (Priority: P1)

As a maintainer, I manage the full configuration lifecycle from the web UI: see when the repo and the deployed configuration have drifted, review per-file diffs, select what to deploy, apply it with backups, clean up stale extras, and restore from backups when something goes wrong — for both the primary assistant configuration and the Codex parity configuration.

**Why this priority**: Deploying `global/` configuration is the repo's core workflow ("edit here, deploy with the apply script"). Without it the web UI cannot replace day-to-day terminal usage.

**Independent Test**: Modify a repo configuration file, open the deployment module, verify the drift indicator and NEW/CHANGED preview, view the diff, apply the selection, and confirm the deployed copy updated with a backup created; then restore the backup.

**Acceptance Scenarios**:

1. **Given** repo configuration differs from the deployed configuration, **When** the maintainer opens the workspace, **Then** a visible drift indicator appears on the relevant navigation entries before any module is opened.
2. **Given** the deployment module is open, **When** the component tree loads, **Then** every deployable component and file shows NEW/CHANGED/UNCHANGED state, supports per-file and per-group selection, and offers a side-by-side or unified diff view per file.
3. **Given** a selection is applied, **When** deployment runs, **Then** existing files are backed up first, results are reported per file, and the drift state refreshes.
4. **Given** deployed files that did not come from the repo (extras), **When** the maintainer opens cleanup, **Then** extras are listed grouped by component with safe defaults, deletion requires confirmation, a backup is taken before removal, and prior cleanups can be restored.
5. **Given** settings backups exist, **When** the maintainer opens restore, **Then** backups are listed newest-first and restoring one preserves a pre-restore copy.

---

### User Story 4 - Sessions, Account, and Usage Observability (Priority: P2)

As a maintainer, I inspect my assistant usage from the web UI: per-project session history with durations, token counts, and costs; a cross-project sessions dashboard with per-model breakdowns, activity detail (skills, agents, tool calls), raw logs, and audited write events; my signed-in account state; configuration health checks; and the model assignment table with inline reassignment.

**Why this priority**: Observability is high-value daily-use functionality and is entirely absent from the current web UI, but it does not block environment setup workflows.

**Independent Test**: Open Sessions, verify totals and the session table match the terminal dashboard for the same data, drill into one session's breakdown and activity, delete a session with confirmation, and reassign one agent's model pin.

**Acceptance Scenarios**:

1. **Given** session transcripts exist, **When** the maintainer opens Sessions, **Then** totals (sessions, tokens in/out, cost) and a sortable session list (date, project, branch, duration, cost, tools, agents, parent/subagent relationships) render, with per-session tabs for overview, activity, raw logs, and write-audit triggers.
2. **Given** a selected session, **When** the maintainer chooses delete, **Then** a confirmation states that the transcript file will be removed from disk, and only after confirming is it deleted and the list refreshed.
3. **Given** the account panel, **When** it loads, **Then** the signed-in account and credential presence are shown without exposing any secret values.
4. **Given** configuration health checks run, **When** issues exist, **Then** each is listed with the affected file and a hint; otherwise an explicit healthy state is shown.
5. **Given** the model assignments table, **When** the maintainer reassigns a pin, **Then** the change is validated against assignable models and written to the repo source and deployed copy consistently.

---

### User Story 5 - Knowledge Graph and Retrieval Workspace (Priority: P2)

As a maintainer, I use the Knowledge module to export and validate the knowledge bundle, explore the graph visually (nodes and relationships, not just a text list), run full-text and semantic searches, build context packs at selectable budgets, run preflight checks, and review the usage ledger.

**Why this priority**: The knowledge system is fully built in the backend and terminal surface; the current web UI shows only counts and edge lists. A visual, interactive graph is one of the clearest "browser is better than terminal" wins.

**Independent Test**: Export the bundle from the UI, verify counts, open the visual graph, select a node to inspect its relationships and evidence, run one full-text and one semantic search, and generate a context pack at each budget size.

**Acceptance Scenarios**:

1. **Given** no bundle exists, **When** Knowledge opens, **Then** an empty state explains that export is needed and offers the export action inline.
2. **Given** a bundle exists, **When** the graph view opens, **Then** nodes and relationships render as an interactive visual graph with pan/zoom, type and relation filters, search-to-highlight, and a detail inspector for the selected node including its evidence and source artifact references.
3. **Given** the search tab, **When** a query is submitted, **Then** full-text results render with ranking and source references; semantic search is offered when its optional dependency is available and states its unavailability otherwise.
4. **Given** the context pack action, **When** a budget size is chosen, **Then** the generated pack is displayed with its size, contents, and a copy/export affordance.
5. **Given** doctor, preflight, index rebuild, and usage-ledger actions, **When** each runs, **Then** progress and results render in the module without leaving the workspace.

---

### User Story 6 - MCP Connectors and Local Agent Services (Priority: P2)

As a maintainer, I manage MCP servers across every scope (plugin, user, project, local, template, connector) with live status, and I operate the local agent services (bridge, orchestrator) — setup, start, stop, live status, and streamed logs — from the web UI.

**Why this priority**: These are operational controls used regularly, and service state changes (running/stopped) are exactly the kind of live status a persistent UI window shows better than a transient terminal screen.

**Independent Test**: Open MCP Connectors, verify the scope table matches the terminal view, activate one template server locally and disable it again; open Services, start and stop one service, and watch its log stream.

**Acceptance Scenarios**:

1. **Given** the MCP module, **When** it loads, **Then** all configured and available servers are listed with name, scope(s), live status, environment indicator, and command, with per-row re-check.
2. **Given** an inactive template or plugin server, **When** the maintainer activates it globally or locally, **Then** a confirmation describes what will change in which scope, and the row updates after the action.
3. **Given** a multi-scope active server, **When** the maintainer disables it, **Then** the UI asks which scope(s) to disable before acting.
4. **Given** the Services module, **When** it loads, **Then** each registered service shows live state (running, stopped, not set up, blocked), unmet prerequisites with actionable messages, and setup/start/stop/log actions as appropriate.
5. **Given** a running service, **When** logs are opened, **Then** output streams live into the UI, and stopping the service requires confirmation.

---

### User Story 7 - Project Lifecycle: Select, Clone, and Initialize (Priority: P3)

As a maintainer, I manage projects end-to-end from the web UI: switch between recent projects, browse to a folder, authenticate with the code-hosting provider, browse and clone my repositories, initialize a brand-new project from a template with per-file staging, and configure per-project settings, local configuration scaffolding, and project-scoped MCP servers.

**Why this priority**: Valuable for onboarding a new machine or project, but used far less frequently than the daily modules above.

**Independent Test**: Switch projects via recents, complete a provider login, clone a repository to a chosen destination with streamed output, and initialize a new project from a template with the staged-file preview.

**Acceptance Scenarios**:

1. **Given** the workspace is open on a project, **When** the maintainer switches projects, **Then** all project-scoped modules refresh to the new project without restarting the application.
2. **Given** the maintainer is not authenticated with the provider, **When** they open the repositories view, **Then** a guided device-style login flow completes authentication without leaving the application.
3. **Given** the new-project wizard, **When** a template source and destination are chosen, **Then** the staged files are listed with per-file toggles, project-scoped MCP configuration can be edited, and applying scaffolds the project and reports progress of any follow-on assistant handoff.
4. **Given** local project configuration, **When** the maintainer applies scaffolding actions (project instructions template, ignore rules, repo-init template, spec-workflow initialization, skills sync), **Then** each action shows a preview before applying and results after.

---

### User Story 8 - Package Security, Environment, and Identity (Priority: P3)

As a maintainer, I scan the selected project's dependencies for vulnerable, outdated, or deprecated packages and apply fixes with confirmation; I review and edit curated environment variables and inspect the full system environment; and I manage my source-control identity and the agent commit policy.

**Why this priority**: Important operational hygiene, but each is a self-contained occasional task rather than a daily loop.

**Independent Test**: Run a security scan and verify findings match the terminal module; apply one fix through the confirmation flow; edit one curated environment variable; view and change one commit-policy field.

**Acceptance Scenarios**:

1. **Given** the security module, **When** a scan completes, **Then** findings list ecosystem, package, kind, severity, current/target versions, and fix availability, and applying a fix shows the exact command before running it.
2. **Given** the environment module, **When** it loads, **Then** curated variables show current values with edit and directory-browse support, applying persists them for future shells, and the full system environment is searchable read-only.
3. **Given** the identity module, **When** it loads, **Then** source-control identity is editable at global and project scope, and the agent commit policy (agent identity, allowed types, protected branches, tag rules) is editable with validation.
4. **Given** any value that is secret-shaped, **When** it appears anywhere in these modules, **Then** it renders redacted.

---

### Edge Cases

- The backend is not running, starts slowly, restarts mid-session, or the desktop shell outlives it; the shell must reconnect and re-sync state rather than showing stale data as fresh.
- Two surfaces mutate at once: a terminal session applies configuration while the web UI has the deployment module open — the web UI must detect staleness on action and re-verify before applying, not clobber.
- A long-running action (tool install, service start, clone, export) is in flight when the maintainer navigates away or closes the window — the action must either complete under supervision with its result recoverable, or be cancelled explicitly; never silently orphaned.
- The desktop application is launched twice — a second instance must not spawn a conflicting duplicate backend or corrupt shared state.
- Default local port conflicts (the current web backend and the bridge service both default to the same port) — the backend must detect conflicts and pick/report a working port.
- An action requires an interactive terminal (assistant handoff, spec-workflow init, provider device login) — the UI must either embed the interaction, stream it, or hand off to an external terminal with clear status; never hang.
- Data sources are partially available: missing CLIs, missing tokens, missing generated bundle, unlinked services — each module shows an actionable empty/degraded state.
- Very large data: thousands of session files, large knowledge graphs, long log streams — views must stay responsive (pagination, virtualization, or equivalent) and must not lock the shell.
- Secret-shaped values appear in command output, environment values, URLs, or logs — redaction must apply to rendered content, copied text, and exported content.
- Stale or version-mismatched payloads after an upgrade — the shell must detect schema mismatch and prompt refresh/upgrade rather than misrendering.
- Filesystem paths differ across platforms (Windows-first, POSIX best-effort) — path display, browse dialogs, and generated files must be correct per platform.
- A mutation fails halfway (deploy partially applied, install exits non-zero) — the UI must report exactly what happened, what was backed up, and how to recover.

## Feature Module Breakdown

The complete inventory of feature modules the overhauled web UI must contain. "Parity source" names the existing terminal capability whose behavior defines correctness.

| # | Module | Parity source (terminal) | Actions included |
|---|--------|--------------------------|------------------|
| 1 | Project Gate & Switcher | Project gate screen, recent projects | Select, browse, prune dead recents |
| 2 | Home Overview | Home screen panels + drift markers | Refresh, navigate |
| 3 | Project Dashboard | Git/GitHub/Supabase/Vercel panel | Refresh per section, open links |
| 4 | Tools Catalog | Tools screen + tool catalog | Install, update, version select, pre-action backup |
| 5 | Global Config Deployment | Global file configuration screen | Select, diff, apply with backup |
| 6 | Cleanup & Restore | Cleanup, cleanup-restore, settings-restore screens | Backup-and-remove, restore |
| 7 | Settings Configurator | Settings screen | Toggle local overrides, reset |
| 8 | MCP Connectors | MCP screen | Activate global/local, disable per scope, re-check |
| 9 | Local Project Config | Local config screen | Scaffold, template apply, ignore rules, spec-workflow init, skills sync |
| 10 | Knowledge & Retrieval | Knowledge screen + knowledge CLI | Export, doctor, visual graph, index, search, semantic, context pack, preflight, usage |
| 11 | Agent Services | Services screen | Setup, start, stop, logs, dashboard handoff |
| 12 | Package Security | Package security screen + panel | Scan, apply fix |
| 13 | Sessions Dashboard | Sessions screen + home panel | Sort, inspect tabs, delete |
| 14 | Account & Assistant Info | Account panel, info screen | View |
| 15 | Config Doctor | Doctor panel | Run checks, view findings |
| 16 | Model Assignments | Model assignments screen | Reassign pins |
| 17 | Environment Variables | Env + system env screens | Edit curated vars, browse paths, apply |
| 18 | Git Identity & Commit Policy | Git config screen | Edit identity per scope, edit policy |
| 19 | Provider Repos & Clone | Repos, clone, device-flow, accounts screens | Login, list, clone, manage accounts |
| 20 | New Project Wizard | Init project + project MCP screens | Template select, staged apply, MCP edit, assistant handoff |
| 21 | Codex Parity | Codex global/local/conversion screens | Deploy, scaffold, conversion diff |
| 22 | Diagnostics & Backend Health | (new; partial in current web UI) | View health, persistent diagnostics, retry sources |

## Requirements *(mandatory)*

### Functional Requirements

#### Application shell & desktop delivery

- **FR-001**: The web UI MUST be delivered as an installable desktop application presenting a native window (no separate browser required), while the same UI MUST remain reachable from a local browser for development use.
- **FR-002**: The desktop application MUST manage the backend lifecycle: start it if not running, detect an already-running instance instead of duplicating it, and shut down cleanly (including supervised child processes) on exit.
- **FR-003**: Launching a second instance of the desktop application MUST NOT create a second backend or corrupt state; it MUST focus or reuse the existing instance's backend.
- **FR-004**: The shell MUST provide persistent primary navigation grouped by purpose (project, environment setup, configuration, knowledge, operations, observability) with every module in the Feature Module Breakdown reachable within two navigation levels.
- **FR-005**: The shell MUST show global connectivity and backend-health state at all times and recover automatically from backend restarts.
- **FR-006**: The UI MUST use a dark, information-dense, operational visual language with consistent loading, empty, error, disabled, and stale states across all modules, and remain usable at desktop and narrow widths.
- **FR-007**: Window state (size, position, last module, selected project) MUST persist across launches.
- **FR-008**: The shell MUST surface repo→deployed drift indicators on navigation entries for the deployment modules before those modules are opened.

#### Shared backend & parity

- **FR-009**: All data shown in the web UI MUST come from the same backend service layer the terminal application uses; no feature logic (status probing, diffing, catalogs, pricing, redaction, policy checks) may be re-implemented separately for the web surface.
- **FR-010**: All mutating operations available in the web UI MUST execute through the same service functions the terminal application uses, so an action performed in either surface produces identical results.
- **FR-011**: Every backend response MUST carry a schema version and capture time; the shell MUST detect incompatible versions and stale snapshots and respond gracefully (refresh prompt, stale badge) rather than misrendering.
- **FR-012**: Each module's data MUST load independently with per-module retry; one failed source MUST NOT block other modules.
- **FR-013**: Long-running operations MUST be modeled as observable jobs with identity, state (queued, running, succeeded, failed, cancelled), streamed output, and a result that survives navigation away and back; the shell MUST show in-flight jobs globally.
- **FR-014**: Before executing any mutation, the backend MUST re-verify the precondition snapshot the user saw (e.g., the diff about to be applied) and refuse with a clear "state changed, re-review" message if it drifted.
- **FR-015**: The terminal application MUST remain fully functional; migrating a capability into the shared service layer MUST NOT change its terminal behavior.

#### Action safety model

- **FR-016**: Every mutating action MUST require an explicit confirmation that states exactly what will run or change (commands, files, scopes) before execution; there MUST be no single-click mutations.
- **FR-017**: Destructive actions (delete session, cleanup removal, disable server, stop service) MUST additionally state what is removed and what backup, if any, is taken; where the terminal flow takes a backup first, the web flow MUST take the same backup.
- **FR-018**: The backend MUST only accept mutation requests from the local machine and MUST refuse any request that does not originate from the shell or a local browser session.
- **FR-019**: All rendered, copied, and exported content MUST pass through a single shared redaction rule set for secret-shaped values; redaction rules MUST NOT be duplicated per surface.
- **FR-020**: An audit trail of mutations performed through the web UI (what, when, outcome) MUST be recorded and visible in Diagnostics.

#### Project context (Modules 1–3)

- **FR-021**: The application MUST require a project context before opening project-scoped modules, offering recent projects (with dead-path pruning), folder browse, repository clone, and new-project creation.
- **FR-022**: The maintainer MUST be able to switch projects at any time; all project-scoped modules MUST refresh to the new context without application restart.
- **FR-023**: The Home Overview MUST aggregate: project dashboard summary, recent sessions with costs, account state, config health, knowledge bundle state, and security findings summary, each linking to its module.
- **FR-024**: The Project Dashboard MUST show source-control, hosting, and linked-service sections with cache-first render, per-section refresh, clickable external links, and hidden sections when a service is not linked.

#### Tools Catalog (Module 4)

- **FR-025**: The Tools module MUST render full catalog metadata immediately and resolve live per-tool statuses asynchronously; statuses MUST always terminate in a definitive state (never a permanent loading state).
- **FR-026**: Tool detail MUST include label, category, description, source link and its availability, install channel, platform support, current status, version metadata, backup policy, badges, and safety notes where defined.
- **FR-027**: The module MUST support search and combined filters (category, status, install channel, badge) with live counts.
- **FR-028**: Install and update actions MUST honor per-tool version selection where supported, run pre-action backups where the catalog defines a backup policy, stream progress, and refresh the tool's status on completion.
- **FR-029**: Tools whose install path is unsupported on the current platform or requires manual source confirmation MUST present that state distinctly and link to the source.

#### Configuration lifecycle (Modules 5–7, 9, 21)

- **FR-030**: The deployment module MUST present the deployable component tree with per-file NEW/CHANGED/UNCHANGED states, tri-state group selection, per-file diff view, and apply-with-backup, for both the primary configuration target and the Codex target.
- **FR-031**: Files present in the deployed target but not originating from the repo MUST be listed as extras (view-only in deployment; actionable in Cleanup).
- **FR-032**: Cleanup MUST group extras by component, default-select only stale-classified items, back up before removal, and support restoring any previous cleanup.
- **FR-033**: Settings restore MUST list existing settings backups newest-first and create a pre-restore copy before restoring.
- **FR-034**: The Settings module MUST show each cataloged setting with its source (global baseline, local override, unset), toggle local overrides per project, and support resetting all local overrides.
- **FR-035**: The Local Project Config module MUST offer the scaffolding actions with per-item preview and toggles: local config directory scaffold, project instructions template selection, stack-matched ignore rules, repo-init template, spec-workflow initialization, and repo-to-project skills sync with NEW/CHANGED preview.
- **FR-036**: The Codex Parity module MUST provide the Codex deployment tree, local Codex scaffolding, and the conversion audit (converted, not converted, target-only, stale, unsupported) with per-item source/output comparison.

#### MCP Connectors (Module 8)

- **FR-037**: The MCP module MUST list all servers across plugin, user, project, local, template, and connector scopes with live status, environment indicator, and command, and support per-row status re-check.
- **FR-038**: The module MUST support activating a server globally or per-project, approving pending project servers, and disabling with explicit scope choice when multiple scopes are active.

#### Knowledge & Retrieval (Module 10)

- **FR-039**: The Knowledge module MUST provide export, validation (doctor), and index rebuild actions with progress and result reporting, and an inline empty state offering export when no bundle exists.
- **FR-040**: The module MUST render the knowledge graph as an interactive visual graph (pan, zoom, node selection) with type and relation filters, search-to-highlight, and a selection inspector showing relationships, evidence, and source references.
- **FR-041**: The module MUST provide full-text search, semantic search when its optional capability is present (with an honest unavailable state otherwise), context-pack generation at selectable budgets with copy/export, preflight checks, and the usage ledger.

#### Agent Services (Module 11)

- **FR-042**: The Services module MUST show each registered service with live state, prerequisite checks with actionable messages, and setup/start/stop actions gated on prerequisites.
- **FR-043**: Service logs MUST stream live into the UI; stopping a service MUST require confirmation; services started by the application MUST be tracked and shut down with it.
- **FR-044**: Where a service offers its own terminal dashboard, the module MUST provide a clearly labeled external handoff.

#### Package Security (Module 12)

- **FR-045**: The security module MUST scan the selected project's ecosystems, present findings (ecosystem, package, kind, severity, current/target, fix availability) plus notices, cache results, and support re-scan.
- **FR-046**: Applying a fix MUST show the exact remediation command in the confirmation and stream its execution.

#### Observability (Modules 13–16, 22)

- **FR-047**: The Sessions module MUST show cross-project totals and a sortable, hierarchy-aware session list, with per-session detail tabs: model/token/cost overview, activity (skills, agents, tool calls, hook events), raw logs, and write-audit triggers.
- **FR-048**: Session deletion MUST be confirmation-gated and remove the transcript from disk.
- **FR-049**: The Account module MUST show signed-in identity and credential presence (never values); the Assistant Info module MUST show the reference content available in the terminal equivalent.
- **FR-050**: Config Doctor MUST run the shared health checks and list findings with file and hint, or an explicit healthy state.
- **FR-051**: Model Assignments MUST list every model pin with inline, validated reassignment writing to both repo source and deployed target.
- **FR-052**: Diagnostics MUST persist across backend restarts within a session history window, showing data-source failures, mutation audit entries, backend version, and per-source health with retry.

#### Environment & identity (Modules 17–19)

- **FR-053**: The Environment module MUST list curated variables with current values, support editing with directory-browse for path-typed variables, persist changes for future shells per platform convention, and provide a searchable read-only view of the full system environment.
- **FR-054**: The Identity module MUST edit source-control identity at global and project scope and the agent commit policy (identity, allowed types, protected branches, tag rules) with validation.
- **FR-055**: The Provider module MUST support device-style login, account management, repository listing, and cloning with destination choice and streamed progress, detecting logged-out state up front.

#### New Project Wizard (Module 20)

- **FR-056**: The wizard MUST validate destination and name, offer template sources (hosted template repositories and local templates), preview staged files with per-file toggles, allow editing project-scoped MCP configuration, and apply with streamed progress including any assistant handoff, which MUST be cancellable.

### Key Entities

- **Feature Module**: A navigable unit of the workspace mapping to one terminal capability area; owns its data sources, actions, and health state.
- **Project Context**: The currently selected project; scopes all project-bound modules and persists across launches.
- **Data Snapshot**: A versioned, timestamped payload from one data source, carrying freshness and health so the shell can mark stale or failed sections.
- **Action**: A mutating operation with a human-readable effect description, precondition snapshot, confirmation requirement, and backup policy.
- **Job**: A long-running action instance with state, streamed output, and a durable result; visible globally while in flight.
- **Confirmation**: The rendered contract of an action — exact commands, files, scopes, and backups — that must be accepted before execution.
- **Drift Report**: The computed difference between repo source and a deployed target, at component and file granularity.
- **Diagnostic Event**: A recorded backend, data-source, or mutation event with severity, affected module, timestamp, and redacted detail.
- **Tool Catalog Item**: A tool definition plus live status, versions, install channel, platform support, backup policy, and safety notes.
- **Knowledge Graph Snapshot**: Bundle availability, nodes, relationships, evidence, and index/ledger state.
- **Session Record**: A parsed transcript with project, hierarchy, duration, per-model token/cost breakdown, activity, and audit triggers.
- **Service**: A registered local agent service with prerequisites, live process state, logs, and lifecycle actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 22 feature modules in the Feature Module Breakdown are reachable and functional in the web UI; a parity walkthrough finds no in-scope terminal capability without a working web equivalent.
- **SC-002**: The desktop application opens to a usable, data-populated workspace within 3 seconds on a warm machine; slow sources load independently without blocking navigation.
- **SC-003**: 100% of tool rows reach a definitive status (never permanent loading) on a standard workstation, and statuses match the terminal application's results for the same machine at the same time.
- **SC-004**: Zero mutations execute without a confirmation that names the exact commands/files/scopes involved, verified across all action flows.
- **SC-005**: Zero secret-shaped values appear in the rendered DOM, copied text, or exported content across all modules during testing.
- **SC-006**: A maintainer can complete each of these end-to-end without the terminal application: deploy changed configuration with backup, install a tool update, activate and disable an MCP server, start and stop a service, run a security scan and one fix, and delete a session — each in under 2 minutes of interaction time.
- **SC-007**: One surface's mutation never corrupts the other: concurrent terminal/web usage tests show stale-state refusal (not clobbering) in 100% of conflict cases.
- **SC-008**: All existing terminal application tests continue to pass after the shared-backend refactor.
- **SC-009**: Closing the desktop application leaves no orphaned backend or supervised service processes in 100% of exit tests.
- **SC-010**: Sessions and knowledge views remain responsive (interaction latency under 200 ms) with 1,000+ sessions and graphs of 1,000+ nodes.

## Assumptions

- **Desktop wrapper technology is user-mandated**: the web application is wrapped as a native desktop application using Tauri (explicitly not Electron). This is recorded here as a planning constraint; all other functional requirements above are surface-technology-agnostic.
- The application is a local, single-maintainer tool. No multi-user access, remote hosting, or authentication beyond local-machine scoping is in scope.
- Mutating capabilities are in scope (superseding the read-only constraint of the first-generation web UI), because the request is full feature parity; the Action safety model section defines the required guardrails.
- The terminal application remains supported. Parity is achieved by moving logic into the shared service layer both surfaces consume — not by duplicating logic into the web backend — so behavior cannot drift between surfaces.
- The first-generation web UI is superseded by this workspace rather than maintained alongside it; its backend concepts (versioned envelopes, redaction, section health) carry forward into the shared layer.
- Interactive terminal-native flows (assistant handoff during project init, spec-workflow initialization, service terminal dashboards, provider device login) may be satisfied by streaming output, embedded guided flows, or clearly labeled external terminal handoff — full terminal emulation inside the window is not required.
- Windows is the primary platform; POSIX platforms are best-effort, matching the existing product stance.
- Browser access remains bound to the local machine; the desktop wrapper is the supported daily entry point.
- Existing backend data sources (catalogs, probes, session transcripts, knowledge bundle, dashboards, service supervisor) remain the source of truth; this feature adds no new authoritative data stores beyond job tracking and the mutation audit trail.
- Where the terminal application defers to external CLIs, the web UI inherits their availability semantics and shows actionable degraded states rather than reimplementing them.
