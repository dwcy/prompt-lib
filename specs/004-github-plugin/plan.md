# Implementation Plan: Package prompt-lib as an Installable Claude Code Plugin (v1)

**Branch**: `004-github-plugin` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-github-plugin/spec.md`

## Summary

Add three small declarative files inside `global/` (plus a marketplace catalog at the repo root) that re-expose the existing prompt-lib skills, agents, hooks, output-styles, and MCP servers as an installable Claude Code plugin. The plugin is sourced from GitHub via `/plugin marketplace add <owner>/prompt-lib` + `/plugin install prompt-lib@prompt-lib`. The apply-script path (`setup/settings-configurator-ui.py` / `setup/tools/apply-global-claude-settings.sh`) keeps working unchanged for users who prefer it — the new files are either harmless when copied to `~/.claude/` or excluded by a small wizard-side ignore list. No content duplication, no build step: the apply path and the plugin path both read from the same `global/` tree.

Effective change-set: 4 new files, 1 small wizard edit, 1 README/docs update, 1 validation script. Zero changes to any existing skill, agent, hook script, or MCP server definition.

## Technical Context

**Language/Version**: JSON (plugin manifest, marketplace, MCP, hooks); no code added in v1.
**Primary Dependencies**: Claude Code CLI (consumer of the manifest) — version recent enough to support `/plugin marketplace add`, `/plugin install`, `--plugin-dir`. No new pip/Node/Cargo dependencies.
**Storage**: N/A — declarative config files only.
**Testing**: `claude plugin validate` for schema; manual smoke checklist in `quickstart.md`; two small parity scripts (MCP-sync and hooks-sync) to enforce the cross-file invariants documented in the plugin-manifest contract.
**Target Platform**: Plugin runtime is wherever Claude Code runs (Windows, macOS, Linux). Hook scripts retain their existing OS prerequisites (Python for `.py`, PowerShell for `.ps1`).
**Project Type**: Configuration packaging / distribution. Not application code.
**Performance Goals**: SC-201 — under 2 minutes from "I heard of prompt-lib" to "everything works." No runtime-perf criteria for the plugin itself.
**Constraints**: Apply path MUST keep working (SC-202); plugin MUST validate (SC-204); plugin MUST be the only modification needed — no users have to set anything beyond what they set today.
**Scale/Scope**: One marketplace, one plugin, repackaging 22 skills + 17 agents + 4 output styles + 8 hooks + 8 MCP servers that already ship.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0, the following gates apply:

- **Gate 1 — Spec-First Conformance**: PASS. This feature implements the Claude Code plugin contract. Two contract files pin the conformance scope:
  - [`contracts/marketplace.contract.md`](./contracts/marketplace.contract.md) — marketplace catalog wire format.
  - [`contracts/plugin-manifest.contract.md`](./contracts/plugin-manifest.contract.md) — plugin manifest, hooks config, MCP config, plus two cross-file parity invariants (`mcp-sync`, `hooks-sync`).
  The published Claude Code plugin docs are authoritative; both contracts cite the canonical URLs. No deviation from the documented schemas.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table below maps every phase to an owner. No domain specialist matches plain JSON manifest authoring — `main` is the correct owner per `.specify/memory/agents.md` rules ("Cross-cutting orchestration, ADRs, scripts that span domains | main").
- **Gate 3 — Contract Tests Before Implementation**: PASS. The two contract files in `./contracts/` define the schema and parity surfaces. The validation runner (`claude plugin validate` + the two `jq` parity scripts) is the contract test. Per the constitution, contract tests MUST appear before implementation in `tasks.md` — to be enforced when `/speckit-tasks` runs.
- **Gate 4 — Reversible Config Changes**: PASS. Every change under `global/` is purely additive: three new files (`global/.claude-plugin/plugin.json`, `global/.mcp.json`, `global/hooks/hooks.json`) and one new file at the repo root (`.claude-plugin/marketplace.json`). Rollback path: `git rm` those four files, revert the wizard's ignore-list patch in one commit. No content of any existing file in `global/skills/`, `global/agents/`, `global/output-styles/`, `global/hooks/*.py`, `global/hooks/*.ps1` is touched.
- **Gate 5 — Minimal Skill & Agent Surface**: PASS. Zero new skills, zero new agents, zero new output styles. The plugin packages what already ships.
- **Gate 6 — Parallel Isolation**: N/A. No phase dispatches two or more writing subagents concurrently. All work is sequential.

No gate violations. No Complexity Tracking entries needed.

## Subagent Delegation

*GATE: Must reference `.specify/memory/agents.md` before generating tasks.*

| Phase / concern | Owner | Why |
|---|---|---|
| Plugin manifest authoring (`global/.claude-plugin/plugin.json`) | `main` | Cross-cutting JSON config — no language-stack specialist matches. Per `agents.md`: "Cross-cutting orchestration, ADRs, scripts that span domains | main". |
| Marketplace catalog (`.claude-plugin/marketplace.json`) | `main` | Same — cross-cutting JSON. |
| Hooks config translation (`global/hooks/hooks.json`) | `main` | 1-to-1 mapping from existing `settings.json` `hooks` block; no script logic changes. |
| MCP config extraction (`global/.mcp.json`) | `main` | 1-to-1 copy from existing `settings.json` `mcpServers` block. |
| Apply-wizard ignore-list patch (`setup/settings-configurator-ui.py` or the underlying copy logic) | `@python-architect` | Python edit to existing wizard logic. Touches actual code, not just config. |
| README + scope-split docs update (`README.md`, `global/MCP.md` or new `docs/plugin-install.md`) | `main` | Documentation. |
| Validation scripts: `claude plugin validate` invocation + `mcp-sync` + `hooks-sync` parity diffs | `main` | Small bash / jq one-liners. No specialist match. Could be added to a `Makefile` or `setup/tools/validate-plugin.sh`. |
| Smoke-test execution against the local plugin (`claude --plugin-dir ./global`) | `main` | Manual verification step. |
| Plan conformance audit before commit | `@code-plan-verifier` | Constitution Gate before pushing. Read-only audit. |

### Parallel Execution Map

*GATE 6: Required when ≥2 writing subagents run concurrently in any phase. Otherwise write `N/A`.*

N/A — all phases run sequentially. No two writing subagents dispatched concurrently.

## Project Structure

### Documentation (this feature)

```text
specs/004-github-plugin/
├── plan.md                                ← This file (/speckit-plan output)
├── spec.md                                ← User-facing spec (already written)
├── research.md                            ← Phase 0 — design decisions (R1–R11)
├── data-model.md                          ← Phase 1 — entity inventory (marketplace, manifest, hooks, MCP)
├── quickstart.md                          ← Phase 1 — install + smoke-test guide
├── contracts/
│   ├── marketplace.contract.md            ← Phase 1 — marketplace wire-format contract
│   └── plugin-manifest.contract.md        ← Phase 1 — plugin manifest, hooks, MCP contracts + parity invariants
└── tasks.md                               ← Phase 2 — /speckit-tasks output (NOT created by /speckit-plan)
```

### Source Code Changes (across the repo)

```text
.claude-plugin/                            NEW DIR
└── marketplace.json                       NEW — single-plugin marketplace catalog (Entity 1+2)

global/
├── .claude-plugin/                        NEW DIR
│   └── plugin.json                        NEW — plugin manifest (Entity 3)
├── .mcp.json                              NEW — MCP server registry (Entity 5)
├── hooks/
│   ├── hooks.json                         NEW — plugin-shaped hooks registry (Entity 4)
│   ├── command_guard.py                   UNCHANGED
│   ├── file_write_guard.py                UNCHANGED
│   ├── write_audit.py                     UNCHANGED
│   ├── session-start.ps1                  UNCHANGED
│   └── stop-session.ps1                   UNCHANGED
├── skills/                                UNCHANGED — auto-discovered by plugin loader
├── agents/                                UNCHANGED — auto-discovered by plugin loader
├── output-styles/                         UNCHANGED — auto-discovered by plugin loader
├── settings.json                          UNCHANGED — apply-path source of truth
├── rules/                                 UNCHANGED — apply-only
├── project-templates/                     UNCHANGED — apply-only
├── CLAUDE.md                              UNCHANGED — apply-only
├── keybindings.json                       UNCHANGED — apply-only
├── statusline.py                          UNCHANGED — apply-only
└── (other docs)                           UNCHANGED

setup/
├── settings-configurator-ui.py            MODIFY — extend the wizard's per-file copy logic to skip plugin-only files
│                                          (.claude-plugin/**, .mcp.json, hooks/hooks.json relative to global/)
└── tools/
    ├── apply-global-claude-settings.sh    MODIFY — same ignore-list addition for the bash fallback
    └── validate-plugin.sh                 NEW (optional) — runs `claude plugin validate`, mcp-sync diff, hooks-sync check

README.md                                  MODIFY — add a "Install as a plugin" section pointing at quickstart.md
                                                    and naming the apply path as the existing alternative
global/MCP.md                              MODIFY — short note on plugin packaging + scope split (or add docs/plugin-install.md)
```

**Structure Decision**: Single-repo, single-plugin marketplace. Plugin root = `global/`. Marketplace root = repo root. Justified in [research R1](./research.md) and [R2](./research.md). This avoids both repo-pollution (option A) and content duplication (options B + C).

## Implementation Notes

### File-by-file contents are pinned by contracts

The exact JSON content of every new file is documented in [`contracts/plugin-manifest.contract.md`](./contracts/plugin-manifest.contract.md) and [`contracts/marketplace.contract.md`](./contracts/marketplace.contract.md). `/speckit-tasks` will emit individual T-tasks for creating each of the four files with their contract-specified content.

### Apply-wizard ignore-list patch

The wizard walks `global/` and copies files into `~/.claude/`. The patch adds a small "skip if matches plugin-only pattern" check. Patterns (relative to `global/`):

```
.claude-plugin/**
.mcp.json
hooks/hooks.json
```

Three patterns. Implementation likely a `fnmatch` check inside the copy loop. The `@python-architect` task line will need to read `setup/settings-configurator-ui.py` first to identify the exact insertion point.

### Parity scripts

Two one-liners that any maintainer adding/removing a hook or MCP server can run before commit:

```bash
# mcp-sync — exit 0 means parity holds
diff <(jq -S '.mcpServers' global/.mcp.json) <(jq -S '.mcpServers' global/settings.json)
```

```bash
# hooks-sync — exit 0 means parity holds (basename-normalized)
python3 setup/tools/diff-hooks-parity.py global/hooks/hooks.json global/settings.json
```

The Python helper (`diff-hooks-parity.py`) is ~30 lines: load both files, normalize each command to its (event, matcher, script basename) tuple, compare the resulting sets. Will be a `main` task.

### Why `version` is omitted

Per [research R4](./research.md): omitting `version` from both the plugin manifest and the marketplace entry makes every git commit a new effective version. Users always get the latest after `/plugin update`. Matches today's "actively developed personal lib" cadence. If a stable-release model is ever wanted, adding an explicit `version` is a non-breaking change.

### What does NOT change

- No skill, agent, hook script, or output style file in `global/` is touched.
- `global/settings.json` is unchanged. The plugin path uses `global/.mcp.json` and `global/hooks/hooks.json`; the apply path continues to use `global/settings.json`. Parity is enforced by the two parity scripts above.
- The existing 003-issue-triage feature is untouched. No conflict.

### Rollback path (Gate 4 explicit)

To revert this feature on the local machine:

1. `git rm -r .claude-plugin/ global/.claude-plugin/ global/.mcp.json global/hooks/hooks.json`
2. `git checkout HEAD~1 -- setup/settings-configurator-ui.py setup/tools/apply-global-claude-settings.sh`
3. `git commit -m "revert: plugin packaging"`
4. Users on the plugin path: `/plugin uninstall prompt-lib@prompt-lib`. The cache cleans up; `~/.claude/` is untouched.
5. Users on the apply path: nothing to do — they were never using the plugin.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate violations. Table empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | (none) | (none) |

## Post-Design Constitution Re-check

After Phase 1 (this document + research + data-model + contracts + quickstart), every gate is still PASS:

- **Gate 1**: Both contracts cite the canonical Claude Code plugin docs URLs. No undocumented deviations.
- **Gate 2**: Delegation table is filled; every phase has a named owner.
- **Gate 3**: Contracts exist before any implementation file is created.
- **Gate 4**: Rollback path is documented above.
- **Gate 5**: No new skill or agent.
- **Gate 6**: No parallel writing dispatch in any phase.

Plan ready for `/speckit-tasks` to expand into `tasks.md`.
