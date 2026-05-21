# Implementation Plan: GitHub Issue Triage Orchestrator (v1)

**Branch**: `feat/003-issue-triage` | **Date**: 2026-05-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-issue-triage/spec.md`

## Summary

Extend the existing `services/orchestrator/` service with a GitHub Issues trigger and a lead-agent triage pipeline. When `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=true`, the daemon also polls `gh issue list --json` at the configured interval, dispatches each new issue to a peer Claude Code agent for structured triage (category / severity / assessment / routing), posts the decision as a `gh issue comment`, suppresses re-triage via a new `issue_cursor` SQLite table, and sends ntfy.sh push notifications at each step. All changes are additive — existing PR-review behaviour is unaffected when the flag is off (default).

## Technical Context

**Language/Version**: Python 3.13 (same as 002)
**Primary Dependencies**: All existing (`typer`, `httpx`, `pydantic`, `pydantic-settings`, `textual`, `rich`); no new pip dependencies. External CLI: `gh` (existing).
**Storage**: Same SQLite `events.db`; adds `issue_cursor` table (new `CREATE TABLE IF NOT EXISTS` in `eventlog.py` schema migration).
**Testing**: pytest + pytest-asyncio + pytest-httpx + existing `fake_gh` shim (extended to handle `gh issue list` and `gh issue comment` invocations).
**Target Platform**: Same as 002 (Windows 10/11 primary, Linux/macOS supported).
**Project Type**: Extension to existing CLI service — no new entry point.
**Performance Goals**: Poll-to-notification ≤ poll_seconds + 5 s (SC-101); triage posted ≤ 90 s for issues under 2000 chars (SC-102).
**Constraints**: Opt-in flag; no breaking change to 002 behaviour; no new global skill/agent; no `.env` files.
**Scale/Scope**: Same single-operator, single-repo scope as 002. ~5–20 issues/day typical.

## Constitution Check

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: PASS. New external surface: `gh issue list --json` (consumer only) documented in [`contracts/gh-issue-list.contract.md`](./contracts/gh-issue-list.contract.md). Existing surfaces (`gh pr list`, ntfy.sh, A2A v1.0.0) are reused unchanged — conformance owned by 001 and 002 respectively.
- **Gate 2 — Subagent Delegation**: PASS. Delegation table below maps every phase to a named owner.
- **Gate 3 — Contract Tests Before Implementation**: PASS. `tests/contract/test_gh_issue_list_schema.py` must be written (and observed failing) before `github_issues_poll.py` implementation begins. ntfy and A2A contract tests already exist from 002.
- **Gate 4 — Reversible Config Changes**: N/A. No `global/` changes. All new code lives under `services/orchestrator/`.
- **Gate 5 — Minimal Skill & Agent Surface**: N/A. No new global skill or agent added. The "lead agent" is the existing peer Claude Code process (same A2A DelegationClient target as 002).
- **Gate 6 — Parallel Isolation**: N/A. Tasks are dispatched sequentially per agent type; no two writing subagents run concurrently within a phase.

No gate violations.

## Subagent Delegation

| Phase / concern | Owner | Why |
|---|---|---|
| `triggers/base.py` — extend `TriggerEvent.kind` Literal + model_validator | `@python-architect` | Pydantic model change; must not break existing PR events |
| `triggers/github_issues_poll.py` — new trigger (NEW FILE) | `@python-architect` | Mirror `github_poll.py`; async polling + cursor queries |
| `agents/issue_triage.py` — new agent (NEW FILE) | `@python-architect` | Mirror `pr_review.py`; delegation + JSON parse + gh comment |
| `config.py` — add `orchestrator_enable_issue_triage: bool = False` | `@python-architect` | pydantic-settings extension |
| `eventlog.py` — add `issue_cursor` table to schema migration | `@python-architect` | SQLite schema change |
| `daemon.py` — wire issue trigger + agent when flag enabled | `@python-architect` | asyncio service composition |
| Contract test: `tests/contract/test_gh_issue_list_schema.py` (NEW) | `@python-tester` | Gate 3 wire-format conformance; must precede implementation |
| Unit tests: `test_github_issues_poll.py`, `test_issue_triage.py` (NEW) | `@python-tester` | pytest + extended `fake_gh` shim |
| Integration test: `test_p5_issue_triage_end_to_end.py` (NEW) | `@python-tester` | Real subprocess + real test repo, gated by `INTEGRATION=1` |
| Spec artifacts (spec.md, research.md, data-model.md, contracts/, quickstart.md) | `main` | Cross-cutting; already produced by `/speckit-plan` |
| CLAUDE.md SPECKIT block update | `main` | Agent context pointer |
| Plan-conformance audit before commit | `@code-plan-verifier` | Constitution gate before pushing |

### Parallel Execution Map

N/A — all phases are sequential; no two writing subagents dispatched concurrently.

## Project Structure

### Documentation (this feature)

```
specs/003-issue-triage/
├── plan.md              ← This file
├── research.md          ← Phase 0 (complete)
├── data-model.md        ← Phase 1 (complete)
├── quickstart.md        ← Phase 1 (complete)
├── contracts/
│   └── gh-issue-list.contract.md   ← Phase 1 (complete)
└── tasks.md             ← Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code Changes (all within `services/orchestrator/`)

```
services/orchestrator/src/orchestrator/
├── triggers/
│   ├── base.py                        MODIFY — extend kind Literal + model_validator
│   └── github_issues_poll.py          NEW — GithubIssuesPollTrigger
├── agents/
│   └── issue_triage.py                NEW — IssueTiageAgent
├── config.py                          MODIFY — add orchestrator_enable_issue_triage
├── eventlog.py                        MODIFY — add issue_cursor table to schema
└── daemon.py                          MODIFY — wire issue trigger + agent when flag=true

services/orchestrator/tests/
├── contract/
│   └── test_gh_issue_list_schema.py   NEW — Gate 3 contract test (written first)
├── unit/
│   ├── test_github_issues_poll.py     NEW
│   └── test_issue_triage.py           NEW
└── integration/
    └── test_p5_issue_triage_end_to_end.py   NEW (INTEGRATION=1 gated)
```

**Unchanged**: `pr_review.py`, `dashboard/app.py`, `notifier.py`, `worktree.py`, `cli.py`, `triggers/__init__.py`, all existing tests, all contracts for gh pr list / ntfy / A2A.

## Implementation Notes

### `triggers/base.py` change

```python
# Before:
kind: Literal["pr.opened", "pr.updated"]

# After:
kind: Literal["pr.opened", "pr.updated", "issue.opened"]

# Add model_validator:
@model_validator(mode="after")
def _validate_head_sha_for_kind(self) -> "TriggerEvent":
    if self.kind != "issue.opened":
        assert len(self.head_sha) == 40 and all(c in "0123456789abcdef" for c in self.head_sha)
    return self
```

### `github_issues_poll.py` key logic

```python
_GH_LIST_ARGS = [
    "issue", "list",
    "--json", "number,title,body,labels,author,createdAt,state",
    "--state", "open",
    "--limit", "100",
]
# Cursor query: SELECT issue_number FROM issue_cursor WHERE repo = ?
# Emit TriggerEvent(kind="issue.opened", repo=repo, pr_number=issue_number,
#                   head_sha="0"*40, payload={issue fields})
```

### `issue_triage.py` key logic

1. Extract issue fields from `trigger_event.payload`
2. Build prompt: system instruction + issue title/body/labels/author
3. Stream `client.delegate(prompt)` — collect output
4. Parse first ` ```json ` block → `TriageDecision`
5. `gh issue comment <n> --repo <repo> --body -` (stdin)
6. `INSERT OR REPLACE INTO issue_cursor ...`
7. Log events; notify via ntfy

### `daemon.py` minimal wiring

```python
# Existing:
trigger = GithubPollTrigger(...)
agent = PrReviewAgent(...)
dispatch = {"pr.opened": agent, "pr.updated": agent}
tasks = [asyncio.create_task(_consume_trigger(trigger, dispatch, stop_event))]

# Addition when config.orchestrator_enable_issue_triage:
issue_trigger = GithubIssuesPollTrigger(...)
issue_agent = IssueTiageAgent(...)
dispatch["issue.opened"] = issue_agent
tasks.append(asyncio.create_task(_consume_trigger(issue_trigger, dispatch, stop_event)))

await asyncio.gather(*tasks, return_exceptions=True)
```

The `_consume_trigger` helper is extracted from the existing `_consume()` function — same semaphore, same `_run_one` logic.

## Complexity Tracking

No gate violations. Table empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | (none) | (none) |
