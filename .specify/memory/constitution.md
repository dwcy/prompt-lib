<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR — Principle II extended with a parallel-isolation clause requiring worktree isolation for concurrent writing subagents. Adds a binding rule without removing or redefining any existing principle.

Modified principles:
  II. Subagent Delegation → adds "Parallel isolation" clause and a new Constitution Check Gate 6

Added sections:
  - Constitution Check Gate 6 — Parallel Isolation (in Development Workflow & Quality Gates)

Removed sections: none

Templates requiring updates:
  ⬜ .specify/templates/plan-template.md — add Parallel Execution Map sub-section under Subagent Delegation; add Gate 6 to Constitution Check
  ⬜ .specify/templates/tasks-template.md — extend Format line with `Parallel: yes/no`; add worktree directive
  ✅ .specify/templates/spec-template.md — no change needed
  ⬜ .specify/memory/agents.md — add Parallel isolation subsection and example
  ⬜ docs/parallel-isolation.md — canonical explainer (to be added)

Follow-up TODOs: propagate template edits and docs explainer in the same PR as this amendment.

----- Previous report (v0.0.0 → 1.0.0) -----
Version change: 0.0.0 (template) → 1.0.0 (initial ratification)
Bump rationale: First concrete fill of placeholder template; establishes governance for spec-driven A2A bridge work.
Modified principles:
  [PRINCIPLE_1] → I. Spec-First Conformance (NON-NEGOTIABLE)
  [PRINCIPLE_2] → II. Subagent Delegation
  [PRINCIPLE_3] → III. Contract Tests Before Implementation
  [PRINCIPLE_4] → IV. Reversible Config Changes
  [PRINCIPLE_5] → V. Minimal Skill & Agent Surface
Added sections:
  - Repository Structure & Deployment
  - Development Workflow & Quality Gates
Templates updated: plan-template.md, tasks-template.md, agents.md.
-->

# prompt-lib Constitution

## Core Principles

### I. Spec-First Conformance (NON-NEGOTIABLE)

When implementing an external protocol (A2A, MCP, JSON-RPC, OpenAPI, etc.), the published spec is authoritative. Implementations MUST conform exactly. Any deviation — extension, omission, or reinterpretation — requires an ADR (in `.specify/specs/<feature>/contracts/` or `docs/adr/`) documenting:

- What part of the spec is deviated from
- Why the deviation is necessary
- What compatibility is broken and with whom

Silent deviation is forbidden. Contract tests (see Principle III) MUST cover the conforming surface before any code that talks to peers ships.

### II. Subagent Delegation

Any task with a domain-specific specialist agent listed in `.specify/memory/agents.md` MUST be delegated to that agent during `/speckit-implement`. The main thread is responsible for orchestration, ADRs, and cross-cutting glue only — never inline work that has a specialist owner.

- `tasks.md` MUST include `Owner: @<agent>` on every task line.
- `Owner: main` is allowed only when no specialist matches; the reason MUST be stated.
- Architecture work goes to the matching `*-architect`; tests go to the matching `*-tester`; CSS-only work goes to `@frontend-css` regardless of framework.

**Parallel isolation** (added in v1.1.0): when two or more subagents are dispatched to operate concurrently on the same repository, every writing agent MUST run in an isolated git worktree. The dispatcher passes `isolation: "worktree"` on the Agent tool call, or pre-creates the worktree via `/using-git-worktrees create` and briefs the agent with its path. Read-only agents are exempt; sequential single-agent dispatch is exempt. Tasks that will be executed in parallel MUST be marked `Parallel: yes` in `tasks.md` so `/speckit-implement` selects worktree dispatch for them. See [`docs/parallel-isolation.md`](../../docs/parallel-isolation.md) for the full rule.

### III. Contract Tests Before Implementation

For any protocol surface (A2A endpoints, agent cards, JSON-RPC methods, REST contracts, MCP tool schemas), contract tests MUST be written and observed failing before the implementation begins. This rule is binding on protocol surfaces only — unit tests remain optional and at the author's discretion.

- Contract tests live under `tests/contract/` (or the language equivalent).
- Each test MUST exercise the wire format the spec defines, not the in-process function signature.
- Implementation tasks for a protocol surface in `tasks.md` MUST be ordered after their contract test tasks.

### IV. Reversible Config Changes

This repo is the source of truth for `~/.claude/`. Any change under `global/` (skills, agents, hooks, `settings.json`) MUST be:

- Deployable via `python setup/apply.py` (or `setup/tools/apply-global-claude-settings.sh` as fallback).
- Revertable via the same flow — no one-way migrations to `~/.claude/`.
- Documented in the PR or ADR with the rollback path explicitly stated.

Hooks that modify global state irreversibly (e.g., wiping `~/.claude/`) are forbidden.

### V. Minimal Skill & Agent Surface

Don't add a new skill or agent if an existing one covers the use case. Before introducing anything that overlaps:

- Run `/review-conflicts` to surface duplicates.
- Prefer extending an existing skill or agent over creating a near-duplicate.
- Justify the addition in the PR description with what the existing surface cannot do.

Skill/agent proliferation degrades the harness — discoverability drops, conflicts multiply, context fills.

## Repository Structure & Deployment

- `global/` is the deploy source for `~/.claude/`. Edits here ship to every project on the machine after `setup/apply.py` runs.
- `.claude/` is project-local config for prompt-lib itself; it does not deploy globally.
- `.specify/` holds spec-kit templates, memory, scripts, and (under `specs/`) per-feature spec/plan/tasks/contracts artifacts.
- `setup/` holds the apply wizard and tooling. Never modify `~/.claude/` outside the apply flow.
- A change that lives only in `~/.claude/` and not in `global/` is a drift bug — fix the source, then re-apply.

## Development Workflow & Quality Gates

Spec-driven workflow for any non-trivial feature:

1. `/speckit-constitution` (this file) — establish or amend principles.
2. `/speckit-specify` — produce `spec.md` (user stories, requirements, success criteria).
3. `/speckit-clarify` (optional) — resolve `NEEDS CLARIFICATION` markers.
4. `/speckit-plan` — produce `plan.md` and design artifacts. **MUST pass Constitution Check gates** (see plan-template.md) before Phase 0 research.
5. `/speckit-tasks` — produce `tasks.md` with `Owner: @<agent>` on every line.
6. `/speckit-analyze` (optional) — cross-artifact consistency check.
7. `/speckit-implement` — execute, dispatching each task to its owner subagent.

Constitution Check gates a `/speckit-plan` run MUST pass:

- **Gate 1 (Spec-First)**: If the feature implements an external protocol, the relevant spec is linked and a conformance scope is stated.
- **Gate 2 (Delegation)**: A delegation table exists in `plan.md` mapping each phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 (Contract Tests)**: For each protocol surface, contract test tasks are listed before the corresponding implementation tasks in the planned task ordering.
- **Gate 4 (Reversibility)**: Any change under `global/` has a documented rollback in `plan.md`.
- **Gate 5 (Surface Minimality)**: Any new skill/agent has a justification line in `plan.md` explaining why an existing one cannot be extended.
- **Gate 6 (Parallel Isolation)**: If any phase dispatches two or more writing subagents concurrently, `plan.md` lists those phases in the Parallel Execution Map and `tasks.md` marks the affected tasks `Parallel: yes`. The implementation MUST pass `isolation: "worktree"` (or pre-create a worktree) for each concurrent writer. If no phase runs writers in parallel, write `N/A`.

Violations MUST be either resolved or recorded in the plan's Complexity Tracking table with explicit justification.

## Governance

- This constitution supersedes ad-hoc decisions and informal preferences.
- Amendments require: (a) edit via `/speckit-constitution`, (b) Sync Impact Report at the top of this file, (c) version bump per semver (MAJOR for principle removal/redefinition, MINOR for new principle/section, PATCH for clarification), (d) propagation to dependent templates.
- All `/speckit-plan` runs MUST verify Constitution Check gates before Phase 0.
- Deviations require an ADR; ADRs live in `.specify/specs/<feature>/contracts/` (feature-scoped) or `docs/adr/` (cross-cutting).
- Compliance review: any PR that touches `global/`, `.specify/templates/`, or this constitution itself requires explicit confirmation that gates are satisfied.

**Version**: 1.1.0 | **Ratified**: 2026-05-09 | **Last Amended**: 2026-05-10
