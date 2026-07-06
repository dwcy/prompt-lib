# Parallel subagent isolation

> Single source of truth for **when** subagents must run in isolated git worktrees, **why**, and **how**. Every other file (CLAUDE.md, constitution, agents.md, plan-template, tasks-template, /plan skill) points back here.

## The rule

When two or more subagents are dispatched to operate concurrently on the same repository, every **writing** agent MUST run in an isolated git worktree. Pass `isolation: "worktree"` on the Agent tool call (preferred — auto-cleanup if the agent makes no changes; path + branch returned on success), or pre-create a worktree via `/using-git-worktrees create <branch>` and brief the agent with its path.

Read-only agents and sequential single-agent dispatch are **exempt**.

## When it applies

| Scenario | Isolation required? |
|---|---|
| Main spawns 1 writing agent, waits for it, then spawns the next | No — sequential |
| Main spawns 2+ writing agents with `run_in_background: true` to overlap them | **Yes — every concurrent writer** |
| `/plan` full-stack flow spawns backend + frontend agents in parallel | **Yes — both** |
| `/speckit-implement` dispatches `Parallel: yes` tasks from `tasks.md` | **Yes — every parallel batch member** |
| Main spawns @code-plan-verifier alongside an architect doing edits | No — verifier is read-only |
| Main spawns @gitignore-auditor + @secret-auditor concurrently | No — both are read-only |
| You open two Claude Code sessions on the same repo at different branches | **Yes — use `/using-git-worktrees create`** |

The rule is about **concurrent writes to a shared working tree**, not about the count of subagents in absolute terms.

## Why — the concrete failure mode

Without isolation, two writers on one tree look like this:

```
t=0   Agent A reads src/api/orders.py            (current content X)
t=1   Agent B reads src/api/orders.py            (current content X)
t=2   Agent A writes src/api/orders.py           (content X + A's change → X')
t=3   Agent B writes src/api/orders.py           (content X + B's change → X'')
              ↑ overwrites A's work, no warning, no conflict
t=4   Both agents report success
t=5   You inspect the tree — only B's change is there
```

Git never sees this. The filesystem doesn't even see this — both writes are syntactically valid file-system operations. The only signal is the missing diff at the end, which neither agent can detect because each saw a successful write.

With `isolation: "worktree"`, A and B operate on **different working trees** off the same repo. Each agent's writes land in its own checkout. Merging the two branches at the end of dispatch produces a normal three-way merge — collisions become git conflicts, which are visible and resolvable.

## How — two mechanisms

### 1. `isolation: "worktree"` on the Agent tool call (preferred)

The Claude Code harness handles the lifecycle:

- A temporary worktree is created when the agent starts.
- The agent runs entirely inside it.
- On exit:
  - **No changes** → worktree is auto-cleaned, nothing returned.
  - **Has changes** → the worktree path + branch are returned in the agent's result so the caller can merge.

This is the right choice for dispatcher-managed parallelism (`/plan` Step 6, `/speckit-implement` parallel batches). The caller doesn't manage worktree lifecycle directly; the harness does.

### 2. `/using-git-worktrees create <branch>` (manual)

For multi-session work where you (the human) want to keep two Claude Code instances running on the same repo at the same time, create worktrees by hand:

```
/using-git-worktrees create feat-new-thing
cd ../<worktree-dir>
claude
```

The new session sees its own working tree and shares history with main. This is the path for [`workflows.md` Workflow 2 — parallel sessions](workflows.md#workflow-2--spec-kit-feature-parallel-sessions).

## Cleanup

| Mechanism | Cleanup |
|---|---|
| `isolation: "worktree"` — agent made no changes | Auto — harness deletes the worktree |
| `isolation: "worktree"` — agent made changes | Manual — caller must `git worktree remove` after merging the returned branch back |
| `/using-git-worktrees create` | Manual — `/using-git-worktrees remove <branch>` or `git worktree remove <path>` |

Stale worktrees aren't dangerous but they take disk space and pollute `git worktree list`. Run `/using-git-worktrees prune` periodically.

## Runtime enforcement

The rule used to live only in docs and CLAUDE.md — easy to forget. Two hooks now enforce it at runtime.

### SessionStart auto-worktree on collision

`global/hooks/session_start.py` claims a per-branch lock at `<git-common-dir>/claude-session-locks/<branch>.json` when the first Claude session lands on a non-`main` branch. If a second session starts in the same cwd on the same branch while the first PID is alive, the hook:

1. Picks the next free sibling slot — branch `<branch>-s<N>` and directory `../<repo>-<branch>-s<N>`.
2. Runs `git worktree add ../<repo>-<branch>-s<N> -b <branch>-s<N>` from the main checkout.
3. Emits `additionalContext` telling Claude to refuse writes in the current cwd and walk the user through `cd <new-path>` + restart `claude`.

Linked worktrees, `main`/`master`, detached HEAD, and non-repo dirs are exempt. The lock is released on `SessionEnd` by `session_end_release_lock.py`; stale locks self-heal via a cross-platform PID-alive check (POSIX `os.kill(pid, 0)`, Windows `tasklist`).

**Opt-out**: set `CLAUDE_WORKTREE_AUTO=0` and the hook emits a warning instead of creating a worktree.

### PreToolUse `Task` guardrail

`global/hooks/pretool_task_isolation.py` runs on every `Task` dispatch. It blocks the most common anti-pattern — a `subagent_type` not in the read-only allowlist, with `run_in_background: true`, and no `isolation: "worktree"`. Block surfaces as `decision: "block"` with the documented reason.

**Read-only allowlist** (no `Write`/`Edit` in declared `tools:`):
`Explore`, `Plan`, `claude-code-guide`, `statusline-setup`, `code-plan-verifier`, `gitignore-auditor`, `github-config-manager`, `load-project`, `secret-auditor`.

**V1 gap (acknowledged)**: two foreground concurrent `Task` calls in the same assistant message both see `run_in_background: false` and slip through. Closing this needs cross-invocation state (a small lockfile of in-flight Task IDs) and is deferred.

## How the rule appears in each file

| File | What it says |
|---|---|
| `global/CLAUDE.md` | Short "Parallel subagent isolation" section in always-loaded context, points here |
| `.specify/memory/constitution.md` | Principle II clause + Constitution Check Gate 6 |
| `.specify/memory/agents.md` | "Parallel isolation" subsection with the `Parallel: yes` task convention and an example |
| `.specify/templates/plan-template.md` | Gate 6 in Constitution Check + "Parallel Execution Map" subsection |
| `.specify/templates/tasks-template.md` | Extended `Format:` line with optional `Parallel: yes` field + dispatch rule |
| `.claude/commands/plan.md` | Step 6 sets `isolation: "worktree"` on both full-stack dispatches |
| `global/hooks/session_start.py` | Claims per-branch lock; auto-creates sibling worktree on collision |
| `global/hooks/session_end_release_lock.py` | Releases the per-branch lock on session exit |
| `global/hooks/pretool_task_isolation.py` | Blocks background `Agent` (formerly `Task`) dispatches without `isolation: "worktree"` |
| `docs/parallel-isolation.md` | (this file) — canonical explainer |

## The `Parallel: yes` task convention

In `tasks.md`, a task that will be dispatched concurrently with other writing tasks ends with `— Parallel: yes`. Example:

```
T012 [P] [US1] Implement POST /api/orders handler — src/api/orders.py — Owner: @python-architect — Parallel: yes
T013 [P] [US1] Implement OrdersForm component — web/src/features/orders/OrdersForm.tsx — Owner: @react-architect — Parallel: yes
T014     [US1] Wire orders feature module — web/src/features/orders/index.ts — Owner: @react-architect
```

T012 and T013 form a parallel batch — `/speckit-implement` dispatches them with `isolation: "worktree"` on each Agent call. T014 runs sequentially in the main tree.

**Important**: `[P]` (the existing parallelism marker) means *can* run in parallel. `Parallel: yes` means *will* run in parallel during dispatch. They are different fields. `[P]` is a property of the task; `Parallel: yes` is a dispatch decision.

## Briefing the worktree-isolated agent

When the dispatcher sets `isolation: "worktree"`, the subagent's prompt should include:

> "You are running in an isolated git worktree. Stay inside it — do not `cd` out, do not write to paths outside this working tree, do not assume the main branch is checked out here. Your changes will be merged back after you return."

Without this line, an agent may try to `cd` to the canonical repo root, read stale files from the main tree, or write to absolute paths that bypass the worktree. The `/plan` skill includes this line in Step 6.

## Anti-patterns

- **Spawning two writing agents with `run_in_background: true` and no `isolation:` parameter.** Race condition by design. Add `isolation: "worktree"` to both.
- **Marking a read-only auditor as `Parallel: yes`.** Pointless — it can't overwrite anything. Worktree creation is overhead for no benefit.
- **Pre-creating a worktree, then forgetting to brief the agent with the path.** The agent will operate on the main tree by default. Either include the path in the prompt, or use `isolation: "worktree"` and let the harness manage it.
- **Not merging the returned branch from `isolation: "worktree"` before moving to the next phase.** The work is in a branch that hasn't been integrated. The next phase will read stale files in main and silently regress.
- **Resolving merge conflicts automatically in the dispatcher.** The dispatcher reports conflicts to the user. Auto-resolving conflicts defeats the purpose of catching them.
- **Using `isolation: "worktree"` for a single sequential agent.** Adds latency (worktree create + remove) for no isolation benefit. Reserve it for actual concurrency.

## FAQ

**Does the worktree share git history with main?**
Yes. A worktree is a second working directory pointed at the same `.git` directory (with a separate index and HEAD). All commits in the worktree appear in the shared object database immediately.

**Can two worktrees be on the same branch?**
No. Git refuses to check out one branch in two worktrees simultaneously. The harness creates a fresh branch per worktree to avoid this.

**What happens if the agent crashes mid-run?**
The worktree remains. The caller sees the failure, can inspect the worktree contents, and either retries or runs `git worktree remove --force`.

**Does this apply to MCP tool calls or skills?**
No. MCP tools and skills run in the current conversation, not as separate subagent sessions. They have no parallelism semantics. The rule is specifically about `Agent` tool dispatches that overlap in time.

**Does this conflict with the `/git` skill's branch-safety rules?**
No. `/git` refuses to commit on `main` — that rule applies regardless of which working tree you're in. The worktree branch is a feature branch by construction.
