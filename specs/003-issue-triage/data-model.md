# Data Model: GitHub Issue Triage Orchestrator (v1)

**Feature**: 003-issue-triage

---

## Entities

### IssueEvent

Represented as a `TriggerEvent` with `kind="issue.opened"`. Extends the existing model rather than introducing a new class.

| Field | Type | Source | Notes |
|---|---|---|---|
| `kind` | `Literal["issue.opened"]` | trigger | New literal added to `TriggerEvent.kind` |
| `repo` | `str` | trigger | `owner/repo` slug (same as PR events) |
| `pr_number` | `int` | trigger | Set to `issue_number` (sentinel reuse) |
| `head_sha` | `str` | trigger | `"0" * 40` sentinel; validator skipped for issue kind |
| `detected_at` | `datetime` | trigger | UTC timestamp of poll detection |
| `payload.issue_number` | `int` | gh CLI | Issue number (also stored as `pr_number`) |
| `payload.title` | `str` | gh CLI | Issue title |
| `payload.body` | `str` | gh CLI | Issue body (may be empty string) |
| `payload.labels` | `list[str]` | gh CLI | Label names extracted from `labels[].name` |
| `payload.author` | `str` | gh CLI | `author.login` from gh JSON |
| `payload.created_at` | `str` | gh CLI | ISO-8601 string from `createdAt` |

---

### TriageDecision

Parsed from the lead agent's structured JSON output. Internal to `IssueTiageAgent.run()`. Not persisted directly — its fields are stored in the `triage.decision` event payload.

| Field | Type | Constraint |
|---|---|---|
| `category` | `str` | One of: `bug`, `feature`, `question`, `infra`, `other` |
| `severity` | `str` | One of: `P1`, `P2`, `P3`, `P4` |
| `assessment` | `str` | Free text, one paragraph |
| `routing` | `str` | `"self"` or `"@<agent-name>"` |

---

### IssueCursor (new SQLite table)

Tracks which issues have been triaged. Created by `eventlog.py` schema migration alongside the existing `cursor` table.

```sql
CREATE TABLE IF NOT EXISTS issue_cursor (
    issue_number INTEGER PRIMARY KEY,
    repo         TEXT    NOT NULL,
    triaged_at   TEXT    NOT NULL  -- ISO-8601 UTC
);
```

`GithubIssuesPollTrigger` queries: `SELECT issue_number FROM issue_cursor WHERE repo = ?`  
`IssueTiageAgent` inserts: `INSERT OR REPLACE INTO issue_cursor (issue_number, repo, triaged_at) VALUES (?, ?, ?)`

---

## Event Kinds (new additions to existing event log)

| Kind | Emitted by | Payload fields |
|---|---|---|
| `issue.detected` | `GithubIssuesPollTrigger` | `issue_number`, `title`, `repo` |
| `run.queued` | `IssueTiageAgent` | `issue_number`, `repo` |
| `run.started` | `IssueTiageAgent` | `issue_number` |
| `agent.message` | `IssueTiageAgent` | `text` (streamed chunk) |
| `triage.decision` | `IssueTiageAgent` | `category`, `severity`, `assessment`, `routing` |
| `triage.routed` | `IssueTiageAgent` | `routing` (when not `"self"`) |
| `gh.comment.posted` | `IssueTiageAgent` | `issue_number`, `comment_url` |
| `gh.comment.failed` | `IssueTiageAgent` | `stderr`, `exit_code` |
| `run.skipped` | `GithubIssuesPollTrigger` | `issue_number`, `reason: "already_triaged"` |
| `run.completed` | `IssueTiageAgent` | `issue_number`, `duration_s` |
| `run.failed` | `IssueTiageAgent` | `issue_number`, `error` |

Existing event kinds (`run.started`, `run.completed`, `run.failed`, `agent.message`) are reused where semantics match exactly.

---

## State Transitions

```
                      poll detects new issue
                              │
                    ┌─────────▼──────────┐
                    │  issue.detected     │
                    └─────────┬──────────┘
                              │
               ┌──────────────▼────────────────┐
               │  already in issue_cursor?       │
               │  YES → run.skipped             │
               │  NO  → run.queued              │
               └──────────────┬────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  run.started        │
                    │  delegate(prompt)   │
                    └─────────┬──────────┘
                              │
               ┌──────────────▼────────────────┐
               │  agent response parseable?      │
               │  NO  → run.failed              │
               │  YES → triage.decision         │
               └──────────────┬────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  gh issue comment   │
                    │  (non-fatal)        │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  insert issue_cursor│
                    │  run.completed      │
                    └────────────────────┘
```
