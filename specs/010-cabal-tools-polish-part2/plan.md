# Implementation Plan: Cabal Tools View Polish Part 2

**Branch**: `010-cabal-tools-polish-part2` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-cabal-tools-polish-part2/spec.md`

## Summary

Expand and stabilize the Cabal Tools view so it becomes a richer workstation bootstrap surface: every tool gets description/source metadata, new tool categories are added, database setup moves to explicit container-backed service definitions, runtime installs gain backup/version choices, and Tools text becomes copyable without breaking existing navigation. The technical approach is to make tool metadata a first-class catalog contract, add focused service modules for containers/version metadata/backups, and keep all long-running probes in existing Textual workers.

## Technical Context

**Language/Version**: Python >=3.11  
**Primary Dependencies**: Textual, Rich, stdlib subprocess/shutil/platform/json/urllib; no new runtime dependency planned  
**Storage**: Local user-machine state only: optional runtime backup records and container volumes; repo source remains the catalog/config source of truth  
**Testing**: pytest, Textual `App.run_test()`, monkeypatched subprocess/network/container probes  
**Target Platform**: Windows primary; macOS/Linux best-effort with explicit unsupported states  
**Project Type**: Python Textual desktop/terminal app  
**Performance Goals**: Tools screen remains responsive while probes/installers/version checks run; first visible render should not wait on network or container checks  
**Constraints**: No secret/token leakage; installer commands must stay capture-mode; source links must be official or explicitly marked unavailable; destructive container cleanup must be explicit; no writes under `global/`  
**Scale/Scope**: Roughly 50+ tool rows, 8+ tool categories, 10+ new install/status surfaces, 4 design contracts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0, the following gates apply:

- **Gate 1 - Spec-First Conformance**: N/A - no external protocol. This is a local Textual UI and installer/catalog feature.
- **Gate 2 - Subagent Delegation**: Delegation table below maps every phase to owners from `.specify/memory/agents.md`.
- **Gate 3 - Contract Tests Before Implementation**: Contract tests are required for the tool catalog schema, database container service specs, runtime version/backup records, and Tools UI copy/read-more behavior before implementation tasks.
- **Gate 4 - Reversible Config Changes**: N/A for `global/`; this feature does not change deployable Claude configuration. Runtime/tool changes are outside `global/` and must expose backup, recovery, or manual uninstall guidance.
- **Gate 5 - Minimal Skill & Agent Surface**: N/A - no new skill or agent is added.
- **Gate 6 - Parallel Isolation**: N/A - implementation should be sequential because catalog, installer registry, and Tools UI files are tightly shared.

No constitution violations are expected.

## Subagent Delegation

*GATE: Must reference `.specify/memory/agents.md` before generating tasks.*

| Phase / concern | Owner | Why |
|---|---|---|
| Tool catalog model, metadata registry, installer registry wiring | `@python-architect` | Python package structure and shared registry design |
| Textual Tools view descriptions, read-more actions, selectable/copyable text, version selectors | `@python-architect` | Textual UI behavior lives in Python views |
| Container-backed database and Azure local-service installer/status modules | `@python-architect` | Python subprocess/container orchestration |
| Runtime backup and version metadata services | `@python-architect` | Python service/helper module work |
| Unit, contract, and integration tests | `@python-tester` | pytest and Textual test ownership |
| Hermes source confirmation and final source-link review | `main` | Product/source-trust decision; no matching specialist in roster |
| Final plan compliance audit | `@code-plan-verifier` | Read-only implementation audit |

### Parallel Execution Map

N/A - no parallel writing subagents planned. The feature touches shared registry/UI modules where sequential changes are simpler and safer.

## Project Structure

### Documentation (this feature)

```text
specs/010-cabal-tools-polish-part2/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── tool-catalog.contract.md
│   ├── database-container.contract.md
│   ├── tools-ui.contract.md
│   └── version-backup.contract.md
└── tasks.md
```

### Source Code (repository root)

```text
setup/src/cabal/
├── tools.py
├── env_detect.py
├── views/
│   └── tools.py
├── installers/
│   ├── _common.py
│   ├── ai_clis.py
│   ├── cloud.py
│   ├── containers.py
│   ├── databases.py
│   ├── devtools.py              # planned
│   ├── editors.py
│   ├── runtime_backups.py       # planned
│   └── versions.py              # planned
└── tool_catalog.py              # planned

setup/tests/
├── test_tools_catalog.py        # planned
└── test_tools_screen_metadata.py # planned

tests/unit/
├── test_database_container_specs.py # planned
├── test_tool_versions.py            # planned
└── test_runtime_backups.py          # planned

tests/integration/
├── test_tools_screen_copy.py        # planned
└── test_tools_screen_versions.py    # planned
```

**Structure Decision**: Keep the Tools feature inside the existing Cabal Python package. Add small helper modules for catalog metadata, version metadata, runtime backup records, and container-backed database specs rather than expanding `tools.py` and `views/tools.py` further.

## Phase 0: Research

Resolved in [research.md](./research.md):

- Tool metadata becomes a required catalog contract instead of ad hoc row text.
- Database installs move from direct host package installs to container service specs with preflight, health, and conflict checks.
- SQLite and DuckDB are treated as embedded/file-oriented engines with utility-shell or local-engine setup, not always-on services.
- Version/LTS metadata is ecosystem-specific; LTS is highlighted only where upstream defines it.
- Runtime backup means reversible evidence and recovery guidance, not unsafe whole-install-directory copying.
- OpenCode must detect CLI, desktop app, and IDE-extension signals separately.
- Hermes agent install support is source-gated until a trusted upstream is confirmed.

## Phase 1: Design and Contracts

Generated artifacts:

- [data-model.md](./data-model.md)
- [contracts/tool-catalog.contract.md](./contracts/tool-catalog.contract.md)
- [contracts/database-container.contract.md](./contracts/database-container.contract.md)
- [contracts/tools-ui.contract.md](./contracts/tools-ui.contract.md)
- [contracts/version-backup.contract.md](./contracts/version-backup.contract.md)
- [quickstart.md](./quickstart.md)

## Phase 2: MVP Implementation Plan

1. Add contract tests for tool metadata completeness, source-link presence, category placement, and unsupported-platform behavior.
2. Introduce a `tool_catalog.py` metadata layer and migrate existing `ENV_INSTALLERS`/`ENV_TOOL_GROUPS` rows to use one source of truth for labels, descriptions, source links, install channels, and status probes.
3. Update the Tools view to render descriptions, read-more actions, selectable status/error text, and version selectors without blocking the UI.
4. Add database container service specs and tests for Redis, MariaDB, Turso/libSQL local service, Qdrant, Weaviate, Milvus, plus embedded SQLite/DuckDB utility setup.
5. Repair existing database install behavior by replacing direct host server installs with container-backed service flows or clearly labelled CLI-only installs.
6. Add desktop database clients: SQL Server Management Studio and DBeaver in their own section.
7. Add Azure local tools: Azure SQL local development options, Cosmos DB emulator/simulator, and Azurite where platform support allows.
8. Add Local AI/agent entries: LM Studio, Hermes agent (source-gated), and OpenCode CLI/app detection.
9. Add IDE/editor entries: Zed, Rider, Visual Studio.
10. Add developer tools: Postman, Hugo, Uvicorn.
11. Add runtime version metadata providers and selectors for Bun, npm, pnpm, Python, Node, and dotnet, with LTS highlighting where meaningful.
12. Add runtime backup/recovery records for Bun, npm, pnpm, Python, Node, and dotnet before install/upgrade changes.
13. Update PyInstaller hidden imports if new modules need explicit inclusion.
14. Run focused unit/integration tests, manual Windows Tools view verification, and a `@code-plan-verifier` audit.

## Complexity Tracking

No constitution violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

## Post-Design Constitution Recheck

**Status**: PASS

The plan defines contracts before implementation, delegates Python implementation and tests to the matching agents, avoids new global config, adds no new skill/agent surface, and keeps implementation sequential to avoid parallel worktree requirements.

## Next Command

Run `/speckit-tasks` for `010-cabal-tools-polish-part2` after accepting this plan.
