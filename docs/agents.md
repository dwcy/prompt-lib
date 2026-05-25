# Agents — every subagent explained

Agents are **separate Claude sessions with focused system prompts and restricted tools**. They protect the main conversation's context window and let you compose specialists.

## How an agent gets picked

Two routes:

1. **Autonomous** — Claude sees your message, scans every agent's `description:` field, picks the best match, and spawns it as a subagent. You usually never see this happen.
2. **Explicit** — you mention `@agent-name` in your message. Claude spawns it directly.

The `description:` field is the only thing that drives autonomous routing. Vague descriptions = bad routing. The agents in this repo lead each description with the trigger context ("Use for…", "Use after…", "Use when…").

## The roster

### Project bootstrap

#### `@init-project`
- **When**: starting a brand-new project that has no `CLAUDE.md` yet.
- **Tools**: `Read, Write, Bash, Glob, Task`
- **Why**: codifies the conventions for the project once instead of re-explaining them every session. Detects the stack (Python / .NET / Unity / frontend / monorepo / generic), asks the right architecture questions for that stack from `global/project-templates/<stack>.md`, writes a populated `CLAUDE.md` at the root, and then announces which specialist subagents are now relevant for the session.
- **Composes well with**: `@dotnet-architect`, `@python-architect`, `@react-architect`, `@tanstack-architect`, `@frontend-architect`, `@unity-architect` — `@init-project` spawns the right one after writing `CLAUDE.md`.

#### `@load-project`
- **When**: opening an existing project with a `CLAUDE.md` already present. Triggered automatically by the `SessionStart` hook.
- **Tools**: `Read, Glob, Bash`
- **Why**: gives Claude a 30-second briefing on this codebase's conventions and tells you which specialists are available. Without it, every session starts cold and re-discovers structure.

### Architecture specialists

Each one owns a stack. They give opinionated guidance, scaffold structure, and write code in their idiom.

#### `@dotnet-architect`
- Clean Architecture layout, CQRS, domain modelling, DI patterns, service design.
- Tools: `Read, Write, Edit, Glob, Bash`.
- Pair with `@dotnet-tester` for the test side of the same change.

#### `@python-architect`
- FastAPI / Django structure, async design, service-layer composition, DI patterns, DB session management.
- Tools: `Read, Write, Edit, Glob, Bash`.
- Pair with `@python-tester`.

#### `@react-architect`
- Current stable React stack: Vite + TS + Zustand + Biome + Tailwind + Zod + DOMPurify + MUI Icons, with light-to-moderate TanStack usage.
- Use for feature structure, component boundaries, client/UI state boundaries, config setup, and React integration patterns.
- If TanStack packages are the architecture itself, use `@tanstack-architect`.
- If the project is Vue 3 or Next.js, use `@frontend-architect` instead.

#### `@tanstack-architect`
- Opinionated TanStack specialist for React projects built around TanStack Start, Router, Query, Form, Table, or Virtual.
- Use for typed route trees, route loaders, search-param state, Query cache boundaries, SSR/streaming, forms, data grids, virtualization, and cross-package integration.
- Hard stance: URL state in Router search params, server state in Query, form state in TanStack Form, table state in TanStack Table. No duplicate caches in Zustand or component state.
- Pairs well with `@react-architect` for component/module shape and `@frontend-css` for styling.

#### `@frontend-architect`
- Vue 3, Next.js, or React projects outside the Vite + Zustand + TanStack stack above.
- Component design, state management, performance, accessibility.

#### `@frontend-css`
- Modular + global CSS pattern. Scaffolds `globals.css` with reset, design tokens, and theming. Generates `Component.module.css` next to each component.
- Hard rule: no hardcoded values — everything pulls from custom properties.

#### `@unity-architect`
- Scene architecture, ScriptableObject design, MonoBehaviour patterns, performance optimisation.

#### `@pi-arduino-architect`
- Hobby electronics for Raspberry Pi (Python) and Arduino (C++): GPIO, I2C/SPI/UART sensors, motor drivers, servos, basic robotics.
- Includes an explicit Pi-vs-Arduino decision rubric for projects that could run on either.
- Hard rules: level shifters for 5V→Pi, motors on their own supply with common ground, explicit pull-ups/pull-downs, no deprecated `RPi.GPIO` on Pi 5.

### Testing specialists

#### `@dotnet-tester`
- xUnit, integration tests with TestContainers, mocking with NSubstitute or Moq.
- Strategy decisions: what to mock, what to integration-test, what to leave out.

#### `@python-tester`
- pytest, async test patterns, fixture design, real-DB integration tests.

### Read-only auditors

These never modify code. They report findings; you decide what to fix.

#### `@code-plan-verifier`
- **When**: after implementing a feature against a plan (`plan.md` / `tasks.md`).
- **Tools**: `Read, Grep, Glob, Bash, WebSearch, WebFetch` — read-only.
- **Why**: catches drift between what was agreed in the plan and what landed in the code. Finds missing tasks, unauthorised additions, version mismatches against the spec.

#### `@gitignore-auditor`
- **When**: just before committing.
- **Tools**: `Read, Grep, Glob, Bash` — read-only.
- **Why**: scans staged files for build artefacts, caches, IDE junk, OS files (`.DS_Store`, `Thumbs.db`), local config, secrets-shaped files. Suggests `.gitignore` lines and `git rm --cached` commands. Doesn't edit anything — output is advisory.

#### `@secret-auditor`
- **When**: just before committing.
- **Tools**: `Read, Grep, Glob, Bash` — read-only.
- **Why**: scans staged files for API keys, OAuth/JWT tokens, private keys, connection strings with embedded passwords, high-entropy strings near credential keywords. Returns per-finding evidence (file, line, type, severity, redacted snippet). Calling skill / human decides per finding.

## Pattern: composing agents

The `@init-project` → `@architect` → `@tester` → `@code-plan-verifier` chain is the canonical multi-agent flow:

```
1. @init-project          writes CLAUDE.md, picks the architect agent
2. @<lang>-architect      proposes structure, scaffolds modules
3. @<lang>-tester         writes the test suite alongside
4. @code-plan-verifier    confirms code matches the plan and conventions
5. @gitignore-auditor     checks staged files before commit
6. @secret-auditor        checks for leaked credentials before commit
```

You don't have to invoke them by hand at every step — once the right `description:` is in place, Claude routes to them when the conversation calls for it.

### Parallel isolation when composing writers

When two or more **writing** agents are spawned to run concurrently (e.g., `@dotnet-architect` + `@react-architect` for a full-stack feature, or two architects on independent modules), each MUST be dispatched with `isolation: "worktree"` so they don't clobber each other's edits on the shared working tree. Read-only auditors (`@code-plan-verifier`, `@gitignore-auditor`, `@secret-auditor`) are exempt — they can run alongside writers without isolation.

See [`parallel-isolation.md`](parallel-isolation.md) for the dispatch contract, the `Parallel: yes` task convention, and the concrete failure mode this prevents.

## Adding an agent

1. Create `global/agents/<name>.md` with frontmatter:
   ```yaml
   ---
   name: <name>
   description: One specific sentence — lead with "Use when/for/after…" and name the trigger.
   tools: Read, Write, Edit, Glob, Bash
   ---
   ```
2. Below the frontmatter, write the system prompt — what the agent does on activation, its rules, its output format.
3. Run `python setup/settings-configurator-ui.py`.
4. Restart Claude Code.

**Description-writing rule**: distinct enough that Claude can pick *only this one* when the trigger appears. Read [`architecture.md`](architecture.md#5-ready--how-claude-picks-a-tool) for the resolution algorithm.
