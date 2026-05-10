# Claude Code — Global Configuration

Personal global configuration for [Claude Code](https://claude.ai/code). Contains agents, hooks, project templates, and settings that apply across all projects.

## How Claude Code resolves context at session start

Every time a session starts, Claude Code builds its context by merging sources in a fixed order. Understanding this helps you know where to put things.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SESSION START                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────▼───────────────┐
          │     1. SETTINGS RESOLVED      │
          │  ~/.claude/settings.json      │
          │  .claude/settings.json        │  ← merged, project wins
          │  .claude/settings.local.json  │
          └───────────────┬───────────────┘
                          │
          ┌───────────────▼───────────────┐
          │   2. CONTEXT LOADED (tokens)  │
          │                               │
          │  ~/.claude/CLAUDE.md          │  ← always loaded
          │    └─ @imports (design.md…)   │  ← pulled in via @import
          │  ./CLAUDE.md                  │  ← project-level (if exists)
          │  .claude/rules/*.md           │  ← only if paths match
          └───────────────┬───────────────┘
                          │
          ┌───────────────▼───────────────┐
          │   3. TOOLS REGISTERED         │
          │                               │
          │  Built-in tools               │  ← Read, Write, Edit, Bash…
          │  ~/.claude/agents/*.md        │  ← global agents (descriptions
          │  .claude/agents/*.md          │    loaded, not full content)
          │  ~/.claude/skills/*.md        │  ← global slash commands
          │  .claude/skills/*.md          │  ← project slash commands
          │  MCP servers (settings.json)  │  ← tools from all MCP servers
          │  Plugin assets                │  ← agents/skills from plugins
          └───────────────┬───────────────┘
                          │
          ┌───────────────▼───────────────┐
          │   4. HOOKS FIRE               │
          │                               │
          │  SessionStart hook runs       │  ← our session-start.ps1
          │    ├─ No CLAUDE.md found?     │
          │    │   └─ injects: ask user   │
          │    │      to describe project │
          │    └─ CLAUDE.md exists?       │
          │        └─ injects: invoke     │
          │           @load-project       │
          └───────────────┬───────────────┘
                          │
          ┌───────────────▼───────────────┐
          │   5. READY — USER TYPES       │
          │                               │
          │  Claude matches intent to:    │
          │   • Agent descriptions        │  ← autonomous invocation
          │   • /skill-name               │  ← explicit invocation
          │   • MCP tool names            │  ← tool calls mid-response
          │   • Built-in tools            │
          └───────────────────────────────┘
```

### How agents are triggered

```
You type: "let's set up this project"
          │
          ▼
Claude reads all agent descriptions in memory
          │
          ├─ init-project: "Initializes a new project by detecting
          │                 the stack, asking architecture questions…"
          │                          ✓ MATCH
          ▼
Claude spawns @init-project as a subagent
          │
          ▼
Subagent runs with its own tools + system prompt
  ├─ Reads file tree (Glob)
  ├─ Asks you questions (AskUserQuestion)
  ├─ Reads template (Read)
  └─ Writes CLAUDE.md (Write)
          │
          ▼
Returns result to main Claude thread
```

### How skills are triggered

```
You type: /commit
          │
          ▼
Claude finds skills/commit.md → injects its content as instructions
          │
          ▼
Executes within current context (no subagent spawned)
  └─ Runs git diff --staged, generates message, asks confirmation
```

### How MCP tools are used

```
You type: "search GitHub for issues tagged bug"
          │
          ▼
Claude sees github MCP tools are available
          │
          ▼
Calls: github__search_issues(query="label:bug")
          │
          ▼
MCP server executes → returns results → Claude summarises
```

### How Claude resolves overlapping tools

```
You type: "search GitHub for issues"
          │
          ▼
Claude scans ALL available tools:
  ├─ Skills:   browser (description: "opens a URL and returns content")
  ├─ MCP:      playwright (description: "browser automation — click, fill, screenshot")
  └─ MCP:      github (description: "search repos, issues, PRs via GitHub API")
          │
          ├─ "search GitHub" → github MCP is the clear semantic match ✓
          │
          ▼
Calls: github__search_issues(query="label:bug")
```

When two tools both seem relevant:

| Scenario | Claude's behaviour |
|---|---|
| One tool matches clearly | Uses it — no ambiguity |
| Two tools both plausible | Picks MCP over skill (more specific by convention) |
| Still ambiguous after that | Asks once: "Did you mean playwright or the browser skill?" |
| Description is vague ("browser stuff") | Guesses — may pick the wrong one |

#### The fix: write distinct, non-overlapping descriptions

| Tool | Bad description | Good description |
|---|---|---|
| playwright MCP | "browser tool" | "browser automation — click, fill forms, screenshot, E2E test flows" |
| browser skill | "browser tool" | "open a URL and return its text content for reading" |
| context7 MCP | "docs" | "fetch up-to-date library documentation by package name" |

**Rule:** the more specific your description, the less Claude guesses. If two tools do different things, their descriptions should make that obvious at a glance.

---

## How it works (session flow)

On every new Claude Code session, a `SessionStart` hook runs and checks the current directory:

- **No `CLAUDE.md` found** → Claude asks whether you want to describe the project now (and creates `CLAUDE.md` from your description) or skip and be reminded next session.
- **`CLAUDE.md` exists** → Claude is prompted to invoke `@load-project`, which reads the existing conventions and announces which specialist subagents are available for the session.

Specialist subagents (e.g. `@dotnet-architect`, `@python-tester`) are then available on demand for the rest of the session — invoked by you or automatically by Claude when the task matches.

## First-time setup

Before applying the config, register your environment variables. These are read by the MCP servers at runtime via `${VAR_NAME}` substitution in `settings.json`.

**1. Fill in your values**

Edit `setup/setup.env.json` at the repo root:

```json
{
  "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_...",
  "FIGMA_ACCESS_TOKEN": "figd_...",
  "POSTGRES_CONNECTION_STRING": "postgresql://user:pass@host:5432/db",
  "AZURE_DEVOPS_ORG_URL": "https://dev.azure.com/your-org",
  "AZURE_DEVOPS_TOKEN": "...",
  "SUPABASE_ACCESS_TOKEN": "sbp_...",
  "OBSIDIAN_API_KEY": "...",
  "OBSIDIAN_HOST": "127.0.0.1",
  "OBSIDIAN_PORT": "27123",
  "PROJECTS_PATH": "/c/projects",
  "TEMP_PATH": "/tmp"
}
```

**2. Run the setup script**

```bash
bash setup/setup.sh
```

This reads `setup.env.json` and persists every key as a user-level environment variable — written to `~/.bashrc` / `~/.zshrc` on Linux/macOS, and additionally registered via `setx` on Windows so they're available in cmd and PowerShell too. Keys with empty values are skipped.

Restart your terminal after running.

**3. Apply the Claude config**

```bash
bash scripts/apply-global-claude-settings.sh
```

---

## Applying changes

After editing any file in this folder, run from Git Bash:

```bash
bash scripts/apply-global-claude-settings.sh
```

This copies everything into `~/.claude` and backs up the existing `settings.json`. Restart Claude Code after applying.

## Structure

```
global/
├── scripts/
│   └── apply-global-claude-settings.sh   # Deploy script — copies files to ~/.claude
├── settings.json                     # Global Claude Code settings (theme, model, hooks)
├── CLAUDE.md                         # Global always-on context — imports design.md + preferences
├── design.md                         # Design philosophy — imported by CLAUDE.md via @import
├── keybindings.json                  # Custom keyboard shortcuts
│
├── agents/                           # Custom agents (~/.claude/agents/)
│   ├── init-project.md               # Orchestrator: initializes a new project
│   ├── load-project.md               # Orchestrator: loads context for an existing project
│   ├── dotnet-architect.md           # .NET architecture specialist
│   ├── dotnet-tester.md              # .NET testing specialist (xUnit, TestContainers)
│   ├── python-architect.md           # Python architecture specialist (FastAPI, SQLAlchemy)
│   ├── python-tester.md              # Python testing specialist (pytest, async)
│   ├── frontend-architect.md         # Frontend architecture specialist (React, Vue, Next.js)
│   ├── frontend-css.md               # CSS architecture specialist (modules, globals, theming)
│   ├── react-architect.md            # React 2025 stack specialist (Vite/Zustand/Biome/Tailwind)
│   ├── tanstack-architect.md         # Opinionated TanStack specialist (Start/Router/Query/Form/Table)
│   └── unity-architect.md            # Unity3D architecture specialist
│
├── hooks/                            # Hook scripts (~/.claude/hooks/)
│   └── session-start.ps1             # SessionStart hook — detects project state
│
├── output-styles/                    # Response formatting styles (~/.claude/output-styles/)
│   ├── concise.md                    # Short and direct — code first, no filler
│   ├── technical.md                  # Deep dives with full examples and tradeoffs
│   ├── review.md                     # Structured code review — Critical / Warning / Suggestion
│   └── architect.md                  # High-level design focus — patterns and tradeoffs
│
├── rules/                            # Conditional rules (~/.claude/rules/)
│   ├── csharp.md                     # Loaded only when editing *.cs files
│   ├── typescript.md                 # Loaded only when editing *.ts / *.tsx files
│   ├── react.md                      # Loaded for React components, hooks, features, api, state
│   └── tests.md                      # Loaded only when editing test files
│
├── skills/                           # Global slash commands (~/.claude/skills/)
│   ├── react-init.md                 # /react-init — scaffold full React 2025 project interactively
│   ├── react-review.md               # /react-review — code quality + architecture review (Critical/Warning/Suggestion)
│   ├── react-test.md                 # /react-test — scaffold or review tests with Vitest + RTL
│   ├── react-safe.md                 # /react-safe — async, error handling, and security audit
│   ├── react-perf.md                 # /react-perf — re-renders, lazy-load, bundle, and query audit
│   └── skill-create.md               # /skill-create — create, test, and refine new Claude Code skills
│   ├── git.md                        # /git [commit|branch|init] — full git workflow with safety checks
│   ├── commit.md                     # /commit — quick conventional commit (no safety checks)
│   ├── standup.md                    # /standup — generate standup from git log
│   ├── pr.md                         # /pr — generate PR title + description, create with gh
│   ├── review.md                     # /review — structured branch review against main
│   ├── css.md                        # /css [scaffold|ComponentName] — globals.css or CSS module
│   └── lovable-cleanup.md            # /lovable-cleanup — strip all Lovable/GPTEngineer scaffolding
│
└── project-templates/                # Templates used by init-project (~/.claude/project-templates/)
    ├── dotnet.md                     # .NET questions + CLAUDE.md template
    ├── python.md                     # Python questions + CLAUDE.md template
    ├── frontend.md                   # Frontend questions + CLAUDE.md template
    ├── monorepo.md                   # Monorepo questions + CLAUDE.md template
    ├── unity.md                      # Unity3D questions + CLAUDE.md template
    └── other.md                      # Generic fallback template
```

## MCP Configuration

MCP servers can be configured at three scopes:

| Scope | File | Committed to git | Available in |
|---|---|---|---|
| **Global** | `~/.claude/settings.json` → `mcpServers` | No | Every project on this machine |
| **Local** | `.claude/settings.local.json` → `mcpServers` | No | This project only, not shared |
| **Project** | `.mcp.json` in project root | Yes | This project, shared with the team |

### Global MCP servers (this file)

Servers in `settings.json` are available in every session. Currently configured:

| Server | Purpose | Requires |
|---|---|---|
| `context7` | Up-to-date library and framework documentation | Node.js |
| `github` | Read/write repos, issues, PRs, and code search | `GITHUB_PERSONAL_ACCESS_TOKEN` env var |
| `figma` | Access Figma files, components, and design tokens | `FIGMA_ACCESS_TOKEN` env var |
| `playwright` | Browser automation — E2E testing, scraping, screenshots | Node.js |
| `azure-devops` | Work items, repos, pipelines, and PRs in Azure DevOps | `AZURE_DEVOPS_ORG_URL` + `AZURE_DEVOPS_TOKEN` env vars |
| `supabase` | Manage Supabase projects — DB, auth, storage, edge functions | `SUPABASE_ACCESS_TOKEN` env var |
| `obsidian` | Read and search your Obsidian vault | Local REST API plugin + `OBSIDIAN_API_KEY` env var |
| `docker` | Manage containers, images, and volumes | Docker running locally |

See [MCP.md](./MCP.md) for full setup instructions, token configuration, and a list of suggested MCP servers.

Add more via `claude mcp add --scope user` or edit `settings.json` directly under `mcpServers`.

### Project MCP servers

Drop a `.mcp.json` into a project root to add project-scoped servers. Commit it to share with your team. Example structure:

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@scope/mcp-package@latest"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

### Local MCP servers

Add via `claude mcp add --scope local` — stored in `.claude/settings.local.json`, never committed.

## Switching output style

Use `/output-style` in any Claude Code session to pick a style for that session:

| Style | Best for |
|---|---|
| `concise` | Everyday coding — quick answers, code first |
| `technical` | Architecture decisions, complex debugging |
| `review` | PR reviews, code audits |
| `architect` | Design discussions, planning sessions |

## Adding a new output style

1. Create a `.md` file in `output-styles/` with the frontmatter below
2. Run `apply-global-claude-settings.sh`

```markdown
---
name: your-style-name
description: One sentence describing when to use this style.
keep-coding-instructions: true
---

Instructions for how Claude should format responses in this style...
```

## Adding a new agent

1. Create a new `.md` file in `agents/` with the frontmatter below
2. Run `apply-global-claude-settings.sh` to deploy
3. Restart Claude Code

```markdown
---
name: your-agent-name
description: One sentence describing when Claude should use this agent.
tools: Read, Write, Edit, Glob, Bash
---

Agent instructions here...
```

## Adding a skill (slash command)

1. Create a `.md` file in `skills/` with the frontmatter below
2. Run `apply-global-claude-settings.sh`
3. The skill is immediately available as `/skill-name` in any session

```markdown
---
name: your-skill-name
description: One sentence describing what this skill does.
allowed-tools: Bash, Read
---

Instructions for what Claude should do when this skill is invoked...
```

## Adding a rule

Rules load automatically when Claude touches a matching file — no token cost unless relevant.

1. Create a `.md` file in `rules/`
2. Add `paths:` frontmatter with glob patterns
3. Run `apply-global-claude-settings.sh`

```markdown
---
description: Short description of when this rule applies
paths:
  - "**/*.ext"
---

Rules to follow when editing these files...
```

## Customising keybindings

Edit `keybindings.json` and uncomment or add entries. Common actions:

| Action | Description |
|---|---|
| `chat:submit` | Submit the current message |
| `chat:newline` | Insert a newline without submitting |
| `chat:killAgents` | Kill all background agents |
| `chat:fastMode` | Toggle fast mode |
| `voice:pushToTalk` | Voice push-to-talk key |

Run `apply-global-claude-settings.sh` then restart Claude Code.

## Adding a new project template

1. Create a `.md` file in `project-templates/` following the existing format (a `## Questions` section and a `## CLAUDE.md Template` section)
2. Reference the new filename in `agents/init-project.md` under the file mapping
3. Run `apply-global-claude-settings.sh`

## Plugins vs this manual setup

### What is a plugin?

A plugin is a **GitHub repo** with a `plugin.json` manifest that Claude Code installs and manages. It can bundle everything in one package — agents, skills, hooks, MCP servers, output styles, and themes.

```
your-plugin-repo/
├── plugin.json          ← manifest
├── agents/
├── skills/
├── hooks/
│   └── hooks.json
├── output-styles/
├── themes/
└── mcp-servers/
```

Install on any machine with one command:
```
/plugin install your-github-username/repo-name
```

### Plugin vs manual bash script

| | This setup (manual) | Plugin |
|---|---|---|
| **Install on new machine** | Clone repo → `bash scripts/apply-global-claude-settings.sh` | `/plugin install you/repo` |
| **Update** | Edit files → run script | `/plugin update` or auto-updates |
| **Share with others** | Share repo + explain the script | `/plugin install you/repo` |
| **Claude manages lifecycle** | No — you manage files in `~/.claude/` | Yes — Claude Code owns the files |
| **Coexistence risk** | None | Duplicates if you mix both approaches |
| **Complexity** | Simple — plain files and a script | Requires `plugin.json` manifest + versioning |
| **Best for** | Active development of config | Stable config ready to distribute |

### How plugins and manual files coexist

Plugins install into a **separate cache** (`~/.claude/plugins/`) and do not overwrite your manual files in `~/.claude/`. Claude Code merges both at runtime:

```
~/.claude/agents/          ← your manual agents (this setup)
~/.claude/plugins/repo/    ← plugin assets (separate)
         ↓                          ↓
              Claude Code merges both at runtime
                    (all agents available)
```

⚠️ **Avoid mixing both** for the same content — you will get duplicates. Pick one approach per asset type.

### When to convert to a plugin

Keep the manual bash script approach while you are **actively building and tweaking** your config. Convert to a plugin when:

- The config is stable and you stop changing it frequently
- You want one-command install on new machines
- You want to share it with teammates
- You want Claude Code to auto-update it

Converting is straightforward — the `global/` folder structure already matches what a plugin expects. The main step is adding a `plugin.json` manifest and pushing to GitHub.

### Plugin manifest example

```json
{
  "name": "my-claude-config",
  "version": "1.0.0",
  "description": "Personal Claude Code configuration — agents, skills, hooks, and styles",
  "author": "your-github-username"
}
```

Claude Code discovers the agents, skills, output-styles, and hooks directories automatically from the repo structure.

## What is NOT tracked here

| File / Folder | Reason |
|---|---|
| `.credentials.json` | Auth tokens — never commit |
| `projects/` | Session transcripts and history |
| `backups/` | Auto-generated backups |
| `cache/`, `debug/`, `downloads/` | Runtime data |
| `file-history/`, `shell-snapshots/` | Runtime data |
