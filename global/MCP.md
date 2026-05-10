# MCP (Model Context Protocol) Setup

MCP servers extend Claude with tools — file access, API calls, database queries, browser control, and more. Each server exposes a set of tools Claude can call during a session.

## Scopes

| Scope | File | Committed | Available in |
|---|---|---|---|
| **Global** | `~/.claude/settings.json` → `mcpServers` | No | Every project on this machine |
| **Local** | `.claude/settings.local.json` → `mcpServers` | No | This project only, not shared |
| **Project** | `.mcp.json` in project root | Yes | This project, shared with the team |

**Rule of thumb:**
- Tools you use everywhere → Global
- Credentials or paths specific to you → Local
- Team-shared project tools (DB inspector, project API) → Project (`.mcp.json`)

---

## Currently configured (Global)

### context7
Provides up-to-date documentation for any library or framework, resolved per-prompt. Ask Claude to "use context7" when working with a library to get current docs instead of training-data guesses. When unsure whether a package, pattern, or API is current, use context7 to verify before recommending it.

**Setup:** None — works out of the box.
**Package:** `@context7/mcp-server`

---

### github
Full GitHub API access — read and write repos, issues, PRs, code search, releases, and more.

**Setup:**
1. Go to `github.com/settings/tokens` → Generate new token (classic)
2. Scopes needed: `repo`, `read:org`, `read:user`
3. Add to your shell profile:
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_yourtoken
   ```
**Package:** `@modelcontextprotocol/server-github`

---

### figma
Access Figma files, components, styles, and design tokens directly from Claude. Useful for translating designs into code.

**Setup:**
1. Go to `figma.com` → Account Settings → Personal access tokens → Generate token
2. Add to your shell profile:
   ```bash
   export FIGMA_ACCESS_TOKEN=figd_yourtoken
   ```
**Package:** `@figma/mcp-server`

---

### playwright
Browser automation — open pages, click, fill forms, take screenshots, and run assertions. Great for E2E testing workflows and scraping.

**Setup:** None — works out of the box. Playwright browsers are downloaded on first use.
**Package:** `@playwright/mcp`

---

### postgres
Query and inspect PostgreSQL databases. Claude can read schema, run queries, and help debug data issues.

**Setup:**
1. Add to your shell profile:
   ```bash
   export POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/dbname
   ```
> Use a read-only database user for safety — Claude will have full query access.

**Package:** `@modelcontextprotocol/server-postgres`

---

### supabase
Full Supabase project management — query databases, manage tables, handle auth users, storage buckets, edge functions, and project settings.

**Setup:**
1. Go to `supabase.com/dashboard/account/tokens` → Generate new token
2. Add to your shell profile:
   ```bash
   export SUPABASE_ACCESS_TOKEN=sbp_yourtoken
   ```
**Package:** `@supabase/mcp-server-supabase`

---

### obsidian
Read and search your Obsidian vault — notes, daily logs, docs, research. Claude can pull context from your knowledge base mid-session.

**Requires the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin in Obsidian.**

**Setup:**
1. Open Obsidian → Settings → Community Plugins → Browse → install **Local REST API**
2. Enable the plugin and copy the API key from its settings (default port: 27123)
3. Add to your shell profile:
   ```bash
   export OBSIDIAN_API_KEY=your_api_key
   ```
4. Keep Obsidian running when you want Claude to access your vault

**Package:** `obsidian-mcp`

---

### azure-devops
Read and write Azure DevOps work items, repos, pipelines, pull requests, and sprints.

**Setup:**
1. Go to `dev.azure.com` → User Settings → Personal Access Tokens → New Token
2. Scopes needed: `Work Items (Read & Write)`, `Code (Read)`, `Build (Read)`
3. Add to your shell profile:
   ```bash
   export AZURE_DEVOPS_ORG_URL=https://dev.azure.com/yourorg
   export AZURE_DEVOPS_TOKEN=your_pat_token
   ```
**Package:** `@tiberriver256/mcp-server-azure-devops`

---

## Suggested MCP servers

### Developer workflow

| Server | Package | What it does |
|---|---|---|
| **Git** | `@modelcontextprotocol/server-git` | Git operations on local repos — log, diff, blame, branch |
| **Playwright** | `@playwright/mcp` | Browser automation — great for E2E testing and scraping |
| **Puppeteer** | `@modelcontextprotocol/server-puppeteer` | Headless Chrome control |
| **Docker** | `mcp-server-docker` | Manage containers, images, and volumes |

### Databases

| Server | Package | What it does |
|---|---|---|
| **PostgreSQL** | `@modelcontextprotocol/server-postgres` | Query and inspect Postgres databases |
| **SQLite** | `@modelcontextprotocol/server-sqlite` | Read/write local SQLite databases |
| **MySQL** | `mcp-server-mysql` | Query MySQL databases |

### Search & knowledge

| Server | Package | What it does |
|---|---|---|
| **Brave Search** | `@modelcontextprotocol/server-brave-search` | Web search via Brave API (requires API key) |
| **Memory** | `@modelcontextprotocol/server-memory` | Persistent key-value memory across sessions |
| **Fetch** | `@modelcontextprotocol/server-fetch` | Fetch and parse any URL |

### Project management

| Server | Package | What it does |
|---|---|---|
| **Linear** | `@linear/mcp-server` | Read/write Linear issues, projects, and cycles |
| **Jira** | `@modelcontextprotocol/server-jira` | Read/write Jira issues and projects |
| **Notion** | `@modelcontextprotocol/server-notion` | Read/write Notion pages and databases |

### Communication

| Server | Package | What it does |
|---|---|---|
| **Slack** | `@modelcontextprotocol/server-slack` | Read channels, post messages, search Slack |

### Cloud

| Server | Package | What it does |
|---|---|---|
| **Azure DevOps** | `@tiberriver256/mcp-server-azure-devops` | Work items, repos, pipelines in Azure DevOps |
| **AWS** | `@aws/mcp-server` | Query AWS resources and services |

---

## Adding a new global MCP server

1. Edit `settings.json` — add an entry under `mcpServers`:

```json
"server-name": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@scope/package-name@latest"],
  "env": {
    "API_KEY": "${MY_ENV_VAR}"
  }
}
```

2. Run `apply-global-claude-settings.sh` to deploy
3. Restart Claude Code — new tools appear automatically

---

## Adding a project MCP server

Create `.mcp.json` in the project root (commit this to share with your team):

```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@scope/package-name@latest"],
      "env": {
        "API_KEY": "${MY_ENV_VAR}"
      }
    }
  }
}
```

Sensitive values go in `.claude/settings.local.json` (not committed):

```json
{
  "mcpServers": {
    "server-name": {
      "env": {
        "API_KEY": "actual-secret-value"
      }
    }
  }
}
```

---

## Troubleshooting

**Server not connecting:** Run `claude mcp list` to see status. Run `/mcp` inside a session for live status.

**Token not picked up:** Make sure the env var is exported in the shell Claude Code launches from. Restart Claude Code after adding env vars.

**Check server tools:** Type `/mcp` in a session and expand the server to see all available tools.
