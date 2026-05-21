# Feature Specification: GitHub Issue Triage Orchestrator (v1)

**Feature Branch**: `feat/003-issue-triage`
**Created**: 2026-05-12
**Status**: Draft
**Input**: Extends 002-agent-orchestrator with an issue-triage trigger. When a GitHub issue is opened on the watched repo, a lead developer agent reviews it, produces a structured triage decision, posts a comment, and notifies the operator's phone.

## Context

`specs/002-agent-orchestrator/spec.md` FR-014 required the trigger surface to be an abstract plug-in point so future trigger types (GitHub Issues, webhooks, manual dispatch) could be wired in without modifying the core dispatch pipeline. The Issue Triage feature is the first exercise of that abstraction.

The `services/orchestrator/` service is fully scaffolded. This feature adds:
- A new trigger: `GithubIssuesPollTrigger` (polls `gh issue list --json`)
- A new agent: `IssueTiageAgent` (calls DelegationClient, posts `gh issue comment`)
- Minimal additions to `config.py` and `daemon.py`

**Explicitly out of scope for v1**: auto-creating PRs or branches from issues, re-triage on issue edits, spawning the routed specialist agent automatically.

---

## User Scenarios & Testing

### User Story 1 — Issue Detection and Lead-Agent Triage (Priority: P1) 🎯 MVP

The operator has the orchestrator daemon running with `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=true`. A contributor opens a GitHub issue on the watched repo. Within the configured polling interval, the daemon detects the issue, dispatches it to a peer Claude Code agent (the "lead agent") with the issue content, and the agent returns a structured triage decision: category, severity, a one-paragraph assessment, and a routing recommendation.

**Independent Test**: Open an issue on the test repo. Within one poll interval, `gh issue view <n> --comments` shows a triage comment and the daemon event log contains `triage.decision`.

**Acceptance Scenarios**:
1. Given the daemon is running with issue triage enabled and a new issue is opened, when the next poll fires, then a `run.started` event is emitted and the issue is dispatched to the lead agent within one polling interval.
2. Given the lead agent returns `{category, severity, assessment, routing}`, when routing is `"self"`, then a `triage.decision` event is emitted and the run completes successfully.
3. Given routing is `"@<agent-name>"`, then a `triage.routed` event is emitted naming the target agent, and the run completes.
4. Given the agent returns an unparseable response, then `run.failed` is emitted and no comment is posted.

---

### User Story 2 — GitHub Comment with Triage Summary (Priority: P2)

After a successful triage run, the daemon posts a structured comment on the GitHub issue via `gh issue comment`, summarizing the category, severity, assessment, and routing recommendation.

**Acceptance Scenarios**:
1. Given a successful triage, `gh issue view <n> --comments` shows a comment with the triage fields.
2. Given routing names a specialist agent, the comment includes the routing suggestion.
3. Given `gh issue comment` exits non-zero, the daemon emits `gh.comment.failed` as a non-fatal warning and still marks the run completed.

---

### User Story 3 — Phone Push Notifications (Priority: P2)

The operator receives ntfy.sh push notifications at each triage step: issue detected, triage complete, triage failed. Each notification includes the issue number, title, and outcome.

**Acceptance Scenarios**:
1. Given a subscribed ntfy topic, when an issue is detected, the phone receives an info-level notification with issue number and title within 5 seconds.
2. Given triage completes, the phone receives an info-level notification with category and routing.
3. Given triage fails, the phone receives an error-level (high priority) notification with a one-line failure reason.

---

### User Story 4 — Duplicate Suppression (Priority: P3)

If an issue has already been successfully triaged, the daemon does not dispatch a second triage run for it on subsequent polls.

**Acceptance Scenarios**:
1. Given an issue was triaged in a prior run, when the next poll detects the same issue number, a `run.skipped` event is emitted with reason `already_triaged` and no dispatch occurs.
2. Given an issue is subsequently edited, the daemon does NOT retriage in v1 (issues lack a head-SHA update signal).

---

### Edge Cases

- Issue closed between detection and comment posting: `gh issue comment` succeeds or fails; treated normally per US2 scenario 3.
- Lead agent returns partial JSON: parse fails → `run.failed`.
- `gh issue list` rate-limited: emit `gh.rate_limited` event; retry on next poll cycle.
- Both PR review and issue triage enabled simultaneously: each trigger runs its own async loop; events are independent.
- `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=false` (default): no `GithubIssuesPollTrigger` is created; daemon behaviour is identical to 002 v1.

---

## Requirements

### Functional Requirements

- **FR-101**: System MUST detect newly-opened GitHub issues on the configured repository within the configured polling interval using `gh issue list --json`.
- **FR-102**: System MUST dispatch each new issue (number, title, body, labels, author) to a peer Claude Code agent via the existing A2A DelegationClient.
- **FR-103**: The dispatched agent MUST return a structured response parseable as `{category, severity, assessment, routing}`.
- **FR-104**: System MUST post a structured comment on the GitHub issue via `gh issue comment` on successful triage.
- **FR-105**: System MUST treat `gh issue comment` failures as non-fatal.
- **FR-106**: System MUST suppress re-dispatch for already-triaged issue numbers (cursor table).
- **FR-107**: System MUST send ntfy.sh push notifications at issue detection, triage completion, and triage failure.
- **FR-108**: System MUST extend `TriggerEvent.kind` to include `"issue.opened"` without breaking existing `"pr.opened"` / `"pr.updated"` events.
- **FR-109**: System MUST expose the issues trigger via the existing `Trigger` Protocol.
- **FR-110**: System MUST record all issue-triage state transitions in the existing SQLite event log.
- **FR-111**: System MUST NOT auto-create PRs, branches, or code changes from issues in v1.
- **FR-112**: System MUST read all config from process environment; no `.env` files written or read.
- **FR-113**: Issue triage MUST be opt-in via `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE` (default `false`) so existing 002 deployments are unaffected.

### Key Entities

- **IssueEvent**: A `TriggerEvent` with `kind="issue.opened"` and issue fields (`issue_number`, `title`, `body`, `labels`, `author`) in `payload`.
- **TriageDecision**: Parsed agent output — `category`, `severity`, `assessment`, `routing`.
- **IssueCursor**: Entry in SQLite `cursor` table tracking per-issue triage state (`source='issue'`, `key=issue_number`, `triaged_at`).

---

## Success Criteria

- **SC-101**: From `gh issue create` to phone notification, no more than the configured poll interval + 5 seconds.
- **SC-102**: From issue detection to comment posted, no more than 90 seconds for issues with body under 2000 chars.
- **SC-103**: A simulated agent failure produces an error-level phone notification, a `run.failed` event, and zero comments posted — in 100% of attempts across 5 trials.
- **SC-104**: With `ORCHESTRATOR_ENABLE_ISSUE_TRIAGE=false` (or unset), the daemon behaviour is identical to 002 v1 — no new code paths run.

## Assumptions

- The operator uses the same `gh` credentials and `ORCHESTRATOR_REPO` as 002.
- The peer Claude Code A2A adapter is already running (same as 002).
- The `ntfy` topic and subscription are already configured (same as 002).
- "Routing" in v1 means a comment recommendation only — the orchestrator does not spawn the named agent.
- The issue triage agent prompt is hardcoded in `issue_triage.py` for v1; a configurable prompt is v2.
