# Data Model: Claude Session Dashboard

## Entities

### Session
Represents a single Claude Code conversation stored on disk.

| Field | Type | Source | Notes |
|---|---|---|---|
| `session_id` | `str` | filename (UUID) | `<uuid>.jsonl` basename |
| `project_path` | `str` | parent dir name | URL-decoded from `~/.claude/projects/<encoded>/` |
| `start_time` | `datetime` | first log entry `timestamp` | |
| `end_time` | `datetime` | last log entry `timestamp` | |
| `log_path` | `Path` | filesystem | Absolute path to `.jsonl` file |
| `file_size_bytes` | `int` | filesystem | For UI display |

---

### LogEntry
One JSONL line from a session transcript.

| Field | Type | Source | Notes |
|---|---|---|---|
| `type` | `str` | `type` field | `"user"`, `"assistant"`, `"tool_use"`, `"tool_result"`, `"summary"` |
| `timestamp` | `datetime \| None` | `timestamp` field | May be absent on older entries |
| `role` | `str \| None` | `role` field | Present on `user`/`assistant` types |
| `content` | `str \| list \| None` | `content` field | String or content-block array |
| `model` | `str \| None` | `model` field | Present on `assistant` entries |
| `usage` | `TokenUsage \| None` | `usage` field | Present on `assistant` entries |
| `tool_name` | `str \| None` | `name` field | Present on `tool_use` entries |
| `tool_input` | `dict \| None` | `input` field | Present on `tool_use` entries |
| `is_error` | `bool` | `is_error` field | Present on `tool_result` entries |
| `cost_usd` | `float \| None` | `costUSD` field | Ignored — cost computed from tokens × pricing |

---

### TokenUsage
Token counts from a single API response.

| Field | Type | Notes |
|---|---|---|
| `input_tokens` | `int` | |
| `output_tokens` | `int` | |
| `cache_read_input_tokens` | `int` | 0 if absent |
| `cache_creation_input_tokens` | `int` | 0 if absent |

---

### AgentInvocation
Parsed from `tool_use` entries where `tool_name in ("Task", "Agent")`.

| Field | Type | Source | Notes |
|---|---|---|---|
| `agent_type` | `str` | `tool_input.subagent_type` | e.g., `"python-architect"` |
| `description` | `str` | `tool_input.description` | Short description of the task |
| `prompt_preview` | `str` | `tool_input.prompt[:200]` | First 200 chars of the agent prompt |
| `timestamp` | `datetime \| None` | parent `LogEntry.timestamp` | |
| `isolation` | `str \| None` | `tool_input.isolation` | `"worktree"` if set |
| `triggered_by` | `str` | derived | Nearest preceding skill name or `"direct"` |

---

### SkillInvocation
Parsed from `user` messages where `content` starts with `/`.

| Field | Type | Source | Notes |
|---|---|---|---|
| `skill_name` | `str` | parsed from content | e.g., `"speckit-plan"` |
| `args` | `str` | remainder after skill name | May be empty |
| `timestamp` | `datetime \| None` | parent `LogEntry.timestamp` | |
| `agents_dispatched` | `list[str]` | derived | Agent types dispatched in the same session after this skill |

---

### TriggerEvent
Represents a hook-triggered event cross-referenced from `write_audit.jsonl`.

| Field | Type | Source | Notes |
|---|---|---|---|
| `timestamp` | `datetime` | `ts` field | |
| `tool` | `str` | `tool` field | `"Write"` or `"Edit"` |
| `path` | `str` | `path` field | Absolute file path modified |
| `session_id` | `str \| None` | derived | Session ID inferred from timestamp overlap |

---

### SessionSummary
Computed view of a Session for the sessions list.

| Field | Type | Derivation |
|---|---|---|
| `session_id` | `str` | from `Session` |
| `project_path` | `str` | from `Session` |
| `start_time` | `datetime` | from `Session` |
| `duration_seconds` | `float` | `end_time - start_time` |
| `total_input_tokens` | `int` | sum of all `LogEntry.usage.input_tokens` |
| `total_output_tokens` | `int` | sum of all `LogEntry.usage.output_tokens` |
| `total_cache_read_tokens` | `int` | sum of `cache_read_input_tokens` |
| `total_cache_write_tokens` | `int` | sum of `cache_creation_input_tokens` |
| `estimated_cost_usd` | `float` | tokens × pricing table (input + output + cache read + cache write) |
| `model_breakdown` | `dict[str, TokenUsage]` | per-model token totals |
| `agent_count` | `int` | count of `AgentInvocation` entries |
| `agents` | `list[AgentInvocation]` | all agent dispatches |
| `skills` | `list[SkillInvocation]` | all skill invocations |
| `message_count` | `int` | count of `user` + `assistant` entries |

---

### PricingEntry

| Field | Type | Notes |
|---|---|---|
| `model_prefix` | `str` | Matched by `startswith()` against model ID |
| `input_usd_per_mtok` | `float` | |
| `output_usd_per_mtok` | `float` | |
| `cache_read_usd_per_mtok` | `float` | |
| `cache_write_usd_per_mtok` | `float` | |

---

## Service Layer

### `session_reader.py` functions

```python
def scan_projects_dir(projects_dir: Path) -> list[Session]
    """Enumerate all sessions across all projects under ~/.claude/projects/"""

def read_session(session: Session) -> list[LogEntry]
    """Parse all JSONL lines from a session file"""

def compute_summary(session: Session, entries: list[LogEntry], pricing: list[PricingEntry]) -> SessionSummary
    """Aggregate tokens, cost, agents, skills from parsed entries"""

def delete_session(session: Session) -> None
    """Remove the .jsonl file from disk"""

def read_write_audit(audit_path: Path, since: datetime | None = None) -> list[TriggerEvent]
    """Parse ~/.claude/write_audit.jsonl into TriggerEvent list"""
```

## State Transitions

```
Session lifecycle in dashboard:
  Listed → Selected → Detail view
  Listed → Delete confirmed → Removed from disk + list
  Selected → Tab: Overview | Agents & Skills | Raw Logs | Triggers
```
