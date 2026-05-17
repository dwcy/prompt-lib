# Research: GitHub Issue Triage Orchestrator (v1)

**Feature**: 003-issue-triage  
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## R1 — TriggerEvent Model Extension

**Decision**: Extend `TriggerEvent.kind` Literal in `triggers/base.py` to add `"issue.opened"`. Issue-specific fields (`issue_number`, `title`, `body`, `labels`, `author`) go in the existing `payload: dict[str, Any]` field. The `pr_number` field on issue events is set to the `issue_number` value; `head_sha` is set to a sentinel `"0" * 40`. A `model_validator` skips the 40-char-hex constraint on `head_sha` when `kind == "issue.opened"`.

**Rationale**: Single type system avoids a parallel class hierarchy. `payload` is already present and untyped — issue fields fit naturally. The `pr_number`-as-`issue_number` sentinel allows the daemon's dispatch path to log a numeric identifier without a new field. The `head_sha` sentinel is ugly but contained to the trigger; the rest of the system ignores it for issue events.

**Alternatives considered**:
- Separate `IssueEvent` Pydantic model: cleaner typing but requires daemon to handle a union type (`TriggerEvent | IssueEvent`), widening the dispatch contract.
- Generic `OrchestratorEvent` base with subclasses: over-engineering for v1 where there are only two event kinds.

---

## R2 — Daemon Multi-Trigger Wiring

**Decision**: Extract the trigger-consume loop in `daemon.py` into a `_consume_trigger(trigger, dispatch_table)` coroutine. When `config.orchestrator_enable_issue_triage` is true, create a `GithubIssuesPollTrigger` and `IssueTiageAgent`, add `"issue.opened"` to the dispatch table, and `asyncio.gather` both trigger coroutines.

The dispatch table is `dict[str, Agent]` where `Agent` is a structural type (duck-typed — both `PrReviewAgent` and `IssueTiageAgent` expose `async def run(trigger_event)`).

**Rationale**: Minimum change to `daemon.py`. The existing bounded semaphore and graceful shutdown apply to all tasks regardless of trigger source.

**Alternatives considered**:
- Single merged async iterator: requires a custom `merge_async_iterators` util; more complex, no benefit for two sources.
- Separate daemon processes per trigger: operational overhead; defeats the single-binary goal.

---

## R3 — Duplicate Suppression (Cursor Table)

**Decision**: Add a `source` discriminator column to the existing `cursor` table (or use a separate `issue_cursor` table). Chosen: separate `issue_cursor` table with `(issue_number INTEGER PRIMARY KEY, triaged_at TEXT NOT NULL)` to avoid touching the PR cursor schema.

**Rationale**: Avoids a migration on the existing `cursor` table. `GithubIssuesPollTrigger` queries `issue_cursor` to skip already-triaged numbers. `IssueTiageAgent` inserts into `issue_cursor` on successful triage.

**Alternatives considered**:
- Extend `cursor` table with a `source` column: requires an `ALTER TABLE` migration in `eventlog.py`; risk of breaking existing deployments.
- Check event log for prior `triage.decision` events: works but requires a full table scan per issue per poll cycle.

---

## R4 — Triage Response Format

**Decision**: The triage prompt instructs the lead agent to return a JSON fenced code block as the final output:

```json
{
  "category": "bug",
  "severity": "P2",
  "assessment": "...",
  "routing": "@python-architect"
}
```

`issue_triage.py` extracts the first ` ```json ` block from the agent's concatenated output and parses it with `json.loads`. If parse fails or required keys are missing, the run is marked `run.failed`.

**Rationale**: Same pattern as structured agent outputs in other agents. Simple, no tool-call schema needed. Failure is loud (`run.failed`) not silent.

**Alternatives considered**:
- Tool-call / structured output: A2A v1 doesn't expose a tool-call surface for the delegate call; would require A2A v2 extension (ADR needed).
- Regex extraction: fragile; JSON parse is more robust.

---

## R5 — `gh issue list` Field Selection

**Decision**: 
```
gh issue list --json number,title,body,labels,author,createdAt,state \
  --repo <repo> --state open --limit 100
```

Fields used:
- `number` → cursor key, payload `issue_number`
- `title` → triage prompt
- `body` → triage prompt (truncated to 4000 chars in prompt to fit context)
- `labels[].name` → triage prompt, category hint
- `author.login` → triage prompt
- `createdAt` → logged in event payload
- `state` → filter; `open` only

**Rationale**: Matches the `gh issue list` JSON schema documented in `contracts/gh-issue-list.contract.md`. `updatedAt` not included in v1 because re-triage on edits is out of scope (R3).

---

## R6 — Routing Convention

**Decision**: `routing` is a free-form string in v1. Allowed values:
- `"self"` — triage complete, no referral
- `"@<agent-name>"` — referral (comment includes the mention)

The orchestrator does NOT validate `<agent-name>` against `agents.md` in v1 (that is v2 with an active dispatch). The comment posts the string as-is.

**Rationale**: Minimal. Validation would require loading `agents.md` at runtime, which is outside the orchestrator's current scope.
