# Workflows — composing agents, skills, and services

Individual agents and skills are useful. Composing them into named workflows is where the leverage is. This document shows the canonical multi-agent flows this repo supports out of the box.

## Workflow 1 — Spec-kit feature, single session

For: a self-contained feature you can finish in one sitting.

```
1. /speckit-specify        ← write spec.md from a natural-language description
2. /speckit-plan           ← derive plan.md, research.md, data-model.md, contracts/
3. /speckit-tasks          ← break plan into ordered tasks.md (Phase 1..N)
4. /speckit-implement      ← execute tasks.md in this session
5. @code-plan-verifier     ← read-only check that code matches the plan
6. @gitignore-auditor      ← scan staged files for junk
7. @secret-auditor         ← scan staged files for credentials
8. /git commit             ← conventional commit, agent authorship, branch safety
9. /pr                     ← draft PR, gh pr create
```

Spec-kit lives in `.specify/` — `templates/`, `memory/constitution.md`, etc. The slash commands are provided by the `speckit-*` skills.

**Why this order**: spec → plan → tasks → implement → verify is the spec-kit doctrine. The verifier as a separate read-only pass catches drift the implementing model can't see in itself. The two auditors run **before** commit, not after, so issues are corrected before they enter history.

## Workflow 2 — Spec-kit feature, parallel sessions

For: a multi-day feature where you want to keep one session implementing and another reviewing.

```
Terminal A (implementing)         Terminal B (reviewing in parallel)
─────────────────────────────     ─────────────────────────────
/using-git-worktrees create       cd into the new worktree directory
  feat-new-thing                  open Claude Code there
                                  /executing-plans
/speckit-specify                    ← reads tasks.md from main worktree
/speckit-plan                       ← runs tasks with checkpoints
/speckit-tasks                      ← pauses for human review
                                    ← resumes when you confirm
                                  @code-plan-verifier between phases
when implementation lands         /finishing-a-development-branch
                                  /pr
```

Worktrees give you two checkouts of the same repo on different branches, sharing history. `/using-git-worktrees` wraps `git worktree add/list/remove/prune` with safe defaults.

**Why parallel sessions**: the implementation context window fills with file reads, refactors, and test runs. Keeping review in a separate session means the reviewer always starts cold and reads what's actually on disk, not what the implementer thinks landed.

> **Isolation rule** — when a dispatcher (`/plan` Step 6, `/speckit-implement` parallel batch) spawns two or more writing subagents concurrently, each MUST run in an isolated git worktree. See [`parallel-isolation.md`](parallel-isolation.md) for the dispatch contract, the `Parallel: yes` task convention, and the concrete failure mode this prevents.

## Workflow 3 — Bootstrap a brand-new project

For: starting from an empty directory.

```
1. mkdir new-project && cd new-project
2. claude                     ← SessionStart hook detects no CLAUDE.md
3. "let's set this up"        ← Claude routes to @init-project
4. @init-project asks the architecture questions for the detected stack
5. CLAUDE.md is written; specialists are announced
6. /react-init (or equivalent) ← scaffold the actual code
7. /git init                  ← initialise repo with conventions
8. /git commit                ← first commit
```

By the end of step 5, every future session in this directory has the right context auto-loaded by `@load-project` and the right specialists routed by description match.

## Workflow 4 — Pick up an existing project

For: opening an unfamiliar repo.

```
1. cd existing-project
2. claude                     ← SessionStart hook sees CLAUDE.md
3. Claude auto-invokes @load-project
4. @load-project reads CLAUDE.md, detects stack, lists available specialists
5. You're ready to work — context is loaded, specialists are routed
```

Zero prompting on your side. The hook + agent handle the warm-up.

## Workflow 5 — Multi-agent via the A2A bridge

For: when one Claude isn't enough — typically when you want a second opinion from a different model (Gemini) or want to decouple a long-running review.

```
Terminal 1: bring up the bridge
  cd services/a2a-bridge
  uv run a2a-bridge serve gemini --port 8766
  uv run a2a-bridge serve claude --port 8765

Terminal 2: drive Claude
  Claude → DelegationClient → POSTs JSON-RPC to localhost:8766
                            → Gemini CLI runs, streams SSE results back
                            → Claude integrates the output
```

This is what powers `services/orchestrator` — it watches a GitHub repo, dispatches every PR to a peer Claude agent over the same bridge, posts the review back via `gh`, and notifies you on phone via ntfy.sh.

See [`services.md`](services.md) for both daemons in detail.

## Workflow 6 — End-of-feature finishing

For: closing a feature branch.

```
1. /finishing-a-development-branch
   ← runs tests, verifies build, creates final commit
   ← offers PR or push
2. (optional) @code-plan-verifier     ← final drift check vs tasks.md
3. (optional) @gitignore-auditor      ← last staged-files audit
4. (optional) @secret-auditor         ← last secrets audit
5. /pr                                ← title, description, gh pr create
6. /review                            ← branch review against main (self-review pass)
```

Run the auditors **before** opening the PR. They're cheap and they catch the embarrassing stuff.

## Workflow 7 — UI / component work

For: building a component on a frontend project.

```
1. /design                    ← load Premium Digital Agency 2.0 system into context
2. /css scaffold              ← (once per project) globals.css with reset + tokens
3. /ui-component              ← build the component (only when explicitly asked)
4. /css ButtonName            ← generate ButtonName.module.css alongside
5. /react-test                ← scaffold tests with Vitest + RTL
6. /react-perf                ← perf audit if it has lists or heavy renders
7. /react-safe                ← async + error + security audit
8. /react-review              ← code-quality review
```

The skills compose because each has a narrow `description:` and a small allowed-tools set — none of them step on each other.

## Workflow 8 — One-off skill creation

For: turning a repeated workflow into a `/skill`.

```
1. /skill-create
2. Describe what you keep doing manually
3. /skill-create drafts the markdown, asks about trigger phrasing
4. Test it in the same session ("type /your-new-skill and tell me what happened")
5. Iterate description until autonomous routing fires reliably
6. python setup/apply.py
7. Restart Claude Code → skill is live in every project
```

## Patterns that compose

- **Auditor + Skill** — `@gitignore-auditor` returns findings → `/git commit` is the human-decision step. Auditors never modify files; skills handle the writes.
- **Implementer + Verifier** — any architect/skill that writes code → `@code-plan-verifier` reads the plan and the code → reports drift. The asymmetry (writer can have biases, reader is read-only) is the value.
- **Skill + Agent** — `/executing-plans` is a skill that orchestrates phases; between phases you call `@code-plan-verifier`. Skill handles the loop, agent handles the hard read.
- **Hook + Skill** — the `SessionStart` hook routes to `@load-project`; `/git commit` enforces commit rules. Hooks set up state; skills act on it.

## Anti-patterns

- **Concurrent writers on a shared working tree.** Two agents dispatched in parallel without `isolation: "worktree"` will silently clobber each other's files. See [`parallel-isolation.md`](parallel-isolation.md).
- **Two skills that do almost the same thing.** Claude will pick the wrong one. Either merge them or sharpen the descriptions.
- **A skill that should have been an agent.** If the work needs context isolation or is open-ended, agents are right. Skills run in your conversation and pollute it.
- **Auditors that fix things.** Once an auditor edits, it's no longer an auditor — it's a tool with bias. Keep them strictly read-only.
- **Hooks that ask questions.** Hooks fire on lifecycle events; they can't be interactive. If you need a prompt, inject it via `additionalContext` so Claude asks the user.
