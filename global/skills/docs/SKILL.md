---
name: docs
description: Generate a comprehensive /docs folder for the current project — index, architecture overview, per-component reference files (agents, skills, services, modules, APIs, config), settings reference, composition workflows, and a learning path. Use when a project has grown enough that newcomers need orientation, when you want to capture the "why" behind components alongside the "what", when a single README has become too dense and needs to be split, or when the user says "write docs", "document this repo", "generate a docs folder", or "explain the project structure". Always reads source first; never fabricates features.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

Announce at start: "I'm using the docs skill to generate a /docs folder for this project."

## What this skill produces

A `/docs` folder with a small set of focused, cross-linked markdown files in a consistent house style. Each file answers a single question. No file is longer than it needs to be. Tables are preferred over prose for any enumeration.

The default set (omit, merge, or rename based on what the project actually has):

| File | Question it answers |
|---|---|
| `README.md` | What's in this folder, what order to read it in. |
| `architecture.md` | How does the system boot / load / run? How do the pieces fit? |
| `<components-A>.md` | What does each <thing-A> do, when does it fire, why does it exist? |
| `<components-B>.md` | Same for the next major axis. |
| `settings.md` (or `config.md`) | What does each configuration field do? |
| `workflows.md` | How are components composed into named end-to-end flows? |
| `learning.md` | What's the fastest path to fluency? What surprises to avoid? |

Adapt the axes to the project. Examples of what "components" can mean:

- A Claude Code config repo → agents, skills, hooks, rules, output styles
- A web app → routes, services, stores, components
- A CLI tool → commands, subcommands, plugins
- A library → public modules, internal modules, extension points
- A service → endpoints, jobs, message handlers, integrations

## Step 1 — Survey the repo (mandatory before writing anything)

Do this work yourself; do not delegate. **Never write docs from assumptions** — every claim in the docs must come from a file you have read.

1. `Glob` for top-level structure: list the directories under the repo root.
2. Read the root `README.md`, `CLAUDE.md`, `package.json` / `pyproject.toml` / `*.csproj` / `Cargo.toml` — whichever exist. These tell you the stack and the author's framing.
3. Identify the natural component axes (see examples above). State them back to the user before writing if ambiguous.
4. For each axis, `Glob` the relevant directory and read **every** file's frontmatter or top docstring. Skim bodies for the non-obvious parts (when something fires, why it exists, what it composes with).
5. Read any existing config file end-to-end (`settings.json`, `appsettings.json`, env schema, etc.) — `settings.md` will document every field.
6. Skim any `specs/` or `.specify/` tree if present. Note feature trees and their status.

If something doesn't make sense from the code alone, ask the user one focused question. Don't guess.

## Step 2 — Confirm the table of contents

Before writing files, propose the TOC back to the user as a single message:

```
Proposed /docs structure:

1. README.md          — index + reading order
2. architecture.md    — <one-line description tailored to the project>
3. <axis-1>.md        — <each component on this axis>
4. <axis-2>.md        — <each component on this axis>
5. settings.md        — every config field explained
6. workflows.md       — <N> named composition recipes
7. learning.md        — day-by-day path + anti-patterns

Anything I should rename, merge, split, or skip?
```

Wait for confirmation or redirection. Adjust, then proceed.

## Step 3 — House style for every file

Apply these rules to every doc file you write.

### Open with the question, not a sales pitch

First sentence states the question the file answers. No tagline, no preamble. Example:

> Every Claude Code session goes through a fixed five-step boot.

Not:

> Welcome to the architecture documentation! This file is going to walk you through the exciting journey of…

### Tables over prose for any enumeration

Whenever you would write "There are several X — A which does this, B which does that, C which does the other" — use a table.

| X | Tools | When | Why |
|---|---|---|---|

### Per-component entries follow a fixed shape

For each agent, skill, hook, service, route, command — the entry has:

```
#### `<name>`
- **When**: the trigger or lifecycle event.
- **Tools** / **Args** / **Inputs**: what it takes.
- **Why**: the non-obvious reason it exists (the problem it solves, not what the name already says).
- **Composes with**: other components it pairs naturally with.
```

If a field doesn't apply, skip it. Don't pad.

### Lead descriptions with the trigger

In a list of components, the description starts with "When…", "Use after…", "Use for…", or a verb. Not "This is a…".

### Cross-link freely

Every file should link to the others at natural moments. Use relative paths: `[settings.md](settings.md)`. The index should point to all of them in reading order.

### One concept per file

If a file is over ~250 lines, split it. The point is focused reference, not a manual.

### No emojis

Unless the user explicitly asks. Tables and headings carry the structure.

### Diagrams as ASCII

If you need a flow diagram, use a plain ASCII tree or arrow chart. No mermaid unless the user asks. Example:

```
You type: "let's commit this"
          │
          ▼
Claude scans every registered tool's description
          │
          ▼
Picks the best match → injects skill body → runs it
```

### Anti-patterns section in `workflows.md`

Every workflows file ends with a short "Anti-patterns" section — common mistakes that this composition surface invites. This is high-value content; don't skip it.

### `learning.md` is a path, not a glossary

Structure it as Day 1 / Day 2 / Day 3 / … with concrete outcomes per day. End with "Mental shortcuts", "Debugging surprises", and "What NOT to do". Each shortcut is one line.

## Step 4 — Write the index last

`docs/README.md` is written **after** the other files exist, so the reading order is grounded in real files. The index has:

1. A one-line description of what's in the folder.
2. A "Reading order" numbered list with one-line descriptions of each file.
3. A "Conventions used in these docs" section explaining notation specific to the project (e.g. `@agent-name`, `/skill-name`, `hook → event`).

## Step 5 — Wire the docs into the root

Add a single bullet to the root `README.md` under the existing "Further reading" / "Documentation" section, pointing at `docs/`. Do **not** rewrite the root README — just add the link.

If there is no such section, propose the bullet to the user before adding it.

## Step 6 — Verify

Before reporting done:

1. Re-read every file you wrote. Catch fabrication. Every component, field, and behaviour mentioned must trace back to a file in the repo.
2. Confirm every cross-link resolves to a real file.
3. Confirm no file is over ~250 lines; if one is, split it.
4. Confirm no emojis crept in.
5. Confirm the table-of-contents in `docs/README.md` matches the files on disk.

Report back with: the list of files created, the axes you chose, and one sentence per file describing what's inside.

## When NOT to use this skill

- For a single file that just needs better inline comments — edit the file, don't write a doc folder.
- For API reference that should be auto-generated from code — point the user at the appropriate tool (typedoc, sphinx, docfx) instead.
- For a tutorial walkthrough — that's a different document type; offer to write a `TUTORIAL.md` at the root instead.
- When the project is too small (< ~10 components total across all axes) — a single well-structured README is better than a `docs/` folder.

## Iron rules

- **Never fabricate.** If you didn't read it, don't write it.
- **No sales pitch.** This is reference documentation, not marketing.
- **One file per question.** If two files would answer the same question, merge them.
- **Tables over prose.** For any enumeration of three or more items.
- **Cross-link generously.** Reference docs are entered at arbitrary points; the reader needs to navigate.
- **Verify before reporting done.** Re-read your own output. Fix what's wrong before claiming completion.
