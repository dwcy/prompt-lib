# Quickstart: /orchestrate

## What it does

`/orchestrate` routes your task to the right specialist subagent automatically. You describe what you want; the skill picks the agent, dispatches it with proper isolation, and returns the result.

## Basic usage

```
/orchestrate refactor the PaymentService to use Clean Architecture
/orchestrate write xUnit tests for OrderRepository
/orchestrate add a React checkout page with Zustand cart state
/orchestrate audit staged files before committing
/orchestrate verify the implementation matches the plan
```

## Automatic routing

You don't always need to type `/orchestrate`. If `global/CLAUDE.md` detects a specialist domain (Python service design, .NET architecture, React components, etc.), the main session will invoke it automatically and tell you which agent was selected.

## Multi-domain tasks

If your task spans two independent domains, both agents run in parallel in isolated worktrees:

```
/orchestrate add a FastAPI endpoint and a React form for user login
```

→ `@python-architect` and `@react-architect` run simultaneously, each in its own git worktree. Results are merged back and any file conflicts are reported.

## Sequential pipelines

For design → implement → verify flows:

```
/orchestrate design, implement, and verify the onboarding checkout flow
```

→ `@frontend-designer` runs first, then `@react-architect` receives the design output, then `@code-plan-verifier` audits the implementation.

## Pre-commit audit

```
/orchestrate audit staged files
```

→ `@gitignore-auditor` and `@secret-auditor` run in parallel (read-only, no isolation needed). Combined report is presented.

---

## Adding a new agent to the routing table

1. Create the agent definition at `global/agents/<name>.md`
2. Add a row to the routing table in **both**:
   - `global/skills/orchestrate.md` — Step 2 table
   - `specs/006-orchestrate-skill/plan.md` — Routing Table section
3. Add the agent to `global/CLAUDE.md` auto-routing triggers if it should fire proactively
4. Deploy: `bash setup/tools/apply-global-claude-settings.sh`
5. Validate: run `/orchestrate <task that should trigger the new agent>` and confirm selection

## Dispatch isolation rules

| Agent type | Isolation required? |
|---|---|
| Writes files (architects, testers, implementors) | Yes — `isolation: "worktree"` |
| Read-only (auditors, verifiers) | No |
| Sequential pipeline, single agent at a time | Yes per writing agent |

Worktree branch naming: `orchestrate/<agent-name>/<short-task-slug>`
