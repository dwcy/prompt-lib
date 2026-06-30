# Feature Specification: Claude Session Dashboard

**Feature Branch**: `feat/013-claude-dashboard`  
**Created**: 2026-06-30  
**Status**: Draft  
**Input**: User description: "I would like to have a claude dashboard with possibility to remove sessions, I want to see usage, tokens sessions, spending per sessions, agents used per session, agents used per session. and everything from the logs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Session Overview Dashboard (Priority: P1)

The user opens the Cabal TUI and navigates to a "Sessions" or "Dashboard" view where they can see all their Claude Code sessions with high-level metrics: total tokens used, estimated cost, duration, and which agents were invoked.

**Why this priority**: This is the core value. Without a sessions list with metrics, nothing else is possible. Every other story builds on this view.

**Independent Test**: Open the Cabal TUI, navigate to Sessions screen, observe a table listing sessions with token counts, cost estimates, and agent names. Delivers standalone value as a read-only analytics view.

**Acceptance Scenarios**:

1. **Given** the Cabal TUI is open, **When** the user navigates to the Sessions view, **Then** a list of sessions is shown, each row showing: session ID/name, date, total input tokens, total output tokens, estimated cost, and the number of agents used.
2. **Given** sessions are listed, **When** the user selects a session, **Then** a detail panel shows all log entries for that session including per-agent breakdown, tool calls, and message counts.
3. **Given** multiple sessions exist, **When** the view loads, **Then** sessions are ordered newest-first by default.

---

### User Story 2 — Session Deletion (Priority: P2)

The user can select one or more sessions from the dashboard and permanently delete their log data from disk.

**Why this priority**: Disk management and privacy control. Blocked on US1 (sessions must be listed before they can be deleted). Deleting removes the underlying log directory/file from `~/.claude/projects/`.

**Independent Test**: Select a session in the Sessions view, press Delete/D, confirm deletion prompt, session disappears from list and its directory is removed from disk.

**Acceptance Scenarios**:

1. **Given** a session is selected, **When** the user presses the delete key or delete button, **Then** a confirmation dialog appears warning that logs will be permanently deleted.
2. **Given** the user confirms deletion, **When** the delete executes, **Then** the session's log directory is removed from `~/.claude/projects/<encoded-path>/`, the session disappears from the list, and aggregate totals update.
3. **Given** the user cancels the confirmation dialog, **When** the cancel is pressed, **Then** nothing is deleted and the session remains in the list.

---

### User Story 3 — Spending & Token Analytics (Priority: P2)

The user sees aggregate and per-session spending calculated from Claude API pricing (input/output/cache token pricing per model) extracted from the log JSONL files.

**Why this priority**: The core reason to have a dashboard — understanding cost. Requires parsing pricing from model metadata in logs. Blocked on US1 infrastructure.

**Independent Test**: Navigate to Sessions view, see a "Cost" column with USD values per session, see a summary total at the bottom. The values match manual calculation from the log data.

**Acceptance Scenarios**:

1. **Given** log data contains model identifiers and token counts, **When** the Sessions view loads, **Then** estimated cost per session is shown using the model's current input/output token pricing.
2. **Given** multiple sessions are shown, **When** the user looks at the view footer, **Then** total tokens (input + output) and total estimated cost across all visible sessions are displayed.
3. **Given** a session used multiple models (e.g., Sonnet in sub-agents), **When** the user views session detail, **Then** cost is broken down per model used.

---

### User Story 4 — Agents, Skills & Triggers Per Session (Priority: P3)

For each session, the user can see which subagent types were invoked, which skills were called, and what triggered each invocation — with token consumption per agent.

**Why this priority**: Advanced analytics — depends on US1 and US3. Requires parsing `tool_use` events (agent dispatches) and user message content (skill invocations starting with `/`) from the JSONL logs.

**Independent Test**: Select a session in the detail view, see a table of agents (e.g., `python-architect`, `react-architect`), skills invoked (e.g., `/speckit-plan`, `/code-review`), and what triggered each (the user message or parent tool call).

**Acceptance Scenarios**:

1. **Given** a session log contains `tool_use` entries with name `"Task"`, **When** the user opens session detail, **Then** a per-agent breakdown shows: agent type, invocation count, tokens consumed, and the triggering prompt/action.
2. **Given** a session log contains user messages starting with `/`, **When** the user views session detail, **Then** a skills panel shows each skill invoked with timestamp, the args passed, and which agent (if any) it dispatched.
3. **Given** the sessions list is visible, **When** the user looks at the "Agents" column, **Then** a count of distinct agent types used in that session is shown.
4. **Given** a session used hooks (e.g., write_audit, post_tool_use), **When** the user views session detail, **Then** a triggers panel shows each hook event with timestamp, tool that fired it, and outcome.

---

### User Story 5 — Raw Log Viewer (Priority: P4)

The user can inspect the raw JSONL log entries for any session, filtered by message type, directly within the TUI.

**Why this priority**: Power-user feature for debugging. Lowest priority since the structured views in US1–US4 already surface all key data.

**Independent Test**: Open a session detail, switch to "Raw Logs" tab, see a scrollable list of JSONL entries with optional type filter.

**Acceptance Scenarios**:

1. **Given** a session is selected, **When** the user activates the "Logs" tab in the detail panel, **Then** raw log entries are displayed with timestamps, message types, and content.
2. **Given** raw logs are shown, **When** the user selects a message type filter (e.g., "assistant", "tool_result", "tool_use"), **Then** only entries of that type are shown.

---

### Edge Cases

- What happens when a session log file is corrupt or partially written (still in-progress)?
- What happens when `~/.claude/projects/` is empty or does not exist?
- What if a session log references a model that is not in the pricing table?
- What if a session log is very large (10k+ entries) — does the TUI remain responsive?
- What happens when the user deletes the currently-viewed session?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read session log data from `~/.claude/projects/` JSONL files.
- **FR-002**: System MUST parse token counts (input, output, cache read, cache write) from log entries.
- **FR-003**: System MUST calculate estimated cost per session using model pricing from a bundled pricing table.
- **FR-004**: System MUST display a sessions list with: session identifier, date, token totals (input/output), estimated cost, agent count.
- **FR-005**: System MUST display a per-session detail view with agent breakdown (name, call count, tokens).
- **FR-006**: System MUST allow deleting a session (removes `~/.claude/projects/<path>/` from disk) after user confirmation.
- **FR-007**: System MUST display aggregate totals (all-time tokens + cost) in the sessions view.
- **FR-008**: System MUST display raw JSONL log entries for a selected session.
- **FR-009**: Pricing table MUST be updatable without code changes (bundled config file).
- **FR-010**: Session list MUST be sortable by date, cost, and token count.
- **FR-011**: System MUST display which skills were invoked per session (user messages matching `/skill-name` pattern).
- **FR-012**: System MUST display which agents were dispatched per session and what triggered each dispatch (the tool call input or skill).
- **FR-013**: System MUST display hook trigger events per session from `~/.claude/write_audit.jsonl` and session state data.

### Key Entities

- **Session**: A directory under `~/.claude/projects/<encoded-project-path>/` containing one or more JSONL log files representing a single conversation/session.
- **LogEntry**: A single JSONL line in a session file with fields: `type`, `timestamp`, `message`, `costUSD`, `model`, `usage` (inputTokens, outputTokens, cacheReadInputTokens, cacheCreationInputTokens).
- **AgentInvocation**: A `tool_use` log entry with `name: "Task"` or `"Agent"`, capturing subagent type, the triggering prompt, and its associated tokens.
- **SkillInvocation**: A user message starting with `/` parsed as `/<skill-name> [args]`, capturing skill name, args, timestamp, and which agent it caused to be dispatched.
- **TriggerEvent**: Any hook-triggered event (write_audit entry, post_tool_use counter update) with timestamp, tool name, and context.
- **PricingEntry**: Model pricing configuration: model ID, input price per MTok, output price per MTok, cache read/write prices.
- **SessionSummary**: Aggregated view of a Session: total tokens (by type), total cost, agent breakdown, skills used, date range.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sessions view loads and renders with data within 2 seconds for up to 500 sessions.
- **SC-002**: Token and cost calculations match manual calculation from log data (within 1% rounding tolerance).
- **SC-003**: Session deletion removes the correct directory on disk and updates the UI without requiring restart.
- **SC-004**: All existing Cabal TUI navigation and features continue to work unchanged after this feature is added.

## Assumptions

- Log files are located at `~/.claude/projects/<url-encoded-path>/<session-id>.jsonl` or similar structure; exact path is confirmed via Phase 0 research.
- Cost data may also be directly available as `costUSD` fields in log entries (rather than requiring manual calculation from token counts + pricing table) — to be confirmed in research.
- This feature is implemented as a new screen/view in the existing Cabal Textual TUI (`cabal/`) — not a standalone web UI or CLI command.
- The feature is Python + Textual (same stack as the rest of Cabal), not a separate web app.
- Sessions are currently not indexed; the reader will scan `~/.claude/projects/` at startup (with caching for large installs).
- Mobile / web access to the dashboard is out of scope for v1.
