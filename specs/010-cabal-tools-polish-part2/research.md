# Phase 0 - Research and Design Decisions

## Decision: Make tool metadata a first-class catalog contract

**Decision**: Add a catalog layer that requires every visible tool to have a label, category, short description, official source link or explicit unavailable state, status probe, install channel, platform support, and optional version metadata.

**Rationale**: The current `ENV_INSTALLERS` and `ENV_TOOL_GROUPS` rows can render install buttons, but most rows do not carry descriptions or source links. Adding descriptions directly inside the Textual view would duplicate data and make completeness hard to test.

**Alternatives considered**:

- Keep descriptions in `views/tools.py`: rejected because the view is already large and would own catalog data.
- Extend only the existing `Tool` dataclass: rejected because `Tool` currently covers featured tools, while `ENV_INSTALLERS` drives the main grouped Tools view.

## Decision: Database installs use container-backed service specs

**Decision**: Replace database service installs with declarative container-backed service specs that include image, ports, volumes, health checks, status probes, conflict checks, and cleanup guidance.

**Rationale**: Current database installers mostly install host CLIs or package-manager database servers. That explains the reported "databases does not work to install" issue: `psql`, `sqlcmd`, Supabase, and Neon rows do not represent local database services consistently, and host package installs vary by OS. Container services are more reversible and easier to validate.

**Alternatives considered**:

- Keep host package installs: rejected because they are less reversible and produce inconsistent workstation state.
- Use Docker Compose files only: rejected for MVP because single-service specs are simpler to test and can later emit compose files if needed.

## Decision: SQLite and DuckDB are embedded engines, not normal services

**Decision**: Include SQLite and DuckDB in the database section, but label them as embedded/file-oriented engines. Provide utility setup or shell guidance and avoid pretending they are always-on daemon services.

**Rationale**: The user asked for all databases as containers, but SQLite and DuckDB do not naturally run as server databases. A containerized utility shell can be useful for consistent CLI access, while the UI should clearly explain the difference.

**Alternatives considered**:

- Hide SQLite/DuckDB from container flows: rejected because the user explicitly requested them.
- Force a long-running server abstraction: rejected because it would be misleading.

## Decision: Initial vector database set is Qdrant, Weaviate, and Milvus

**Decision**: Add at least Qdrant, Weaviate, and Milvus as AI-era vector database options with container-backed install/status flows.

**Rationale**: These are mature vector database choices with official local container documentation. Qdrant's quickstart documents Docker as the local path, with REST and gRPC ports; Redis also now positions vector search as part of its data platform, but it is already a broader cache/NoSQL database service.

**Alternatives considered**:

- Add many vector DBs at once: rejected for MVP because each needs source links, port/volume checks, and tests.
- Use Chroma in the first batch: deferred because the official Docker documentation path was less stable during research than the other three.

## Decision: Version/LTS metadata is ecosystem-specific

**Decision**: Implement version selectors through per-ecosystem providers. Highlight LTS only where upstream defines LTS or support lifecycle data; otherwise show latest/stable without inventing LTS labels.

**Rationale**: Node.js publishes a release schedule with LTS status; .NET distinguishes LTS and STS support; Python publishes supported branches and statuses. Bun, npm, and pnpm should default to latest/stable metadata unless their upstreams define LTS semantics.

**Alternatives considered**:

- Treat every package-manager latest as LTS: rejected as inaccurate.
- Keep only current hard-coded version floors: rejected because the user wants selectable latest versions.

## Decision: Runtime backup means recovery evidence, not blind binary copy

**Decision**: Before installing/upgrading Bun, npm, pnpm, Python, Node, or dotnet, capture previous version, executable path, install channel, package-manager evidence, and restore guidance. Copy user-level configuration where safe, but do not blindly copy whole runtime installation directories.

**Rationale**: Host runtimes can be installed by winget, scoop, npm, brew, distro package managers, or manual installers. Copying arbitrary install directories can be huge, incomplete, or unsafe. A structured backup record plus channel-specific restore guidance is reliable and testable.

**Alternatives considered**:

- Full filesystem backup of runtimes: rejected due size, permissions, and partial-restore risk.
- No backup for package-managed runtimes: rejected because the user explicitly requested backup functionality.

## Decision: OpenCode must detect CLI and app separately

**Decision**: Model OpenCode status as separate CLI, desktop app, and later IDE-extension signals.

**Rationale**: OpenCode's official site/docs describe it as available in terminal, desktop app, and IDE extension forms, and it documents a desktop beta plus CLI install commands. The current Cabal status only checks `opencode` on PATH.

**Alternatives considered**:

- Keep one boolean status: rejected because it cannot explain "app installed but CLI missing."

## Decision: Hermes agent install is source-gated

**Decision**: Add Hermes agent as a requested catalog item, but require a trusted source URL/install channel before enabling an automated install. Until then, the row should show "source confirmation required" and keep install disabled or manual-only.

**Rationale**: Research did not identify a clear official Hermes Agent upstream from primary sources. Installing arbitrary packages or scripts for an ambiguous agent name would be unsafe.

**Alternatives considered**:

- Use search-result package names or third-party articles: rejected because installer sources must be official or maintainer-approved.
- Omit Hermes entirely: rejected because the user explicitly requested it.

## Decision: Tools copy support should use existing app-level copy plumbing

**Decision**: Make Tools row text selectable/copyable using existing `CabalApp.action_copy`, `copy_to_clipboard`, and Textual selection behavior. Add Tools-specific tests that select description/status/error text and verify Ctrl+C reaches the clipboard.

**Rationale**: `CabalApp` already binds Ctrl+C/Ctrl+Shift+C to copy and has tests protecting against Ctrl+C quitting. The Tools view likely needs selectable widgets and integration coverage rather than a separate clipboard system.

**Alternatives considered**:

- Add a Tools-only copy handler: rejected because it would duplicate app-level clipboard behavior.

## Source Notes

- LM Studio official site documents local/private model use, app download, and CLI/headless resources: https://lmstudio.ai/
- Zed official site describes the editor and source/download links: https://zed.dev/
- OpenCode official docs describe terminal, desktop app, IDE extension, and install channels: https://opencode.ai/docs
- Redis and MariaDB have Docker Official Images: https://hub.docker.com/_/redis and https://hub.docker.com/_/mariadb
- Qdrant, Weaviate, and Milvus publish local Docker/container documentation: https://qdrant.tech/documentation/quickstart/, https://docs.weaviate.io/deploy/installation-guides/docker-installation, https://milvus.io/docs/install_standalone-docker.md
- Microsoft documents SSMS install, Cosmos DB emulator, Azurite, and Azure SQL local development: https://learn.microsoft.com/en-us/ssms/install/install, https://learn.microsoft.com/en-us/azure/cosmos-db/emulator, https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite, https://learn.microsoft.com/en-us/azure/azure-sql/database/local-dev-experience-overview
- Node.js, .NET, and Python publish release/support metadata suitable for version selectors: https://nodejs.org/en/about/previous-releases, https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core, https://devguide.python.org/versions/
