# Rules, output styles, and project templates

Three loosely related mechanisms that each shape Claude's behaviour in a different way.

## Rules — file-pattern conditional context

A rule is a markdown file in `global/rules/` with a `paths:` glob in its frontmatter. The body loads into Claude's context **only when** Claude is about to touch a file that matches the glob. Free until relevant — no token cost, no preamble bloat.

### Currently shipped

| File | Loads when | Contains |
|---|---|---|
| `csharp.md` | Editing `**/*.cs` | C# conventions — naming, async patterns, nullability, file-scoped namespaces, etc. |
| `typescript.md` | Editing `**/*.ts`, `**/*.tsx` | TypeScript conventions — strict types, no `any`, import sort, etc. |
| `react.md` | Editing `**/*.tsx`, `**/components/**/*.ts`, `**/features/**/*.ts`, `**/hooks/**/*.ts`, `**/state/**/*.ts` | React 2025 idioms — function components, hook patterns, file colocation |
| `tests.md` | Editing test files (`**/*Tests*/**/*.cs`, `**/*Test.cs`, `**/*.test.ts`, `**/*.test.tsx`, `**/*.spec.ts`) | Test conventions across stacks |

### Why this beats putting it in CLAUDE.md

`~/.claude/CLAUDE.md` is loaded **every session, regardless of what you're doing**. Putting C# rules there means a Python project pays for them too. Rules let you scope domain-specific guidance to the language or layer it applies to.

### Adding a rule

```yaml
---
description: Short — when does this load?
paths:
  - "**/*.your-extension"
---

Conventions to apply when editing these files…
```

Drop it in `global/rules/`, run `setup/apply.py`, restart.

## Output styles — response formatting profiles

An output style is a markdown file in `global/output-styles/` with a `name:` and a body of formatting rules. Pick one per session via `/output-style <name>`.

### Currently shipped

| Style | Best for | Behaviour |
|---|---|---|
| `concise` | Everyday coding | No preamble, no summaries, no filler. Code first. |
| `technical` | Architecture decisions, complex debugging | Thorough — full code examples, reasoning, tradeoffs. |
| `review` | PR reviews, code audits | Findings organised by severity (Critical / Warning / Suggestion) with concrete fixes. |
| `architect` | Design discussions, planning | High-level — patterns, structure, tradeoffs over implementation details. |

### Why styles instead of restating in every prompt

You don't want to type "be concise, no summaries, code first" every time. Style files are durable + switchable.

### Frontmatter

```yaml
---
name: your-style
description: One sentence — when to pick this style.
keep-coding-instructions: true
---
```

`keep-coding-instructions: true` means the style adds to the global coding rules (in `~/.claude/CLAUDE.md`) rather than replacing them. Almost always what you want.

## Project templates — used by `@init-project`

Project templates live in `global/project-templates/` and drive what `@init-project` asks the user when scaffolding a new project's `CLAUDE.md`.

### Currently shipped

| Template | Stack |
|---|---|
| `dotnet.md` | .NET projects — solution layout, Clean Architecture preferences, test framework, ORM |
| `python.md` | Python — FastAPI / Django / CLI, packaging, async, DB |
| `frontend.md` | React / Vue / Next.js (non-2025-stack) |
| `monorepo.md` | Mono-repos — package manager, workspace tooling, build orchestrator |
| `unity.md` | Unity3D — render pipeline, target platforms, asset organisation |
| `other.md` | Generic fallback — open-ended questions, freeform |

Each template has two sections:

1. **`## Questions`** — what `@init-project` asks the user.
2. **`## CLAUDE.md Template`** — the structure of the populated `CLAUDE.md` that gets written, with placeholders for the answers.

### How a template gets used

```
You: "let's set up this project"
  ↓
Claude routes to @init-project (description match)
  ↓
@init-project scans the cwd for stack hints (*.sln, package.json, pyproject.toml, etc.)
  ↓
Picks the matching template file from project-templates/
  ↓
Asks the questions from "## Questions"
  ↓
Fills "## CLAUDE.md Template" with answers, writes it to ./CLAUDE.md
  ↓
Announces which specialist subagents are now available for the session
```

### Adding a template

1. Create `global/project-templates/<name>.md` with the two-section format.
2. Add a hint in `global/agents/init-project.md` so the agent knows when to pick this template (e.g. "for Rust projects, use `rust.md`").
3. `python setup/apply.py` → restart.
