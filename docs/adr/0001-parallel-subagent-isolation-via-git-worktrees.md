# 0001. Constitution v1.1.0 — Parallel Subagent Isolation via Git Worktrees

Date: 2026-05-10

## Status

Accepted

## Context

This repo's spec-kit workflow and the `/plan` skill both dispatch multiple subagents through the `Agent` tool. Three concrete dispatch patterns produce concurrent writers on the same working tree:

1. `/plan` Step 6 (full-stack) spawns a backend architect and a frontend architect simultaneously, with `run_in_background: true` on the first.
2. `/speckit-implement` walks `tasks.md` and was free to dispatch sibling tasks tagged `[P]` (parallelisable) concurrently.
3. A future orchestrator (`services/orchestrator`) review pass dispatches one or more peer Claude agents over the A2A bridge while local work continues.

Until now nothing in this repo's governance, templates, or skills mandated isolation between those writers. The default behaviour — two `Agent` calls hitting the same checkout — produces a silent failure mode:

```
t=0  Agent A reads src/foo.py    (content X)
t=1  Agent B reads src/foo.py    (content X)
t=2  Agent A writes src/foo.py   → X'
t=3  Agent B writes src/foo.py   → X''   (overwrites A, no warning)
t=4  Both report success
```

Git never sees the overwrite because both writes are syntactically valid file-system operations on a shared tree. The only signal is a missing diff at the end of the run, which neither agent can detect. This violates the **spirit** of Constitution Principle II (Subagent Delegation) — the principle assumed each delegated task lands on disk as written — but did not have a textual rule that bound dispatchers to enforce it.

The Claude Code harness already supports `isolation: "worktree"` on the `Agent` tool: a temporary worktree is created at dispatch, auto-cleaned if the agent makes no changes, and the path + branch are returned on success. The mechanism existed; the policy did not.

Constraints considered:

- The rule must be findable by the harness on every relevant code path (not just docs). That means it has to live in always-loaded context, the constitution, the spec-kit memory roster, and the templates the templates instantiate from.
- Read-only auditors (`@code-plan-verifier`, `@gitignore-auditor`, `@secret-auditor`) cannot overwrite anything; forcing worktrees on them would be pure overhead with no isolation benefit.
- Sequential single-agent dispatch has no race; forcing worktrees there is also pure overhead.
- The rule must distinguish `[P]` (the task is *capable* of running in parallel) from `Parallel: yes` (the task *will* be dispatched in parallel), because the latter is a dispatch decision, not a property of the task.

## Decision

We will amend the project constitution to **v1.1.0** (MINOR bump per the constitution's own versioning rule), extending Principle II — Subagent Delegation — with a binding parallel-isolation clause, and adding a sixth Constitution Check gate to `/speckit-plan`.

The canonical rule:

> When two or more subagents are dispatched to operate concurrently on the same repository, every writing agent MUST run in an isolated git worktree. Pass `isolation: "worktree"` on the Agent tool call, or pre-create a worktree via `/using-git-worktrees create` and brief the agent with its path. Read-only agents (no Write/Edit in `tools:`) and sequential single-agent dispatch are exempt.

To make the rule operational, we will:

1. Add a "Parallel subagent isolation" section to `global/CLAUDE.md` so it is in always-loaded context for every session.
2. Bump `.specify/memory/constitution.md` to v1.1.0 with a Sync Impact Report, extending Principle II and adding Constitution Check Gate 6.
3. Add a "Parallel isolation" subsection to `.specify/memory/agents.md`, including a new `Parallel: yes` task-line convention with an example.
4. Update `.specify/templates/plan-template.md` (new "Parallel Execution Map" subsection + Gate 6 in Constitution Check) and `.specify/templates/tasks-template.md` (extended `Format:` line, dispatch directive).
5. Update `.claude/commands/plan.md` Step 6 so both full-stack agents are dispatched with `isolation: "worktree"` and briefed to stay inside their worktree.
6. Write `docs/parallel-isolation.md` as the single canonical explainer that every other file references, covering the rule, when it does and does not apply, the concrete failure mode, the two mechanisms (`isolation: "worktree"` and `/using-git-worktrees`), cleanup, anti-patterns, and FAQ.
7. Cross-link the explainer from `docs/README.md`, `docs/workflows.md`, `docs/speckit.md`, `docs/agents.md`, `docs/skills.md`, and the root `README.md`.

Existing feature trees (`specs/001-a2a-bridge`, `specs/002-agent-orchestrator`) are not retroactively updated; new features inherit the rule from the templates.

## Consequences

**Positive**

- Concurrent writers can no longer silently clobber each other. Conflicts become explicit at merge time, where they are visible and resolvable through normal git operations.
- The rule is enforceable at the harness level: the `Agent` tool's `isolation: "worktree"` parameter makes worktree lifecycle the responsibility of the runtime, not of every dispatcher.
- The `Parallel: yes` convention separates "this task could be parallelised" (the existing `[P]` marker) from "this task will be dispatched in parallel" (the new marker), removing the ambiguity that allowed accidental concurrent writes.
- Read-only auditors stay exempt, so the audit chain at the end of every feature retains its current zero-overhead semantics.
- The rule appears in seven files but lives canonically in one (`docs/parallel-isolation.md`); future changes amend one document and update the cross-links.

**Negative**

- Every concurrent-writer dispatch now pays the cost of creating and (when changes occur) merging a worktree branch. For two-agent batches the cost is small but non-zero.
- After agents finish, the dispatcher must merge each returned branch back to the integration branch before the next phase starts. Forgetting to merge causes the next phase to read stale files in the main tree — a new failure mode that didn't exist before (though it's noisier than the silent overwrite it replaces).
- The Constitution Check section in every future `plan.md` grows by one gate. Plans that don't run writers in parallel must now explicitly write `N/A` for Gate 6, adding two lines of boilerplate.
- The rule lives in seven files. Future amendments require touching all of them; drift between them would be a real concern if the explainer at `docs/parallel-isolation.md` is not treated as the single source of truth.

**Neutral**

- The change does not affect existing feature trees. Retroactive application is explicitly out of scope.
- Constitution version goes 1.0.0 → 1.1.0. The Sync Impact Report at the top of `constitution.md` retains the previous (0.0.0 → 1.0.0) report inline so prior context is not lost.

## Alternatives Considered

**1. Do nothing; require dispatchers to remember.**
Rejected. The harness already supports `isolation: "worktree"`, but nothing in the current text mandated its use. Relying on every future dispatcher (human or LLM) to remember a defensive parameter is exactly the failure mode that produced the gap in the first place.

**2. Make `isolation: "worktree"` the default for every `Agent` dispatch.**
Rejected. This would impose worktree-creation cost on every subagent invocation, including read-only auditors and single sequential dispatches that have no race. The harness behaviour is upstream of this repo, so we can't change the default — but even if we could, the cost-benefit doesn't justify it.

**3. Pre-create one worktree per parallel batch in the dispatcher and brief each agent with its path.**
Rejected as the preferred mechanism, retained as a documented alternative. It works (and `/using-git-worktrees create` is the explicit fallback), but it shifts worktree lifecycle management onto every dispatcher. `isolation: "worktree"` lets the harness own cleanup of zero-change worktrees automatically, which is the common case.

**4. Add a Principle VI rather than extending Principle II.**
Rejected. Parallel isolation is a property of delegation (the topic of Principle II), not a new orthogonal concern. Adding a new principle inflates the constitution; extending an existing one preserves the structure.

**5. Block concurrent dispatch entirely; require sequential execution.**
Rejected. The whole point of `/plan` Step 6 and the `[P]` marker in `tasks.md` is to overlap independent work. Forcing sequential execution would erase a real productivity gain to fix a problem that has a cheap mechanical solution.
