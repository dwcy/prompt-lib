# Implementation Plan: Claude Session Dashboard

**Branch**: `feat/013-claude-dashboard` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/013-claude-dashboard/spec.md`

## Summary

Add a Sessions screen to the Cabal Textual TUI showing all historical Claude Code sessions parsed from `~/.claude/projects/` JSONL transcripts. Each session shows token usage (input/output/cache), estimated cost by model, agents dispatched (with what triggered each), skills invoked (via `/skill-name` user messages), and raw log entries. Sessions can be deleted from disk via a confirmation dialog.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Textual (TUI framework), existing Cabal app at `setup/src/cabal/`
**Storage**: Read-only from `~/.claude/projects/<encoded-path>/<session-id>.jsonl`; write (delete) only. `~/.claude/write_audit.jsonl` for hook triggers. No database.
**Testing**: pytest + fixture JSONL transcripts (no real `~/.claude/` data in tests)
**Target Platform**: Windows + POSIX (same as rest of Cabal)
**Project Type**: TUI screen + service layer — extension to existing Cabal app
**Performance Goals**: Sessions list loads within 2 seconds for up to 500 sessions; lazy-load detail on selection
**Constraints**: Read-only access to `~/.claude/`; delete is the only mutation; no new hooks required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Gate 1 — Spec-First Conformance**: N/A — no external protocol implemented.
- **Gate 2 — Subagent Delegation**: Delegation table below. `@python-architect` owns service layer; `@python-tester` owns tests; `main` owns Textual UI (no Python TUI specialist in agents.md).
- **Gate 3 — Contract Tests**: N/A — no protocol surface exposed to external consumers.
- **Gate 4 — Reversible Config Changes**: N/A — no changes under `global/`.
- **Gate 5 — Surface Minimality**: N/A — no new skills or agents introduced.
- **Gate 6 — Parallel Isolation**: N/A — all phases sequential; no concurrent writing subagents.

## Subagent Delegation

| Phase / concern | Owner | Why |
|---|---|---|
| Service layer: `session_reader.py`, `pricing.py` | `@python-architect` | Service + data parsing decisions in Python |
| Tests: `tests/dashboard/` | `@python-tester` | pytest fixtures + real-file integration tests |
| Textual Screen + widgets | `main` | No Python TUI specialist in agents.md; Textual screen is UI architecture |
| Orchestration, plan.md, constitution | `main` | Cross-cutting |

### Parallel Execution Map

N/A — all implementation phases are sequential.

## Project Structure

### Documentation (this feature)

```text
specs/013-claude-dashboard/
├── plan.md              # This file
├── research.md          # Data source findings
├── data-model.md        # Entities and service API
├── quickstart.md        # Dev setup and testing
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
setup/src/cabal/
├── screens/
│   └── sessions_screen.py       # NEW — Textual Screen: sessions list + detail tabs
├── services/
│   └── session_reader.py        # NEW — log parsing, scanning, delete
├── data/
│   └── pricing.py               # NEW — bundled model pricing table
└── wizard.py                    # MODIFIED — register SessionsScreen in navigation

tests/
└── dashboard/
    ├── fixtures/
    │   └── sample_session.jsonl  # NEW — sample JSONL for tests
    ├── test_session_reader.py    # NEW
    └── test_pricing.py          # NEW
```

## Implementation Phases

### Phase 1 — Service Layer (`@python-architect`)

**Files**: `setup/src/cabal/services/session_reader.py`, `setup/src/cabal/data/pricing.py`

1. **`pricing.py`**: Bundled dict of model prefixes → `PricingEntry`. Loads override from `~/.claude/dashboard-pricing.json` if present.

2. **`session_reader.py`**: Six functions (see `data-model.md`):
   - `scan_projects_dir(projects_dir)` — enumerate `~/.claude/projects/` recursively, yield `Session` per `.jsonl` file
   - `read_session(session)` — parse JSONL lines into `LogEntry` list; handle malformed lines gracefully
   - `compute_summary(session, entries, pricing)` — aggregate tokens, cost (tokens × pricing table), extract `AgentInvocation` from `tool_use` where `name in ("Task", "Agent")`, extract `SkillInvocation` from user messages starting with `/`
   - `delete_session(session)` — `session.log_path.unlink()`
   - `read_write_audit(audit_path, since)` — parse `~/.claude/write_audit.jsonl`, cross-reference timestamps to sessions
   - `infer_trigger(entry_index, entries)` — walk backwards from an `AgentInvocation` to find the nearest skill or user message as trigger

3. **Dataclasses** (in `session_reader.py`): `Session`, `LogEntry`, `TokenUsage`, `AgentInvocation`, `SkillInvocation`, `TriggerEvent`, `SessionSummary`, `PricingEntry`

### Phase 2 — Tests (`@python-tester`)

**Files**: `tests/dashboard/test_session_reader.py`, `tests/dashboard/test_pricing.py`

Key test scenarios:
- Parse a fixture JSONL with user/assistant/tool_use/tool_result entries → correct token sums
- Skill invocation detection: user message `/speckit-plan args` → `SkillInvocation`
- Agent dispatch detection: `tool_use` with `name="Task"` → `AgentInvocation` with `triggered_by`
- Cost calculation: tokens × pricing table (all four token types)
- Graceful handling of malformed JSONL lines
- `delete_session` removes the file (tmp dir fixture)
- Empty `~/.claude/projects/` → empty session list (no crash)

### Phase 3 — Textual Screen (`main`)

**Files**: `setup/src/cabal/screens/sessions_screen.py`, `setup/src/cabal/wizard.py`

**`sessions_screen.py`** layout:
```
┌─────────────────────────────────────────────────────────┐
│ Sessions                              [Sort: Date ▼]     │
├──────────────┬──────────────┬────────┬───────┬──────────┤
│ Project      │ Date         │ Tokens │ Cost  │ Agents   │
├──────────────┼──────────────┼────────┼───────┼──────────┤
│ prompt-lib   │ 2026-06-30   │ 45.2k  │ $0.68 │ 3        │
│ ...          │ ...          │ ...    │ ...   │ ...      │
├──────────────┴──────────────┴────────┴───────┴──────────┤
│ Total: 120 sessions · 2.3M tokens · $34.20              │
└─────────────────────────────────────────────────────────┘

On session select → detail panel with tabs:
  [Overview] [Agents & Skills] [Raw Logs] [Triggers]
```

**Overview tab**: Session metadata, per-model token + cost breakdown
**Agents & Skills tab**: Table of agents (type, trigger skill/message, tokens) + skills (name, args, timestamp)
**Raw Logs tab**: Scrollable DataTable of all log entries with type filter (user/assistant/tool_use/tool_result)
**Triggers tab**: write_audit events cross-referenced to this session by timestamp

**Delete flow**: `D` key on selected session → `ModalScreen` confirmation → `delete_session()` → refresh list

**`wizard.py`**: Add `SessionsScreen` to the navigation (same pattern as existing screens).

### Phase 4 — Verification (`@code-plan-verifier`)

After implementation:
1. Run `uv run pytest tests/dashboard/ -v` — all pass
2. Launch Cabal TUI via `.\run.cmd` — Sessions screen accessible
3. Sessions list populated from real `~/.claude/projects/`
4. Select a session → detail tabs render with real data
5. `D` key → confirmation modal → session removed from list + file deleted
6. All existing Cabal screens still navigate correctly
7. No crashes on empty or malformed JSONL files

## Complexity Tracking

No constitution violations.
