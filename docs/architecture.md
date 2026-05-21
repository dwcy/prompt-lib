# Architecture — how Claude Code wires everything together

> Read this first.

Every Claude Code session goes through a fixed five-step boot. Knowing the order tells you exactly where to put new things and why a "missing" agent or skill is missing.

## Session boot, in order

```
1. Settings resolved      (~/.claude/settings.json + .claude/settings*.json — project wins)
2. Context loaded         (~/.claude/CLAUDE.md, project CLAUDE.md, conditional rules)
3. Tools registered       (built-ins, agents, skills, MCP servers, plugin assets)
4. Hooks fire             (SessionStart — injects additionalContext)
5. Ready                  (Claude matches your input to a tool)
```

### 1. Settings resolved

Three files merge into one effective configuration:

| File | Purpose | Tracked? |
|---|---|---|
| `~/.claude/settings.json` | Global — what this repo deploys | No |
| `.claude/settings.json` | Project — committed, team-shared | Yes |
| `.claude/settings.local.json` | Project — your machine only | No |

Project wins on conflict. See [`settings.md`](settings.md) for every field.

### 2. Context loaded (eats tokens)

- `~/.claude/CLAUDE.md` — always loaded. This is your durable behavioural baseline (commit rules, tone, "never edit env files", etc.).
- Project `./CLAUDE.md` — always loaded if present. Project-specific conventions.
- `~/.claude/rules/*.md` — only loaded if the file paths Claude touches match the rule's `paths:` glob. Free until relevant.

### 3. Tools registered (cheap — only descriptions are scanned)

- **Built-in tools** — Read, Write, Edit, Bash, Grep, Glob, Task, etc.
- **Agents** — every `*.md` in `~/.claude/agents/` and `.claude/agents/`. Only the `description:` is loaded into the matcher; the body fires only when the agent is invoked.
- **Skills** — every `*.md` in `~/.claude/skills/` and `.claude/skills/`. Same: description scanned, body injected on `/invoke`.
- **MCP servers** — every entry in `mcpServers`. Each server's tools are exposed by name + description.
- **Plugins** — installed via `/plugin install`, kept in a separate cache (`~/.claude/plugins/`), merged at runtime. Currently enabled: `azure@claude-plugins-official`, `microsoft-docs@claude-plugins-official`.

### 4. Hooks fire

`SessionStart` runs `session-start.ps1` which inspects the cwd:

- **No `CLAUDE.md`** → injects "ask the user to describe this project so I can scaffold one."
- **`CLAUDE.md` exists** → injects "invoke `@load-project` to brief yourself on this project's conventions."

This is why opening a fresh session in any project feels coherent — the hook bootstraps context for you.

### 5. Ready — how Claude picks a tool

```
You type: "let's commit this"
          │
          ▼
Claude scans every registered tool's name + description
          │
          ├─ skills/commit.md description: "Lightweight quick commit…"
          ├─ skills/git.md     description: "Full git workflow with branch safety…"
          │                                               ✓ best match
          ▼
Claude injects skills/git.md body and follows it
```

Three things break this:

| Problem | Symptom | Fix |
|---|---|---|
| Two tools have similar descriptions | Claude picks the wrong one | Make descriptions distinct and concrete (see `global/README.md` examples) |
| Description is vague ("git stuff") | Claude guesses or asks | Lead with a verb, name the trigger words explicitly |
| Description duplicates with a plugin | Both fire or one shadows the other | Disable the plugin entry or rename your local skill |

## How a subagent runs

A subagent (`@dotnet-architect`, `@code-plan-verifier`, etc.) is a **separate Claude session** with its own system prompt and a restricted tool set. It receives the parent's task as input, runs to completion, and returns a single message.

```
Main thread: "verify this feature against plan.md"
          ▼
spawns @code-plan-verifier (tools: Read, Grep, Glob, Bash, WebSearch, WebFetch)
          ▼
subagent runs in isolation — its scratch tool calls are NOT in your context
          ▼
returns one summary message → main thread sees only the summary
```

Subagents protect your context window from large file reads and tool-call noise. Use them for any open-ended investigation that would otherwise pollute the main conversation.

## How a skill runs

A skill (`/git`, `/review`) is **just text injected into the current conversation**. No subagent, no isolation. Whatever the skill body says, the main Claude proceeds to do, with the tools listed in `allowed-tools:`.

```
You type: /commit
          ▼
Claude reads skills/commit.md → injects its body as the next instruction
          ▼
Claude runs `git diff --staged`, drafts a message, asks for confirmation
```

## How an MCP tool is called

```
You type: "search GitHub for issues tagged bug"
          ▼
Claude sees github MCP tools registered (e.g. github__search_issues)
          ▼
Calls: github__search_issues(query="label:bug")
          ▼
MCP server (`pnpm dlx` or `uvx`) returns JSON → Claude summarises
```

MCP servers run as long-lived stdio subprocesses for the duration of the session. `${ENV_VAR}` placeholders in `settings.json` are substituted from the shell that launched Claude Code — not from `.env` files. See [`settings.md`](settings.md#mcp-environment-variables) for the env-var lifecycle.

## Why this layout

- **`global/`** is the source of truth. You edit here, run `setup/settings-configurator-ui.py`, and the deployed config under `~/.claude/` is overwritten.
- **`.claude/`** at the project root is for project-only commands and overrides. Not deployed.
- **`services/`** are runtime daemons, not config. They run as separate processes and use the A2A protocol to talk to other agents.
- **`specs/`** is spec-kit driven design — feature trees that produce `services/` implementations. The spec is the source of truth for the service.
- **`setup/`** is the installer; everything Python-based, no shell required (bash fallback exists in `setup/tools/`).
