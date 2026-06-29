# Implementation Plan: Headroom as a Managed Tool

**Branch**: `012-headroom-tool` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-headroom-tool/spec.md`

## Summary

Make Headroom (`chopratejas/headroom`, a context-compression layer for AI agents) a first-class managed tool inside the cabal TUI: an installer module so it appears and installs from the Tools view, registry wiring so it's grouped with the other AI CLIs, and an opt-in MCP server template so the cabal MCP manager can register it for Claude Code. A separate investigate-only research spike records a verdict on whether the transparent proxy/wrap mode works with subscription/OAuth auth. The whole feature reuses existing machinery (`installers/specify.py` pattern, `claude_mcp_add_from_template`, `enumerate_mcp_servers`, `installers/uv.uv_install`) — no new subsystems.

## Technical Context

**Language/Version**: Python 3.13 (cabal `setup/src/cabal/`)
**Primary Dependencies**: Textual (TUI), `uv` (tool installer prerequisite), `claude` CLI (`claude mcp add/list`), Headroom (`headroom-ai`, the third-party tool being managed)
**Storage**: N/A — config files only (`setup/mcp-templates.json`; Claude Code's `~/.claude.json` written via `claude mcp`)
**Testing**: pytest under `setup/`; Textual `App.run_test()`/`Pilot` smoke tests for any screen touch (none expected here)
**Target Platform**: Windows primary (subscription/OAuth Claude Code), cross-platform via the same wrapping the existing managed tools use
**Project Type**: Desktop TUI + CLI tooling (single project)
**Performance Goals**: N/A — interactive install/registration actions
**Constraints**: Reuse existing installer + MCP-template machinery; no new subsystems; honor `rules/python.md` size discipline (installer module mirrors the ~45-LoC `specify.py`)
**Scale/Scope**: 1 new installer module, edits to 1 registry module + 1 JSON template + 2 docs, 1 research deliverable

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol implemented`. We register an existing third-party MCP server via a config template; we do not author MCP tools or any wire protocol. Headroom owns its own tool schemas.
- **Gate 2 — Subagent Delegation**: Delegation table below maps each phase to an owner from `agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: `N/A`. No protocol surface is authored here. The only "contract" we own is the internal shape of an `mcp-templates.json` entry, already validated by `claude_mcp_add_from_template` / `enumerate_mcp_servers`; correctness is verified by the registration round-trip in quickstart, not by wire contract tests.
- **Gate 4 — Reversible Config Changes**: Applies — this touches `global/MCP.md` (docs) and ships `setup/mcp-templates.json`. **Rollback path**: (a) all source edits are revertable via git on this branch; (b) `global/` changes redeploy/restore through `python setup/settings-configurator-ui.py` (the restore flow rolls back `settings.json`; the MCP.md doc edit is text-only and revertable); (c) a registered Headroom MCP server is removable via the cabal MCP manager or `claude mcp remove -s user headroom`; (d) the tool itself is removable via `uv tool uninstall headroom-ai`. No one-way migration.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A` — no new skill or agent is added. This is a tool/MCP catalog addition only, extending existing registries.
- **Gate 6 — Parallel Isolation**: `N/A` — implementation is sequential single-agent. No phase dispatches concurrent writers.

All gates pass; Complexity Tracking table is empty.

## Subagent Delegation

*GATE: references `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Phase 0 — install Headroom locally, confirm MCP-serve invocation + `uv` install extras, run proxy/subscription-auth investigation → `research.md` | `main` | Cross-cutting manual investigation (shell + external tool + judgement); no single language specialist owns it |
| Phase 1 — `installers/headroom.py` + `tools.py` registry wiring | `@python-architect` | Structural Python change in the cabal package (`pyproject`/package module + dataclass registry) |
| Phase 1 — tests (if any added for the installer/registry) | `@python-tester` | pytest is the matching tester per agents.md |
| Phase 2 — `setup/mcp-templates.json` entry | `@python-architect` | Config consumed by the cabal Python MCP layer; same owner keeps template + consumer consistent |
| Phase 3 — docs (`global/MCP.md`, `setup/README.md`) + apply/verify | `main` | Documentation + deploy/verification glue, cross-cutting |
| Post-implementation — plan-compliance audit | `@code-plan-verifier` | Read-only gate before commit |

### Parallel Execution Map

N/A — no phase dispatches two or more writing subagents concurrently.

## Project Structure

### Documentation (this feature)

```text
specs/012-headroom-tool/
├── spec.md              # /speckit-specify output
├── plan.md              # This file
├── research.md          # Phase 0 — technical decisions + the proxy investigation verdict (FR-009 deliverable)
├── data-model.md        # Phase 1 — the catalog/template entities
├── quickstart.md        # Phase 1 — end-to-end verification steps
├── contracts/
│   └── mcp-template.md  # Internal config contract: shape of the headroom mcp-templates.json entry
├── checklists/
│   └── requirements.md  # /speckit-specify quality checklist
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
setup/
├── mcp-templates.json                  # EDIT — add "headroom" entry (default_enabled: false)
└── src/cabal/
    ├── tools.py                         # EDIT — import + TOOLS row + ENV_INSTALLERS + ENV_TOOL_GROUPS
    └── installers/
        ├── headroom.py                  # NEW — headroom_status() / headroom_install() (mirrors specify.py)
        ├── specify.py                   # REFERENCE — closest precedent (uv tool install)
        └── uv.py                        # REUSE — uv_install() auto-provision prerequisite

global/
└── MCP.md                              # EDIT — document the Headroom MCP server (3 tools, manual compression, opt-in)

setup/README.md                          # EDIT — note Headroom in the featured tools/MCP coverage (if enumerated)
```

**Structure Decision**: Single-project desktop TUI. The change is additive and localized: one new small installer module plus edits to the existing tool/MCP registries and docs. No new packages, services, or layers. `installers/headroom.py` follows the established `installers/specify.py` shape (`uv tool install`, auto-provision `uv`), keeping it well under the `rules/python.md` script soft cap.

## Complexity Tracking

> No constitution violations — table intentionally empty.
