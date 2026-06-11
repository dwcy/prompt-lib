# Settings — `global/settings.json` field by field

The single most important file in this repo. This document explains every field, what it controls, and what changes when you edit it.

## Top-level fields

| Field | Current value | What it does |
|---|---|---|
| `autoUpdatesChannel` | `"latest"` | Which Claude Code release channel to track. `"latest"` follows stable; switch to a beta channel if you want to test pre-releases. |
| `theme` | `"dark"` | UI theme. Cosmetic. |
| `model` | `"sonnet"` | Default model picked at session start. Override per session with `/model`. Claude family aliases: `sonnet`, `opus`, `haiku`. |
| `defaultMode` | `"acceptEdits"` | Permission mode when a session starts. `acceptEdits` means edits to existing files are auto-approved; commands and writes still go through permission checks. Other modes: `default`, `plan`, `bypassPermissions`. |
| `statusLine` | command running `statusline.py` | Renders the bottom-of-screen status. Our script shows the full project path as a clickable link. Replace with any command that outputs a single line of text. |

## `permissions.allow` — auto-approved tool patterns

Each entry is a glob over a `Tool(arg-pattern)` shape. If a call matches, the tool fires without asking you. Categories currently allow-listed:

- **Network read** — `WebSearch`, `WebFetch`, `Fetch`
- **Read-only git** — `git status`, `git diff`, `git log`, `git branch`, `git rev-parse`, `git show`, `git config`, `git tag` — across both `Bash(...)` and `PowerShell(...)`
- **Safe git mutations** — `git init`, `git add`, `git checkout`, `git switch`, `git restore`, `git stash` (these don't push or destroy history)
- **Build/test runners** — `pnpm:*`, `bun:*`, `bunx:*`, `dotnet build/test/format/restore/new/add/sln/publish/pack/run/nuget`, `pytest:*`, `pip:*`, `poetry init/install/add`, `uv:*`, `uvx:*`, `python:*`, `python3:*`, `py:*`, `nuget:*`
- **Read-only shell** — `ls`, `cat`, `pwd`, plus `Get-ChildItem`, `Get-Location`, `Test-Path`

The intent: anything strictly local, reversible, or read-only is auto-approved so you stop click-confirming during normal flow. Anything that can rewrite history, force-push, or wipe files goes through `deny` or prompts for confirmation.

## `permissions.deny` — hard-blocked patterns

| Pattern | Why blocked |
|---|---|
| `rm -rf /`, `rm -rf ~`, `rm -rf ~/` | Catastrophic delete of root or home |
| `git push --force`, `git push -f` | Rewrites remote history; never auto-approved |
| `git reset --hard` | Discards uncommitted work |
| `git clean -fd` | Wipes untracked files |
| `npm`, `npx`, `yarn` | Frontend/Node package manager policy: use `pnpm` or `bun` |

`deny` is absolute — it overrides `allow`. If you legitimately need to force-push, you run the command yourself in a terminal.

## `mcpServers` — pre-configured tool integrations

Every entry is a long-lived stdio subprocess started at session boot.

| Server | Command | Env vars | What it gives Claude |
|---|---|---|---|
| `context7` | `pnpm dlx @context7/mcp-server@latest` | — | Live, version-current library docs (use for "is this API still valid in vN") |
| `figma` | `pnpm dlx @figma/mcp-server@latest` | `FIGMA_ACCESS_TOKEN` | Files, components, design tokens |
| `playwright` | `pnpm dlx @playwright/mcp@latest` | — | Browser automation — open, click, fill, screenshot |
| `azure-devops` | `pnpm dlx @tiberriver256/mcp-server-azure-devops@latest` | `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN` | Work items, repos, pipelines, PRs |
| `supabase` | `pnpm dlx @supabase/mcp-server-supabase@latest` | `SUPABASE_ACCESS_TOKEN` | Project, DB, auth, storage, edge functions |
| `obsidian` | `pnpm dlx obsidian-mcp@latest` | `OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT` | Read/search your Obsidian vault (requires Local REST API plugin) |
| `docker` | `uvx docker-mcp` | — | Manage containers, images, volumes |

### MCP environment variables

`${VAR}` placeholders are resolved from the **shell that launched Claude Code**, not from `.env` files. The flow:

1. `setup/settings-configurator-ui.py` (mode: "Initialize env vars") prompts for each var and persists it via `setx` on Windows / shell rc on Unix.
2. Restart your terminal so the new vars are inherited.
3. Launch Claude Code.

If a server fails to authenticate, `claude mcp list` is the first thing to check, then verify the env var is exported in the parent shell.

## `enabledPlugins`

Currently enabled:

- `azure@claude-plugins-official` — Azure SDK / Bicep / az CLI helpers
- `microsoft-docs@claude-plugins-official` — Microsoft Learn search and fetch

Plugins live in a separate cache (`~/.claude/plugins/`) and merge with your manual config at runtime — no overwrites. Disable by flipping the value to `false`.

## `hooks` — lifecycle bindings

| Event | Matcher | Script | Purpose |
|---|---|---|---|
| `SessionStart` | (none) | `session-start.ps1` | Detects project state, injects `additionalContext` to bootstrap Claude. |
| `PreToolUse` | `Bash` | `command_guard.py` | Inspects bash commands for prompt injection, hidden Unicode, obfuscated execution, destructive patterns. Exit 2 = block. |
| `PreToolUse` | `PowerShell` | `command_guard.py` | Same guard, applied to PowerShell calls. |
| `PreToolUse` | `Write` | `file_write_guard.py` | Hard-blocks writes to `command_guard.py` and `file_write_guard.py` themselves so prompt injection can't disable the guards. |
| `PreToolUse` | `Edit` | `file_write_guard.py` | Same — applied to edits. |
| `PostToolUse` | `Write` | `write_audit.py` | Appends `{ts, tool, path}` to `~/.claude/write_audit.jsonl`. |
| `PostToolUse` | `Edit` | `write_audit.py` | Same — for edits. |
| `Stop` | (none) | `stop-session.ps1` | Warns about uncommitted changes when the session ends. |

See [`hooks.md`](hooks.md) for what each script actually checks.

## What is NOT in `settings.json`

- Agents — discovered from `~/.claude/agents/*.md`
- Skills — discovered from `~/.claude/skills/*.md`
- Rules — discovered from `~/.claude/rules/*.md`
- Output styles — discovered from `~/.claude/output-styles/*.md`
- Project templates — discovered from `~/.claude/project-templates/*.md`

These are pure file-system conventions. Drop a file in the right folder → run `setup/settings-configurator-ui.py` → it's registered.

## Editing safely

1. Edit `global/settings.json` here in the repo.
2. Run `python setup/settings-configurator-ui.py` → the wizard takes a timestamped backup before overwriting `~/.claude/settings.json`.
3. Restart Claude Code.
4. If something breaks: rerun the wizard → "Restore" → pick the timestamped backup.

The "Doctor" mode in the wizard diffs `~/.claude/` against `global/` and reports drift (missing, changed, extra files) without modifying anything.
