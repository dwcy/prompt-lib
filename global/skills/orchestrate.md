# /orchestrate — Automatic Subagent Routing

Route a task to the right specialist subagent(s) automatically. Analyses the task, selects agents from the registry, dispatches with worktree isolation when needed, and aggregates results.

**Usage:** `/orchestrate <task description>`

---

## Step 1 — Analyse the task

Read the task description and identify two things:

**Domain signals** — what technology or system is involved?
- `.NET` / `C#` / `csproj` / CQRS / MediatR / Clean Architecture
- Python / FastAPI / Django / SQLAlchemy / `pyproject.toml`
- React / Vue / Next.js / Nuxt / Angular / Vite / Zustand / TanStack
- CSS / design tokens / `globals.css`
- UI design / UX / wireframe / design system / typography
- new UI component / content page / interaction behaviour / UX best practice / a11y review
- Unity / MonoBehaviour / ScriptableObject / scene
- Raspberry Pi / Arduino / GPIO / I2C / sensor
- GitHub settings / branch protection / secret scanning
- `.gitignore` / staged files / pre-commit
- API keys / secrets / credentials / tokens
- New project / init / scaffold
- requirements / user stories / acceptance criteria / scope
- dataset / CSV / data analysis / metrics / SQL query results
- API contract / endpoints / OpenAPI / GraphQL schema / REST
- database schema / migration / indexing / data model
- URL / web page / article / docs page / changelog (research a link)
- repo URL / GitHub repository (analyse / mine for features or code)

**Phase signals** — what kind of work is it?
- `architect` / design / structure / review / DI / domain
- `test` / xUnit / NUnit / pytest / fixture / NSubstitute / Moq
- `implement` / scaffold / build
- `verify` / check / "does the code match"
- `audit` / scan
- `design` / UX / wireframe / mockup
- `analyse` / research / extract / profile / explore
- `configure` / set up

---

## Step 2 — Select agent(s)

Match domain + phase against this routing table. Apply the **highest-priority matching row**. If multiple independent domains are present, select one agent per domain.

| Priority | Domain signals | Phase signals | Agent |
|---|---|---|---|
| 1 | .NET / C# / csproj / CQRS / MediatR | test / xUnit / NUnit / NSubstitute / Moq / TestContainers | `dotnet-tester` |
| 2 | .NET / C# / csproj / CQRS / MediatR / Clean Architecture | architect / design / structure / review / DI / domain | `dotnet-architect` |
| 3 | TanStack Router / TanStack Query / TanStack Form / TanStack Table / typed routes / route loaders | any | `tanstack-architect` |
| 4 | React + (Vite / Zustand / Biome / Zod / MUI Icons) | architect / design / component / state | `react-architect` |
| 5 | React / Vue / Next.js / Nuxt / Angular (not Vite+Zustand stack) | architect / design / component / state | `frontend-architect` |
| 6 | CSS / globals.css / design tokens / theming / CSS modules | implement / scaffold / audit | `frontend-css` |
| 7 | UI design / UX / wireframe / design system / colors / typography / mockup | design / plan / vision | `frontend-designer` |
| 8 | Python / FastAPI / Django / SQLAlchemy / pyproject.toml | test / pytest / fixture / async test | `python-tester` |
| 9 | Python / FastAPI / Django / SQLAlchemy / pyproject.toml | architect / design / structure / async / service layer | `python-architect` |
| 10 | Unity / MonoBehaviour / ScriptableObject / scene / prefab / Assets/ | architect / design / review | `unity-architect` |
| 11 | Raspberry Pi / Arduino / GPIO / I2C / SPI / UART / sensor / motor / servo | any | `pi-arduino-architect` |
| 12 | GitHub settings / branch protection / secret scanning / Dependabot | configure / set up / audit | `github-config-manager` |
| 13 | .gitignore / staged files / pre-commit / `git add` | audit / check | `gitignore-auditor` |
| 14 | API keys / secrets / credentials / tokens / passwords | scan / audit / pre-commit | `secret-auditor` |
| 15 | new project / CLAUDE.md missing / init / scaffold | setup / initialise | `init-project` |
| 16 | verify / plan conformance / "does the code match" / architecture review | verify / check / audit | `code-plan-verifier` |
| 17 | requirements / user stories / acceptance criteria / scope / vague request | analyse / scope / elicit | `requirements-analyst` |
| 18 | dataset / CSV / Parquet / SQL results / metrics / logs | analyse / profile / explore | `data-analyst` |
| 19 | API contract / endpoints / OpenAPI / GraphQL schema / REST surface | design / structure | `api-designer` |
| 20 | database schema / migration / indexing / normalisation / data model | architect / design / review | `db-architect` |
| 21 | URL / web page / article / docs page / changelog (a link to read) | analyse / research / extract | `website-content-analyst` |
| 22 | repo URL / GitHub repository / clone (mine for features or code) | analyse / research / extract | `git-repo-analyst` |
| 23 | new UI component / content page / interaction behaviour / a11y / UX best practice | analyse / review / question | `ux-analyst` |

**If no row matches:** say "No specialist matched — handling in main session" and continue without delegation.

**If ambiguous between two rows:** pick the higher-priority (lower number) row and tell the user which agent was chosen and why.

Tell the user which agent(s) you selected and why before dispatching.

---

## Step 3 — Determine dispatch mode

**Parallel** — when two or more agents are selected for independent domains:
- Requires `isolation: "worktree"` on every agent that writes files
- Read-only agents (`gitignore-auditor`, `secret-auditor`, `code-plan-verifier`) are exempt — no isolation needed
- Name worktree branches: `orchestrate/<agent-name>/<short-task-slug>`

**Sequential** — when agents form a pipeline (output of one feeds the next):
- Common pipelines: `frontend-designer` → `react-architect` → `code-plan-verifier`
- **New UI component / content page = a trio**: dispatch `ux-analyst` (behaviour, states, best-practice questions) alongside `frontend-designer` (look + design system), then hand both to the UI developer (`react-architect` / `tanstack-architect` / `frontend-architect` / `frontend-css`). `ux-analyst` does not decide — its brief informs the designer's and architect's decisions.
- Pass each agent's result as context to the next agent's prompt
- Still use `isolation: "worktree"` for each writing agent

**Single agent** — dispatch directly; use `isolation: "worktree"` if it writes files.

---

## Step 4 — Dispatch

For each agent, call:

```
Agent(
  subagent_type: "<agent-name>",
  isolation: "worktree",           ← omit only for read-only agents
  prompt: "<task context + any prior agent output if sequential>"
)
```

For parallel agents, dispatch all in a single message (multiple Agent tool calls). Set `run_in_background: true` on all but the last so they run concurrently.

---

## Step 5 — Aggregate results

**Single agent:** present the result directly.

**Parallel agents:**
1. Collect both results
2. Merge each returned worktree branch into the integration branch sequentially
3. If there are file conflicts, report them per-file — do NOT auto-resolve
4. Present a combined summary: what each agent did, any conflicts

**Sequential pipeline:**
1. Present the final agent's output
2. Note which agents ran and in what order

---

## Step 6 — Report

Always end with:
- Which agent(s) ran
- What was produced or changed
- Any conflicts or issues that need user attention
- What to do next (e.g. "Run `/orchestrate verify` to confirm the implementation matches the plan")
