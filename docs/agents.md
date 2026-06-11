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

### Design specialists

#### `@frontend-designer`
- Visual UI + UX designer. Runs the Design Discovery Loop (language, fonts, colors, mobile-first, audience, theme, a11y floor) before any visual decision.
- If no direction exists: recommends wireframes, mockups, vision-paste of a reference screenshot, or AI exploration via Stitch / Google Antigravity — picks the cheapest fit for the project phase.
- Writes / edits a project-local `DESIGN.md` (tokens, breakpoints, components with full state coverage, do's and don'ts). Treats `~/.claude/design.md` as reference language, never as the default.
- Ends every pass with the work split into **UX issues** (flows, states, IA, a11y, copy) and **UI issues** (tokens, type, spacing, components, motion).
- Hard rules: never writes CSS or component code (hands off to `@frontend-css` / `@react-architect` / `@tanstack-architect` / `@frontend-architect`); never `#000`; mobile-first means base CSS is mobile and queries are `min-width`; touch targets ≥ 44×44 px; every animation has a `prefers-reduced-motion` fallback.

### Design & data specialists

#### `@ux-analyst`
- The behaviour + best-practice **quality gate** on every new UI component or content page. Pairs with `@frontend-designer` (look/design system) and the UI developer (`@react-architect` / `@tanstack-architect` / `@frontend-architect` / `@frontend-css`).
- Tools: `Read, Write, Edit, Glob, Grep` — writes UX briefs, never code.
- Asks **scoped** questions about the thing being added — states, validation timing, feedback/latency, edge data, keyboard/focus, reversibility (components); goal, hierarchy, entry/exit, page states, responsive behaviour, content (pages). Never a generic UX questionnaire.
- Suggests proven interaction patterns with trade-offs (pagination vs infinite scroll, confirm vs undo, wizard vs long form) and runs a consistency/a11y checklist (all states covered, keyboard operable, WCAG AA floor, reduced-motion, empty/loading/error designed, matches siblings).
- **Hard rule: it is not the decider.** It surfaces questions, options, and risks; the **architect or the user** decides. It stays out of the design system and the code. Output is a `UX-NOTES.md` brief that hands visual decisions to `@frontend-designer` and implementation to the UI developer.

#### `@requirements-analyst`
- Turns vague or conflicting asks into testable, prioritised requirements **before** anyone designs or codes.
- Tools: `Read, Write, Edit, Glob, Grep`.
- Runs an Elicitation Loop (goal/metric, actors, scope boundary, constraints, data/states, edge cases, NFRs), then writes/extends `REQUIREMENTS.md` (or the active `specs/**/spec.md`): numbered FRs with Given/When/Then acceptance criteria, MoSCoW priority, explicit assumptions, and open questions.
- Hard rules: every FR has an acceptance criterion; no solution language in requirements; mark every assumption; verifiable-or-cut.
- Hands off to `@db-architect`, `@api-designer`, and the language architects.

#### `@api-designer`
- Designs the client/server contract — REST / GraphQL / RPC — and produces a valid OpenAPI 3.1 or GraphQL SDL file plus an `API-DESIGN.md` rationale.
- Tools: `Read, Write, Edit, Glob, Grep`.
- Owns resource modelling, status codes, a single error envelope, pagination/filtering/sorting consistency, versioning policy, idempotency, and auth scopes.
- Hard rules: contract is the source of truth (must parse); consistency over cleverness; never `200` on failure; no verbs in REST paths; design for additive evolution. No business logic — hands off to the language architects.

#### `@db-architect`
- Schema design, key/type selection, normalisation vs deliberate denormalisation, indexing, migrations, transactions, and query performance across Postgres / SQL Server / MySQL / SQLite and document/KV stores.
- Tools: `Read, Write, Edit, Glob, Bash`.
- Produces DDL / ORM migrations in the project's format plus `DB-DESIGN.md` (entities, integrity rules, access-pattern→index map, lock-aware migration plan, trade-offs).
- Hard rules: constraints live in the schema; `decimal` not float for money; timezone-aware timestamps only; every FK indexed; justify each index/denormalisation; flag lock-taking migrations with the online-safe alternative.

#### `@data-analyst`
- Answers questions *from data* — profiles, cleans, computes metrics, finds patterns/anomalies in CSV/JSON/Parquet/SQL results/logs, and reports findings with the query behind each claim.
- Tools: `Read, Write, Edit, Glob, Bash`.
- Prefers DuckDB for ad-hoc SQL over files, polars/pandas for awkward transforms; keeps scratch scripts in `analysis/`.
- Hard rules: measure never guess; report n + caveats; cleaning is visible (record impact stated); correlation ≠ causation; no spurious precision.

### Analysis & research specialists

These take **links you provide** and read the real source — never a guess about what it "probably" says.

#### `@website-content-analyst`
- You hand it URLs (docs, articles, product pages, changelogs); it `WebFetch`es each, extracts the load-bearing facts/quotes/links, assesses relevance + credibility, and writes a cited findings report.
- Tools: `Read, Write, WebFetch, WebSearch` — read-only on the web.
- Hard rules: only report what it fetched (every source marked ✓/partial/✗); attribute every claim to a URL; quote precisely; separate fact from assessment; flag recency and contradictions.
- For code repositories, use `@git-repo-analyst` instead.

#### `@git-repo-analyst`
- You hand it a GitHub/GitLab repo URL (or local clone); it mines it in **two explicit stages**.
- Tools: `Read, Write, WebFetch, WebSearch, Bash, Glob, Grep`.
- **Stage 1 — Map**: purpose, health signals (stars/last release/maintenance/license), architecture at a glance, and a *ranked list of useful features* with paths — then asks which threads to deep-dive.
- **Stage 2 — Deep dive**: reads the real implementation of the chosen threads and extracts concrete code examples (`path:line` cited), the reusable pattern/idea, adaptation notes, and gotchas.
- Acquisition is cheapest-sufficient: raw-file `WebFetch` + `gh api` metadata for a light touch, shallow `git clone --depth 1` to scratch for a deep dive.
- Hard rules: two stages in order; cite real code (no from-memory snippets); read-only on the target; respect + state the license before suggesting reuse; flag staleness/security smells.

### Testing specialists

#### `@dotnet-tester`
- xUnit, integration tests with TestContainers, mocking with NSubstitute or Moq.
- Strategy decisions: what to mock, what to integration-test, what to leave out.

#### `@python-tester`
- pytest, async test patterns, fixture design, real-DB integration tests.

### GitHub specialists

#### `@github-config-manager`
- Interactive configurator for GitHub repo-level settings via `gh api`. Use after `git init` + first push, after `gh repo create`, after `git clone` on a repo you own, or whenever `/github-audit` flags missing settings.
- Tools: `Read, Bash, Glob, Grep` — calls `gh api` directly.
- Walks one Q&A covering security alerts (default OFF), push protection, code scanning, branch protection (PR required, approval count, admin enforcement), and Copilot code review. Conservative defaults across the board.
- Signed commits are never required (project-wide decision); the agent will not ask, will not enable.
- Knows the free vs paid matrix (public free / private no GHAS / private + GHAS / Copilot Business+). Always prints a `COST CHECK:` block before flipping any paid toggle and requires a second confirmation with the price.
- Always shows the exact `gh api` command before running it; backs up existing branch protection JSON before overwriting.
- Refuses on repos the user doesn't own.
- Composes with: `/github-scaffold` (writes the workflow files that branch protection then requires), `/github-audit` (read-only pre-flight), `@init-project` (optional post-push handoff).

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

#### `@owasp-security-reviewer`
- **When**: before releases, after auth/API changes, or when reviewing security-sensitive code.
- **Tools**: `Read, Grep, Glob, Bash` — read-only by default; patches only on explicit request.
- **Why**: defensive OWASP Top 10 / ASVS-style review of the whole codebase — access control, auth/session flows, CSRF, injection, XSS, crypto, misconfiguration, vulnerable dependencies, logging gaps, API exposure. Produces a severity-classified remediation report with file-level evidence; never generates exploits.

### Maintenance

#### `@code-cleaner`
- **When**: during refactoring, before releases, or when a repository has accumulated clutter.
- **Tools**: `Read, Grep, Glob, Bash, Edit` — a **writing** agent; needs worktree isolation when run alongside other writers.
- **Why**: evidence-based removal of dead code, dead CSS, unused assets, stale files, and unused dependencies. Classifies every candidate (safe to remove / manual review / keep), deletes in small verified batches, and stops + reverts if build/tests break. Uncertain cases are reported, never deleted.

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

When two or more **writing** agents are spawned to run concurrently (e.g., `@dotnet-architect` + `@react-architect` for a full-stack feature, or two architects on independent modules), each MUST be dispatched with `isolation: "worktree"` so they don't clobber each other's edits on the shared working tree. Read-only auditors (`@code-plan-verifier`, `@gitignore-auditor`, `@secret-auditor`, `@owasp-security-reviewer`) are exempt — they can run alongside writers without isolation.

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
