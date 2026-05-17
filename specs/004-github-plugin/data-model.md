# Phase 1 — Data Model: Plugin Manifest Entities

**Feature**: 004-github-plugin
**Date**: 2026-05-16

The "data" in this feature is declarative configuration, not runtime data. This document enumerates each entity (file), its fields, and the validation rules each must satisfy.

---

## Entity 1 — Marketplace Catalog

**File**: `.claude-plugin/marketplace.json` (repo root)

**Purpose**: Declares the marketplace identity, owner, and the list of plugins it offers. Read by Claude Code when a user runs `/plugin marketplace add <owner>/prompt-lib`.

### Fields

| Field | Type | Required | Value for prompt-lib |
|---|---|---|---|
| `name` | string (kebab-case) | yes | `"prompt-lib"` |
| `owner.name` | string | yes | `"Dawid"` (or `pawzor`) |
| `owner.email` | string | no | `"pawzor@gmail.com"` (optional) |
| `description` | string | no | `"Personal Claude Code library — skills, agents, hooks, and MCP servers."` |
| `plugins` | array | yes | one entry (see Entity 2 reference) |
| `$schema` | string | no | `"https://json.schemastore.org/claude-code-plugin-marketplace.json"` (for editor autocomplete) |

### Validation rules

- `name` MUST be kebab-case (lowercase letters, digits, hyphens only). `prompt-lib` is valid.
- `name` MUST NOT be a reserved marketplace name. `prompt-lib` is not on the reserved list.
- `owner.name` MUST be non-empty.
- `plugins` MUST contain at least one entry.
- Every entry in `plugins` MUST have `name` and `source`.

### State transitions

None — pure declaration. Reads by Claude Code are idempotent.

---

## Entity 2 — Plugin Entry (inside marketplace)

**Location**: `marketplace.json` → `plugins[0]`

**Purpose**: Tells Claude Code where to fetch the plugin code from, relative to the marketplace clone.

### Fields

| Field | Type | Required | Value for prompt-lib |
|---|---|---|---|
| `name` | string (kebab-case) | yes | `"prompt-lib"` |
| `source` | string \| object | yes | `"./global"` (relative path; resolved against marketplace root) |
| `description` | string | no | `"Skills, agents, hooks, and MCP servers for Claude Code."` |
| `version` | string | no | (omitted — commit SHA used; see research R4) |
| `author.name` | string | no | `"Dawid"` |
| `homepage` | string | no | `"https://github.com/<owner>/prompt-lib"` |
| `repository` | string | no | `"https://github.com/<owner>/prompt-lib"` |
| `license` | string | no | (omitted in v1 unless a LICENSE file is added) |
| `keywords` | array | no | `["skills", "agents", "hooks", "mcp", "claude-code"]` |
| `category` | string | no | `"productivity"` |

### Validation rules

- `name` MUST equal the `name` in the plugin manifest (Entity 3) when both are present.
- `source` as a relative path MUST start with `./`.
- `source` MUST NOT contain `..` (path traversal).

### Source resolution

`./global` resolves to `<marketplace-clone>/global`. Claude Code copies that subtree into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.

---

## Entity 3 — Plugin Manifest

**File**: `global/.claude-plugin/plugin.json`

**Purpose**: Plugin's identity. Read at plugin load time to determine name, components, and metadata.

### Fields

| Field | Type | Required | Value for prompt-lib |
|---|---|---|---|
| `name` | string (kebab-case) | yes | `"prompt-lib"` |
| `description` | string | no | `"Personal Claude Code library — skills, agents, hooks, and MCP servers."` |
| `author.name` | string | no | `"Dawid"` |
| `author.email` | string | no | `"pawzor@gmail.com"` |
| `version` | string | no | (omitted — git commit SHA used) |
| `homepage` | string | no | `"https://github.com/<owner>/prompt-lib"` |
| `repository` | string | no | `"https://github.com/<owner>/prompt-lib"` |
| `keywords` | array | no | `["skills", "agents", "hooks", "mcp", "claude-code"]` |
| `$schema` | string | no | `"https://json.schemastore.org/claude-code-plugin-manifest.json"` |

### Component fields (all omitted — defaults used)

`skills`, `commands`, `agents`, `hooks`, `mcpServers`, `outputStyles`, `lspServers` are all OMITTED. Claude Code auto-discovers:

| Component | Default location (inside `global/`) | Contains |
|---|---|---|
| Skills | `skills/` | `git.md`, `commit.md`, `pr.md`, `review.md`, `css.md`, `design.md`, `docs.md`, `executing-plans.md`, `finishing-a-development-branch.md`, `lovable-cleanup.md`, `react-init.md`, `react-perf.md`, `react-review.md`, `react-safe.md`, `react-test.md`, `skill-create.md`, `ui-component.md`, `using-git-worktrees.md`, `infographics-design/SKILL.md` |
| Agents | `agents/` | `code-plan-verifier.md`, `dotnet-architect.md`, `dotnet-tester.md`, `frontend-architect.md`, `frontend-css.md`, `gitignore-auditor.md`, `init-project.md`, `load-project.md`, `python-architect.md`, `python-tester.md`, `react-architect.md`, `secret-auditor.md`, `tanstack-architect.md`, `unity-architect.md` |
| Output styles | `output-styles/` | `architect.md`, `concise.md`, `review.md`, `technical.md` |
| Hooks | `hooks/hooks.json` | (Entity 4) |
| MCP servers | `.mcp.json` | (Entity 5) |

### Validation rules

- `name` MUST be kebab-case.
- `name` MUST match the marketplace plugin entry name.

### Relationship

`plugin.json.name` ↔ `marketplace.json.plugins[*].name` (must be equal).

---

## Entity 4 — Hooks Config

**File**: `global/hooks/hooks.json`

**Purpose**: Registers event-driven scripts. Same schema as the inline `hooks` block in user `settings.json`.

### Structure

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "<optional ToolName regex>",
        "hooks": [
          { "type": "command", "command": "<shell command>" }
        ]
      }
    ]
  }
}
```

### Records for prompt-lib

Eight entries (see research R5 for the full mapping table):

| Event | Matcher | Script |
|---|---|---|
| `SessionStart` | — | `${CLAUDE_PLUGIN_ROOT}/hooks/session-start.ps1` |
| `PreToolUse` | `Bash` | `${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py` |
| `PreToolUse` | `PowerShell` | `${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py` |
| `PreToolUse` | `Write` | `${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py` |
| `PreToolUse` | `Edit` | `${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py` |
| `PostToolUse` | `Write` | `${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py` |
| `PostToolUse` | `Edit` | `${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py` |
| `Stop` | — | `${CLAUDE_PLUGIN_ROOT}/hooks/stop-session.ps1` |

### Validation rules

- Event names MUST be from the Claude Code hook event list (case-sensitive: `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`).
- `command` MUST be valid JSON-encoded shell.
- For `.ps1` scripts, the `command` MUST invoke `powershell` (or `pwsh`) with `-ExecutionPolicy Bypass -File`.
- Hook scripts at `${CLAUDE_PLUGIN_ROOT}/hooks/` MUST exist (validation done by `claude plugin validate`).

---

## Entity 5 — MCP Server Config

**File**: `global/.mcp.json`

**Purpose**: Registers MCP servers that start when the plugin is enabled.

### Structure

```json
{
  "mcpServers": {
    "<server-name>": {
      "type": "stdio",
      "command": "<binary>",
      "args": ["..."],
      "env": { "VAR": "${VAR}" }
    }
  }
}
```

### Records for prompt-lib

Eight servers, copied verbatim from current `global/settings.json` `mcpServers` block:

| Name | Command | Requires env |
|---|---|---|
| `context7` | `pnpm dlx @context7/mcp-server@latest` | — |
| `github` | `pnpm dlx @modelcontextprotocol/server-github@latest` | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| `figma` | `pnpm dlx @figma/mcp-server@latest` | `FIGMA_ACCESS_TOKEN` |
| `playwright` | `pnpm dlx @playwright/mcp@latest` | — |
| `azure-devops` | `pnpm dlx @tiberriver256/mcp-server-azure-devops@latest` | `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN` |
| `supabase` | `pnpm dlx @supabase/mcp-server-supabase@latest` | `SUPABASE_ACCESS_TOKEN` |
| `obsidian` | `pnpm dlx obsidian-mcp@latest` | `OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT` |
| `docker` | `uvx docker-mcp` | — |

### Validation rules

- `type` MUST be `"stdio"` (or `"sse"` / `"streamable-http"` for HTTP transports — not used here).
- `command` MUST be a binary discoverable on PATH at plugin runtime (`pnpm`, `uvx`).
- `env` variable interpolation (`${VAR}`) is performed by Claude Code at server-start time — unset vars cause the affected server to fail, others still start.

### Notes

- These same servers stay duplicated in `global/settings.json` for the apply path. **Manual sync rule**: when adding/removing an MCP server, update BOTH `global/settings.json` and `global/.mcp.json` in the same commit. The contract test in `./contracts/mcp-sync.contract.md` enforces parity.

---

## Entity Relationships

```
marketplace.json (root)
  └── plugins[0]
        └── source: "./global"  ─── points to ───┐
                                                  ▼
                                           global/
                                           ├── .claude-plugin/
                                           │     └── plugin.json   (Entity 3)
                                           ├── skills/             (auto-discovered)
                                           ├── agents/             (auto-discovered)
                                           ├── output-styles/      (auto-discovered)
                                           ├── hooks/
                                           │     ├── hooks.json    (Entity 4)
                                           │     ├── *.py
                                           │     └── *.ps1
                                           └── .mcp.json           (Entity 5)
```

Apply path (parallel, additive):

```
global/                  ──── apply wizard copies to ────►   ~/.claude/
  (everything EXCEPT
   .claude-plugin/**,
   .mcp.json,
   hooks/hooks.json)
```

Both paths read from `global/`; the wizard excludes the plugin-only files via the new ignore list documented in research R7.
