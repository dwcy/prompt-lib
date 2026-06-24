---
name: add-mcp
description: Add an MCP server to Claude Code the right way. Use when the user wants to register, connect, or install an MCP server (e.g. "add context7", "set up the github MCP", "connect supabase MCP"). Captures hard-won learnings about Claude Code's MCP storage, Windows .CMD wrapping, scope precedence, and env-var handling. NEVER edit settings.json `mcpServers` — that field is dead.
allowed-tools: Bash, Read
---

# How Claude Code actually stores MCP servers

Claude Code does NOT read MCP servers from `~/.claude/settings.json` `mcpServers`. That block is silently ignored. The only ways MCP servers reach Claude Code:

| Scope | Storage | Use when |
|---|---|---|
| **local** (default) | `~/.claude.json` under the project path | One-off, this project only, current user |
| **project** | `<repo>/.mcp.json` | Committed to repo, shared with team (gated by trust dialog) |
| **user** | `~/.claude.json` user section | Available across ALL projects on this machine |
| **plugin** | The plugin's `plugin.json` / `.mcp.json` | Comes from a marketplace plugin |

Precedence (highest → lowest): **local > project > user > plugin**. Same name in two scopes — only the highest scope's definition runs.

# Canonical commands

```bash
# Inspect what Claude Code knows
claude mcp list

# Add a stdio server (subprocess) — note the `--` before the command
claude mcp add -s user <name> -- <command> [args...]

# Add an HTTP MCP server
claude mcp add -s user --transport http <name> <url> [--header "X: Y"]

# Add with env vars
claude mcp add -s user <name> -e KEY1=value1 -e KEY2=value2 -- <command> [args...]

# Remove
claude mcp remove -s <scope> <name>
```

`--` separates the `claude mcp add` flags from the subprocess command + args. Always include it for stdio servers or your `--flags` will be eaten by `claude mcp add`.

# Windows: pnpm/npx/bunx need `cmd /s /c` wrapping

`pnpm`, `npx`, `bunx` on Windows are `.CMD` shim files. Windows `CreateProcess` cannot execute `.CMD` directly — only real `.exe` binaries. MCP servers are spawned with `CreateProcess`. So a bare `command: "pnpm"` registration fails silently on Windows.

The fix: wrap with `cmd /s /c "<full command as one string>"`.
- `/s` strips outer quotes so cmd doesn't re-parse the inner command's slashes
- This matters because package names like `@upstash/context7-mcp` contain `/c`, which cmd would otherwise treat as a new `/c` switch

Correct registration on Windows:
```bash
claude mcp add -s user context7 -- cmd /s /c "pnpm dlx @upstash/context7-mcp@latest"
```

Without `/s`, the `/c` inside `@upstash/context7-mcp` makes cmd re-parse and you get errors like `'ontext7-mcp@latest' is not recognized` (cmd ate the `@upstash/c` prefix).

# Git Bash gotcha: MSYS_NO_PATHCONV=1

If you run `claude mcp add` from Git Bash on Windows, MSYS path conversion will rewrite `/s` → `S:/` and `/c` → `C:/` before they reach `claude.exe`. The registration succeeds but stores `cmd S:/ C:/ pnpm dlx ...` which fails to connect.

Always prefix the command:
```bash
MSYS_NO_PATHCONV=1 claude mcp add -s user context7 -- cmd /s /c "pnpm dlx @upstash/context7-mcp@latest"
```

From PowerShell or cmd directly, no prefix needed.

# On Linux/macOS

`pnpm`/`npx`/`bunx` are real executables (or shebang scripts). No wrapping:
```bash
claude mcp add -s user context7 -- pnpm dlx @upstash/context7-mcp@latest
```

# Workflow when the user asks to add an MCP

1. Run `claude mcp list` first — confirm it's not already added.
2. Identify the package and any required env vars (check the MCP's README; common ones below).
3. Pick a scope. Default to `-s user` for personal tools the user wants everywhere. Use `-s project` only if the MCP is project-specific AND should be committed.
4. Build the command:
   - Windows: `MSYS_NO_PATHCONV=1 claude mcp add -s user <name> [-e KEY=value]... -- cmd /s /c "pnpm dlx <package>"`
   - Linux/macOS: `claude mcp add -s user <name> [-e KEY=value]... -- pnpm dlx <package>`
5. If env vars are needed but unset in the shell, STOP. Tell the user which env vars they need to set (e.g. `setx FIGMA_ACCESS_TOKEN <value>` on Windows or `export ...` on Unix), then re-run.
6. Run `claude mcp list` to confirm the new server shows `✓ Connected`.
7. Tell the user to restart Claude Code so MCP tools appear in the deferred tools list.

# Common MCP packages

| Server | Package | Env vars |
|---|---|---|
| context7 | `@upstash/context7-mcp@latest` | none |
| playwright | `@playwright/mcp@latest` | none |
| supabase | `@supabase/mcp-server-supabase@latest` | `SUPABASE_ACCESS_TOKEN` |
| figma | `@figma/mcp-server@latest` | `FIGMA_ACCESS_TOKEN` |
| azure-devops | `@tiberriver256/mcp-server-azure-devops@latest` | `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN` |
| obsidian | `obsidian-mcp@latest` | `OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT` |

# What NOT to do

- **Do not edit `~/.claude/settings.json` `mcpServers`** — silently ignored by Claude Code. Confused humans for hours.
- **Do not omit `cmd /s /c` on Windows for pnpm/npx/bunx** — spawn fails with no log entry, looks like the server doesn't exist.
- **Do not omit `/s` from `cmd /s /c`** — works for package names without `/c`/`/s`/`/k` inside, breaks for any package whose name contains those.
- **Do not omit `MSYS_NO_PATHCONV=1` when calling from Git Bash** — args get path-mangled silently; `mcp list` will show the mangled command.
- **Do not register servers needing env vars without verifying the vars are set** — server registers but fails to connect, looks broken.

# Trust dialog

Project-scope `.mcp.json` servers are gated by a per-project trust dialog (tracked in `~/.claude.json` under each project's `hasTrustDialogAccepted`). If a project-scope server isn't running, check that flag. User-scope servers bypass this entirely.

# Where to verify after adding

- `claude mcp list` — should show the server with `✓ Connected`
- `~/.claude.json` — `mcpServers` block (top-level for user scope, per-project for local scope)
- `~/AppData/Local/claude-cli-nodejs/Cache/<project-slug>/mcp-logs-<name>/` (Windows) or equivalent — JSONL spawn/error logs once Claude Code attempts the server
- After Claude Code restart, the MCP's tools should appear in the deferred tools list at session start
