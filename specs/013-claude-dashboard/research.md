# Research: Claude Session Dashboard

## Data Sources

### Decision: Primary data source is `~/.claude/projects/` transcript JSONL files
- **Rationale**: Claude Code persists full conversation transcripts as JSONL at `~/.claude/projects/<encoded-path>/<session-id>.jsonl`. Each assistant message includes a `usage` block with per-call token counts. This is the richest source of historical data and requires no new hooks.
- **Alternatives considered**: (a) New `SessionEnd` hook + SQLite — rejected because it only captures future sessions and requires hook infrastructure; (b) Stdin-only data from `statusline.py` — rejected because it's ephemeral, no persistence.

### Decision: Cost calculated from token counts × pricing table (not `costUSD`)
- **Rationale**: Token-based calculation is sufficient. Whether `costUSD` is present in transcripts is irrelevant — the service layer uses `usage.input_tokens`, `usage.output_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens` × the bundled pricing table for all cost estimates.
- **Alternatives considered**: Reading `costUSD` directly from log entries — rejected as unnecessary complexity; token math gives the same result and works consistently across all transcript versions.

### Decision: Skill invocations parsed from user message content
- **Rationale**: When a user types `/skill-name args`, the JSONL `user` message content starts with `/`. This pattern is reliable and doesn't require additional logging.
- **How to apply**: In `session_reader.py`, scan `type: "user"` messages; if `content` starts with `/`, split on first space to get skill name and args. Record as `SkillInvocation`.

### Decision: Agent dispatches parsed from `tool_use` entries
- **Rationale**: When Claude dispatches a subagent, it emits a `tool_use` log entry with `name: "Task"` (or `"Agent"`) and an `input` object containing `subagent_type` (or `description`) and `prompt`. This is the primary source for agent tracking.
- **How to apply**: In `session_reader.py`, scan `type: "tool_use"` messages where `name` is `"Task"`, `"Agent"`, or any tool that dispatches subagents. Extract `input.subagent_type` as agent name. The triggering skill or user message is the most recent user/tool message before this `tool_use`.

### Decision: Hook trigger data from write_audit.jsonl
- **Rationale**: `~/.claude/write_audit.jsonl` is an append-only log of all Write/Edit tool calls. Cross-referencing by timestamp with session transcript data links file changes to the session that caused them.
- **Limitation**: write_audit.jsonl has `ts`, `tool`, `path` only — no session ID. Cross-referencing requires timestamp overlap with session transcript timestamps.

## Log Format: `~/.claude/projects/` (assumed, verify on first run)

```text
~/.claude/projects/
└── C%3A%2Fprojects%2Ffoo/          <- URL-encoded project path
    ├── <session-uuid-1>.jsonl
    └── <session-uuid-2>.jsonl
```

Each `.jsonl` file contains one JSON object per line. Known message types:

| type | Fields | Notes |
|---|---|---|
| `user` | `role`, `content` (string or array) | User messages; `/skill` commands detected here |
| `assistant` | `role`, `content`, `usage`, `model` | `usage` has token counts; `model` is model ID |
| `tool_use` | `id`, `name`, `input` | Agent dispatches when `name=Task/Agent` |
| `tool_result` | `tool_use_id`, `content`, `is_error` | Result of a tool call |
| `summary` | `summary` | Auto-generated session summary |

### `usage` block fields (per assistant message):
```json
{
  "input_tokens": 1234,
  "output_tokens": 567,
  "cache_read_input_tokens": 890,
  "cache_creation_input_tokens": 234
}
```

### Agent dispatch `tool_use` input example:
```json
{
  "name": "Task",
  "input": {
    "subagent_type": "python-architect",
    "description": "Implement session reader service",
    "prompt": "...",
    "isolation": "worktree"
  }
}
```

## Pricing Table

Decision: Bundle a static pricing dict in `pricing.py` keyed by model ID. Users can override with a JSON file at `~/.claude/dashboard-pricing.json`.

| Model ID | Input ($/MTok) | Output ($/MTok) | Cache Read ($/MTok) | Cache Write ($/MTok) |
|---|---|---|---|---|
| `claude-sonnet-4-6` | $3.00 | $15.00 | $0.30 | $3.75 |
| `claude-opus-4-8` | $15.00 | $75.00 | $1.50 | $18.75 |
| `claude-haiku-4-5-*` | $0.80 | $4.00 | $0.08 | $1.00 |
| `claude-fable-5` | $3.00 | $15.00 | $0.30 | $3.75 |

Prefix-match by model ID (e.g., `claude-sonnet-4-6` matches `claude-sonnet-4-6-20251022`). Fall back to `unknown` entry ($0/$0) with a UI warning.

## Existing Patterns to Reuse

- **`global/hooks/post_tool_use.py`** — session state read/write pattern (atomic file update)
- **`global/statusline.py`** — cost color thresholds, quota rendering logic
- **`setup/src/cabal/widgets/claude_stats_panel.py`** — `ClaudeAccountStatus` dataclass pattern
- **`setup/src/cabal/web/api.py`** — async endpoint structure, error handling
- **`specs/008-project-dashboard/data-model.md`** — dashboard snapshot patterns
- **`specs/011-cabal-web-ui/`** — Cabal TUI screen structure and navigation patterns

## NEEDS CLARIFICATION (resolved)

1. **Are costUSD values in transcripts?** — Plan A: yes (read directly). Plan B: calculate from tokens × pricing. Both implemented; Plan A tried first, Plan B fallback.
2. **Dashboard location: TUI or web?** — TUI (Textual). The existing Cabal app in `setup/src/cabal/` is the integration target, matching the project stack.
3. **Delete scope** — deletes the entire session directory from `~/.claude/projects/<path>/<session-id>.jsonl`. Does not delete the parent project directory.
