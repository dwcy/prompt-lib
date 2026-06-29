# Feature Specification: Cabal Tools View Polish Part 2

**Feature Branch**: `010-cabal-tools-polish-part2`  
**Created**: 2026-06-24  
**Status**: Draft  
**Input**: User description: "For the tools view: add short descriptions to all tools and a read-more link to source; add LM Studio, Zed IDE, database fixes and container-backed database installs, SQL Server Management Studio, DBeaver, Azure local apps, selectable text with Ctrl+C, Rider, Visual Studio, dev tools such as Postman and Hugo, Uvicorn, backup support for Bun/npm/pnpm/Python/Node/dotnet, latest/LTS version selection, OpenCode app-vs-CLI detection, and Hermes agent install support."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Tools Before Installing (Priority: P1)

As a maintainer using the Cabal Tools view, I want every tool entry to explain what the tool is and provide a read-more link so that I can make installation decisions without leaving the wizard to search manually.

**Why this priority**: The Tools view is growing into a large catalog. Clear descriptions and source links keep it understandable and reduce mistaken installs.

**Independent Test**: Open the Tools view and verify every visible tool has a concise description and a read-more action that opens or exposes a source link.

**Acceptance Scenarios**:

1. **Given** the Tools view lists any tool, **When** the row is rendered, **Then** the row includes a short plain-language description.
2. **Given** a tool has an official homepage, repository, package page, or documentation page, **When** the user activates read-more, **Then** Cabal opens or displays that source link.
3. **Given** a tool's source link is temporarily unavailable, **When** the user activates read-more, **Then** Cabal shows a clear unavailable state without breaking the Tools view.

---

### User Story 2 - Install and Detect a Broader Tool Catalog (Priority: P1)

As a maintainer, I want the Tools view to cover local AI tools, IDEs, database tools, Azure local services, desktop database clients, developer utilities, and agent tools so that Cabal can bootstrap a complete development workstation from one place.

**Why this priority**: Tool coverage is the core value of the Tools view. Missing tools force users back into manual setup and make environment status incomplete.

**Independent Test**: Load the Tools view and verify the requested new tools appear in the expected sections with status detection, install actions where supported, and source links.

**Acceptance Scenarios**:

1. **Given** the user opens the Local AI section, **When** tool rows are listed, **Then** LM Studio, Hermes agent, and OpenCode status appear, with OpenCode distinguishing CLI and desktop-app installations.
2. **Given** the user opens the IDE section, **When** tool rows are listed, **Then** Zed, Rider, Visual Studio, and existing editors appear with accurate platform-aware install/status behavior.
3. **Given** the user opens database-related sections, **When** tool rows are listed, **Then** SQL Server Management Studio and DBeaver appear in a desktop database-client section, and database engines/services appear in a database section.
4. **Given** the user opens developer utilities, **When** tool rows are listed, **Then** Postman, Hugo, Uvicorn, and existing developer tools appear with descriptions and install/status behavior.
5. **Given** the user opens Azure local tools, **When** tool rows are listed, **Then** Azure SQL local options, Cosmos DB emulator/simulator options, and related Azure development services appear where supported by the platform.

---

### User Story 3 - Use Reliable Container-Backed Database Installs (Priority: P1)

As a maintainer, I want database installs to work reliably through local containers so that database setup is reversible, isolated, and consistent across environments.

**Why this priority**: The current database install path is reported as broken, and database services are high-risk to install directly on a workstation.

**Independent Test**: From a clean machine with a supported container engine, install each database service from the Tools view and verify status, health, and uninstall or cleanup guidance.

**Acceptance Scenarios**:

1. **Given** Docker or Podman is available, **When** the user installs Redis, MariaDB, Turso/libSQL-compatible services, or selected vector databases, **Then** Cabal provisions a container-backed local service with clear status feedback.
2. **Given** SQLite or DuckDB is selected, **When** the user installs or enables it, **Then** Cabal provides a container-backed utility or documented local engine setup that reflects their embedded/file-oriented nature.
3. **Given** a required port, volume, or image is unavailable, **When** install is attempted, **Then** Cabal explains the blocking condition and does not report success.
4. **Given** the database is already installed or running, **When** status is refreshed, **Then** Cabal identifies the existing instance and avoids duplicate setup.

---

### User Story 4 - Upgrade Runtimes Safely (Priority: P2)

As a maintainer, I want version selection and backup support for core runtimes so that upgrades are deliberate and reversible.

**Why this priority**: Bun, npm, pnpm, Python, Node, and dotnet are foundational. Accidental upgrades can break many projects.

**Independent Test**: For each supported runtime, view available versions, identify latest and LTS choices where applicable, perform an upgrade with backup enabled, and verify the backup can be found or restored according to the displayed guidance.

**Acceptance Scenarios**:

1. **Given** version metadata is available, **When** the user opens a version selector for Bun, npm, pnpm, Python, Node, or dotnet, **Then** Cabal displays latest versions and highlights LTS choices where applicable.
2. **Given** the user starts an install or upgrade for a supported runtime, **When** backup is enabled, **Then** Cabal records the previous install state or recovery instructions before changing the runtime.
3. **Given** version metadata cannot be fetched, **When** the user opens the selector, **Then** Cabal shows cached or current-version information and explains that fresh metadata is unavailable.

---

### User Story 5 - Copy and Inspect Tool Output (Priority: P2)

As a maintainer, I want text in the Tools view to be selectable and copyable with Ctrl+C so that I can copy tool names, commands, version output, errors, and links into notes or issue reports.

**Why this priority**: Copy support makes troubleshooting and reporting practical, especially for install errors.

**Independent Test**: Select text in descriptions, status output, version output, and error output, press Ctrl+C, and verify the selected text reaches the clipboard without triggering an unintended app action.

**Acceptance Scenarios**:

1. **Given** text is selected in the Tools view, **When** the user presses Ctrl+C, **Then** the selected text is copied to the clipboard.
2. **Given** no text is selected, **When** Ctrl+C is pressed, **Then** Cabal preserves existing keyboard behavior and does not crash.
3. **Given** an install error is displayed, **When** the user selects and copies the message, **Then** the copied text matches the visible message.

### Edge Cases

- Container engine is missing, stopped, unsupported, or configured without permissions.
- A tool has a desktop app installed but no CLI on PATH, or a CLI installed but no desktop app.
- A requested tool is platform-specific and cannot be installed on the current operating system.
- Version metadata sources are rate-limited, offline, slow, or return incomplete release information.
- A latest release exists but is not an LTS release.
- Existing database containers have conflicting names, ports, images, or volumes.
- Source links differ by platform, package manager, or installation channel.
- Backup fails or cannot fully capture a runtime installed outside Cabal's control.
- Clipboard support is unavailable in the terminal/session environment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Tools view MUST show a concise description for every tool entry.
- **FR-002**: Every tool entry MUST expose a read-more source link when an official source, package, repository, or documentation page is known.
- **FR-003**: The Tools view MUST support selecting visible text and copying selected text with Ctrl+C without disrupting existing navigation.
- **FR-004**: The Local AI section MUST include LM Studio, Hermes agent, and OpenCode.
- **FR-005**: OpenCode status MUST distinguish between CLI availability and desktop-app availability when the platform exposes enough evidence to do so.
- **FR-006**: The editor/IDE catalog MUST include Zed, Rider, and Visual Studio in addition to existing editors.
- **FR-007**: The database catalog MUST include Turso/libSQL-compatible local service support, DuckDB, SQLite, Redis, MariaDB, and at least three vector database options relevant to AI workflows.
- **FR-008**: Database engine/service installs MUST use container-backed setup where the tool is a service, and MUST clearly label embedded/file-oriented engines when a long-running service container is not meaningful.
- **FR-009**: Cabal MUST diagnose and fix the currently broken database install path before adding new database rows.
- **FR-010**: Database install flows MUST report container engine readiness, image availability, port conflicts, volume conflicts, health state, and existing-instance detection.
- **FR-011**: SQL Server Management Studio and DBeaver MUST appear in a distinct desktop database-client section.
- **FR-012**: Azure local development tools MUST include Azure SQL local options, Cosmos DB emulator/simulator options, and related local Azure service tools that are supportable from the current platform.
- **FR-013**: The developer-tools catalog MUST include Postman, Hugo, and Uvicorn.
- **FR-014**: Bun, npm, pnpm, Python, Node, and dotnet install/upgrade flows MUST provide backup or recovery guidance before changing an existing installation.
- **FR-015**: Bun, npm, pnpm, Python, Node, and dotnet entries MUST offer version selection when version metadata is available.
- **FR-016**: Version selectors MUST identify newest available versions and highlight LTS versions when the upstream ecosystem defines LTS channels.
- **FR-017**: All new tool entries MUST include status detection, install action behavior, unsupported-platform behavior, and source-link metadata.
- **FR-018**: Tool installs MUST avoid exposing secrets, tokens, or credential-shaped values in status panes, copied text defaults, logs, or generated guidance.
- **FR-019**: Existing Tools view entries and install behavior MUST remain available unless explicitly replaced by a clearer platform-aware path.
- **FR-020**: The Tools view MUST keep long-running install, version-check, and container-status work from blocking the rest of the UI.

### Key Entities

- **Tool Entry**: A catalog item with name, category, description, source link, status detection, install behavior, platform support, and optional version metadata.
- **Tool Category**: A grouped section such as Local AI, IDEs, Databases, Database Clients, Azure Local Tools, Developer Tools, Runtimes, or AI Agents.
- **Source Link**: An official homepage, documentation page, package page, repository, or release page used by read-more.
- **Install Channel**: A supported route for installing or enabling a tool, such as package manager, desktop installer, container-backed service, embedded local engine, or manual guidance.
- **Container Database Service**: A database option managed as a local container with image, container name, ports, volumes, health status, and cleanup guidance.
- **Version Option**: A selectable runtime version with label, version number, release channel, latest marker, LTS marker, and source metadata.
- **Runtime Backup Record**: Evidence or guidance captured before changing Bun, npm, pnpm, Python, Node, or dotnet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of visible Tools view entries have descriptions and read-more source links or an explicit "source unavailable" state.
- **SC-002**: The requested new tools appear in the correct sections with status detection and unsupported-platform handling.
- **SC-003**: Database install validation covers each database option and reports failures before claiming success.
- **SC-004**: At least three vector database options can be installed or enabled through container-backed flows.
- **SC-005**: Version selectors for Bun, npm, pnpm, Python, Node, and dotnet display latest and LTS information when upstream metadata is reachable.
- **SC-006**: Backup or recovery guidance is recorded before each supported runtime install/upgrade.
- **SC-007**: Ctrl+C copies selected Tools view text in manual verification on Windows and does not break existing navigation when no text is selected.
- **SC-008**: The Tools view remains responsive while install checks, version checks, and container checks are running.

## Assumptions

- "Tools view" refers to the Cabal wizard Tools screen under `setup/src/cabal/views/tools.py` and related catalog/status/install modules.
- "Read more with link to source" means official documentation, homepage, repository, package, or release pages rather than local source-code file links.
- "Sqllite" is normalized to SQLite.
- "UVicorn" refers to Uvicorn, the Python ASGI server command-line tool.
- Container-backed database support may use Docker or Podman, matching whichever container engine Cabal already detects as available.
- SQLite and DuckDB are embedded/file-oriented engines; Cabal should provide a useful local setup and, where appropriate, a containerized utility shell rather than misrepresenting them as always-on services.
- Platform-specific tools such as SQL Server Management Studio, Visual Studio, Rider, Azure emulators, LM Studio, and Zed may expose install guidance instead of an automated install when the current OS lacks a supported unattended route.
- OpenCode may exist as a CLI, desktop application, or both; status should show both signals when detectable.
