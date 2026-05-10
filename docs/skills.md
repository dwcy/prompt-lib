# Skills — every slash command explained

A skill is a markdown file with frontmatter. When you type `/<name>`, Claude reads the file and treats its body as the next instruction. **No subagent is spawned** — the skill runs in the current conversation with the tools listed in `allowed-tools:`.

Skills are how you turn "things you keep doing" into one keystroke.

## Git workflow skills

### `/git`
- **Args**: `commit` (default), `branch <name>`, `init`
- **Tools**: `Bash, Read, Glob`
- **What it does**:
  - `commit` — runs `git diff --staged`, drafts a conventional commit message (`<type>: <subject>`), tags it with a category (`ui/dotnet/python/css/html/js/ts`) when appropriate, refuses to commit on `main`/`master`, uses agent authorship via `-c user.email="my@agent.commit" -c user.name="Claude Agent"`, asks for confirmation, then commits.
  - `branch <name>` — creates a feature branch off `main`.
  - `init` — initialises a new repo with the convention.
- **Why**: enforces the global commit rules (subject ≤72 chars, imperative mood, agent authorship) without you having to remember them.

### `/commit`
- **Tools**: `Bash`
- **What it does**: lighter version of `/git commit` — staged-only, drafts a conventional message, asks confirmation, commits. No branch safety check, no category tagging, no agent authorship override.
- **When to pick it over `/git commit`**: quick fixups inside a feature branch where the safety machinery is overkill.

### `/pr`
- **Tools**: `Bash, Read`
- **What it does**: runs `git log` and `git diff` between the current branch and main, drafts a PR title + description, creates the PR with `gh pr create`. Uses HEREDOC for the body to keep formatting clean.

### `/review`
- **Tools**: `Bash, Read, Glob`
- **What it does**: structured branch review against `main` — code quality, conventions, potential issues. Output is a flat list of findings, not a code rewrite. Pairs naturally with the `review` output style.

### `/finishing-a-development-branch`
- **Tools**: `Bash, Read, Glob`
- **What it does**: end-of-feature checklist runner. Runs tests, verifies build, creates a final commit, and offers to either open a PR or push. Use after all implementation tasks are done — saves the "did I forget to run tests?" moment.

### `/using-git-worktrees`
- **Args**: `create` (default), `list`, `remove`, `prune`
- **Tools**: `Bash, Read, Glob`
- **What it does**: manages `git worktree` operations so you can run multiple Claude Code sessions on the same repo, in parallel, on different branches. Used by `/executing-plans` when a plan needs an isolated workspace.
- **Dual role**: this skill is the **manual** half of the parallel-isolation rule (for two human-driven Claude Code sessions). The **automatic** half is `isolation: "worktree"` on the Agent tool call, which the dispatcher passes when spawning concurrent subagents. See [`parallel-isolation.md`](parallel-isolation.md).

## Implementation skills

### `/executing-plans`
- **Tools**: `Bash, Read, Write, Edit, Glob, Grep`
- **What it does**: takes a written implementation plan (typically `tasks.md` from a spec) and executes it in a separate session with review checkpoints between phases. Announces itself at start so you know which mode you're in.
- **When to use**: long implementations where you want the model to execute, then pause for human review, rather than barrel through the whole feature.
- **Composes with**: `/using-git-worktrees` to isolate the workspace, then `@code-plan-verifier` once execution finishes.

## Frontend / React skills

### `/react-init`
- **Tools**: `Bash, Read, Write, Edit, Glob`
- **What it does**: scaffolds a complete React 2025 project — Vite + TS + Zustand + TanStack + Biome + Tailwind v4 + Zod + MUI Icons. Asks all questions up front, then generates config files, folder structure, and `.cursorrules` without further interruptions.
- **Pairs with**: `@react-architect` for React structure decisions and `@tanstack-architect` for route/data/form/table architecture.

### `/react-review`
- **Tools**: `Read, Glob, Bash`
- **What it does**: reviews a React file or feature for code quality — separation of concerns, naming, component design, data flow, types, documentation, hygiene. Outputs Critical / Warning / Suggestion findings.

### `/react-test`
- **Tools**: `Read, Write, Glob, Bash`
- **What it does**: scaffolds or reviews tests for a React component, hook, or feature using Vitest + React Testing Library. Follows DI patterns, covers happy paths and failure modes, never tests implementation details.

### `/react-safe`
- **Tools**: `Read, Glob, Bash`
- **What it does**: audits a React file/feature for async correctness, error handling completeness, security — unhandled promises, swallowed errors, missing sanitisation, logged secrets, input validation gaps.

### `/react-perf`
- **Tools**: `Read, Glob, Bash`
- **What it does**: performance audit — unnecessary re-renders, missing memoisation, heavy imports, bundle size, large-dataset handling, lazy-load opportunities.

### `/css`
- **Args**: `scaffold`, or a `ComponentName`
- **Tools**: `Read, Write, Edit, Glob`
- **What it does**: `scaffold` sets up `globals.css` with reset and design tokens. `Button` (or any component name) generates `Button.module.css` alongside the component file.
- **Pairs with**: `@frontend-css` for deeper architectural questions.

### `/ui-component`
- **Tools**: `Read, Glob, Grep, Write, Edit`
- **What it does**: builds a UI component on demand. Enforces design-language compliance, ships a `Preview` component alongside every component, enforces correct HTML semantics for inputs, wires forms to Zustand + Zod validation.
- **Iron rule**: only writes a component when explicitly asked — won't anticipate or pre-emptively scaffold.

### `/design`
- **Tools**: `Read, Write, Edit, Glob`
- **What it does**: loads the Premium Digital Agency 2.0 design system into context. Invoke before building UI components, reviewing designs, or making styling decisions — once loaded, every styling decision in the session must follow it.

### `/lovable-cleanup`
- **Tools**: `Read, Edit, Glob, Bash`
- **What it does**: strips all Lovable / GPTEngineer scaffolding from a project — `lovable-tagger` from `package.json` and `vite.config.ts`, cleans `index.html` metadata, removes injected `data-lovable-id` and `data-gptengineer-id` attributes from all source files, rewrites README, regenerates the lockfile.

## Meta skills

### `/skill-create`
- **Tools**: `Read, Write, Edit, Glob, Bash`
- **What it does**: walks you through designing, writing, testing, and refining a new skill. Use this whenever a workflow you keep doing manually should become a `/command`.

## Pattern: skill vs agent

| Use a skill when… | Use an agent when… |
|---|---|
| The flow is short, deterministic, mostly tool calls | The work is open-ended, exploratory, or large |
| You want it to run in the current context | You want context isolation (a clean window) |
| Output should land directly in the conversation | Output should be a single summary message |
| You'll trigger it explicitly with `/name` | You want autonomous routing on description match |

A skill can call an agent (via the `Task` tool) and an agent can be invoked from a skill — they compose.

## Adding a skill

1. Create `global/skills/<name>.md`:
   ```yaml
   ---
   name: <name>
   description: One sentence — what triggers it, what it does.
   allowed-tools: Bash, Read
   ---
   ```
2. Body = the instruction Claude follows when you invoke it.
3. `python setup/apply.py` → restart.

Use `/skill-create` if you want guided drafting and trigger-accuracy checks.
