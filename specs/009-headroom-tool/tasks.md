---

description: "Task list for 009-headroom-tool implementation"
---

# Tasks: Headroom as a Managed Tool

**Input**: Design documents from `/specs/009-headroom-tool/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mcp-template.md, quickstart.md

**Tests**: Light pytest smoke/visibility checks only (no protocol contract tests — Constitution Gate 3 = N/A; we register an existing third-party MCP server, we do not author one).

**Organization**: Grouped by phase per the approved plan. All tasks run sequentially — **no concurrent writers** (`Parallel: no` everywhere), so no worktree isolation is required (Constitution Gate 6 = N/A).

## Format: `[ID] [P?] [Story] Description — Owner: @<agent>`

- **[P]**: parallelizable — none here (sequential feature).
- **[Story]**: US1 / US2 / US3 maps to spec.md user stories.
- **Owner**: named subagent from `.specify/memory/agents.md`.

---

## Phase 1: Research Spike (Foundational — corresponds to plan Phase 0)

**Status**: ⬜ Pending (0/3 — T001–T003)
**Purpose**: Confirm the empirical unknowns the installer + template depend on, and produce the investigate-only proxy verdict.

**⚠️ CRITICAL**: T001–T002 block Phase 2 and Phase 3 (the installer extra and the MCP serve invocation must be confirmed before they are written). T003 (US3) blocks nothing — it is the FR-009 deliverable and no code depends on its outcome (FR-010).

- [ ] T001 Install Headroom locally and confirm the exact `uv tool install` package spec/extra that yields a working `headroom` CLI **with** the MCP server present (`headroom-ai[mcp]` vs `[all]`); verify `headroom --version`; record the confirmed spec in `specs/009-headroom-tool/research.md` §A2 — Owner: main
- [ ] T002 Confirm the exact stdio invocation the Headroom MCP server runs (inspect what `headroom mcp install` writes to `~/.claude.json`, and/or `headroom mcp --help`); record the confirmed `command`/`args` in `specs/009-headroom-tool/research.md` §A3 — Owner: main
- [ ] T003 [US3] Run the proxy/subscription-auth investigation per `research.md` §B steps (does `headroom wrap claude`/proxy work with subscription/OAuth Claude Code without an API key; risks; measured savings if any) and fill §B **Findings / Risks / Measured savings / Verdict** (pursue/shelve/reject) — Owner: main

**Checkpoint**: research.md §A2, §A3 confirmed and §B verdict recorded. Implementation can begin.

---

## Phase 2: User Story 1 — Install Headroom from the Tools view (Priority: P1) 🎯 MVP

**Status**: ⬜ Pending (0/3 — T004–T006)
**Goal**: Headroom appears in the cabal Tools view and the AI-CLIs group, and installs/upgrades in one action.

**Independent Test**: Launch the cabal TUI → Tools view shows the Headroom row → Install → status flips to `installed {version}`; `headroom --version` works in a fresh shell.

- [ ] T004 [US1] Create `setup/src/cabal/installers/headroom.py` mirroring `setup/src/cabal/installers/specify.py`: module docstring; `headroom_status() -> str` (via `shutil.which("headroom")` + `headroom --version`); `headroom_install() -> tuple[bool, str]` (ensure `uv` via `cabal.installers.uv.uv_install`; `uv tool upgrade` if present else `uv tool install` with the spec confirmed in T001). Keep well under the python.md script soft cap — Owner: @python-architect
- [ ] T005 [US1] Wire Headroom into `setup/src/cabal/tools.py`: import `headroom_install`/`headroom_status`; append a `Tool(key="headroom", name="Headroom (context compression)", …)` to `TOOLS`; add `("headroom", "Headroom", headroom_install)` to `ENV_INSTALLERS`; add `"headroom"` to the `"AI CLIs"` group in `ENV_TOOL_GROUPS`. No `WINGET_IDS` entry — Owner: @python-architect
- [ ] T006 [US1] Add a pytest smoke check under `setup/` (e.g. `tests/`) asserting `import cabal.tools` succeeds, `"headroom"` is present in `TOOLS`/`ENV_INSTALLERS` and in the `"AI CLIs"` group, and `headroom_status()` returns a `str` — Owner: @python-tester

**Checkpoint**: US1 fully functional and independently testable in the Tools view.

---

## Phase 3: User Story 2 — Register Headroom as an opt-in MCP server (Priority: P2)

**Status**: ⬜ Pending (0/2 — T007–T008)
**Goal**: The cabal MCP manager lists Headroom as an opt-in server that registers cleanly for Claude Code.

**Independent Test**: MCP manager shows `headroom` (not enabled by default) → register → `claude mcp list` shows it Connected → fresh Claude Code session exposes the 3 tools and a compress→retrieve round-trip succeeds.

- [ ] T007 [US2] Add a `headroom` entry to `setup/mcp-templates.json` per `contracts/mcp-template.md`: `transport: stdio`, `command`/`args` confirmed in T002, `env_required: []`, `default_enabled: false` — Owner: @python-architect
- [ ] T008 [US2] Add a pytest visibility check that `mcp-templates.json` parses and that `enumerate_mcp_servers()` returns a `headroom` key carrying the `"template"` scope (live `claude mcp add` registration + in-session tool round-trip is covered manually in T011) — Owner: @python-tester

**Checkpoint**: US1 AND US2 both work; Headroom is registrable and opt-in.

---

## Phase 4: Docs, Deploy & Verification (Polish & Cross-Cutting)

**Status**: ⬜ Pending (0/4 — T009–T012)
**Purpose**: Document, deploy through the reversible flow, verify end-to-end, and gate the commit.

- [ ] T009 Document the Headroom MCP server in `global/MCP.md`: the 3 tools (`headroom_compress`/`headroom_retrieve`/`headroom_stats`), that compression is on-demand (not automatic), and the opt-in default (FR-011) — Owner: main
- [ ] T010 Note Headroom in `setup/README.md` where it enumerates featured tools / MCP coverage — Owner: main
- [ ] T011 Deploy via `python setup/settings-configurator-ui.py`, then run `quickstart.md` §1–§4 end-to-end: Tools install + status flip (SC-001/SC-002), MCP register + 3 tools in a fresh session + compress/retrieve round-trip (SC-003), opt-in absence check (SC-004), and regression of existing Tools/MCP entries (SC-006) — Owner: main
- [ ] T012 Read-only plan-compliance audit of the implementation against `plan.md` + `quickstart.md` (no shortcuts, no unplanned files, python.md size discipline, gates honored); emit PASS / PASS WITH WARNINGS / FAIL before commit — Owner: @code-plan-verifier

---

## Dependencies & Execution Order

- **Phase 1 (Spike)**: no dependencies; T001–T002 BLOCK Phases 2–3; T003 blocks nothing (investigate-only, FR-010).
- **Phase 2 (US1)**: needs T001 (install spec). T005 depends on T004; T006 depends on T005.
- **Phase 3 (US2)**: needs T002 (MCP invocation). T008 depends on T007. Independent of US1 in principle, but US1 (the tool installed) is needed for the live round-trip in T011.
- **Phase 4**: T011 depends on Phases 2–3 shipped; T012 depends on all prior tasks.

### Within stories
- T004 → T005 → T006 (US1, sequential — same package).
- T007 → T008 (US2, sequential).

### Parallel opportunities
- None. All tasks are sequential (`Parallel: no`); no worktree isolation needed (Gate 6 = N/A).

---

## Implementation Strategy

### MVP (User Story 1)
1. Phase 1 T001–T002 (confirm unknowns).
2. Phase 2 (installer + registry) → validate in the Tools view → MVP shippable.

### Incremental delivery
1. Spike → confirmed unknowns + proxy verdict.
2. US1 → Tools-view install (MVP).
3. US2 → opt-in MCP registration.
4. Docs + deploy + verify + audit → commit.

---

## Notes
- Owner field maps each task to a subagent from `.specify/memory/agents.md`.
- No protocol contract tests: Headroom owns its MCP tool schemas; we register the server via existing machinery (Gate 3 = N/A).
- Recompute each phase `**Status**:` line whenever `[X]` checkboxes change during `/speckit-implement`.
- Commit at plan-completion checkpoint per the repo's git rules (one feature commit for the 009 spec-kit artifacts; per-task commits during implement).
