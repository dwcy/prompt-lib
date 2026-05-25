# Contract — `global/.claude-plugin/plugin.json` + companion files

**Spec surface**: Claude Code plugin manifest (v1, as documented at https://code.claude.com/docs/en/plugins-reference).
**Conformance scope**: The plugin manifest, plus the auto-discovered component layout under `global/`, MUST satisfy the Claude Code plugin loader.

---

## Required shape — `global/.claude-plugin/plugin.json`

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
  "name": "prompt-lib",
  "description": "Personal Claude Code library — skills, agents, hooks, and MCP servers.",
  "author": {
    "name": "Dawid",
    "email": "pawzor@gmail.com"
  },
  "homepage": "https://github.com/<owner>/prompt-lib",
  "repository": "https://github.com/<owner>/prompt-lib",
  "keywords": ["skills", "agents", "hooks", "mcp", "claude-code"]
}
```

### Field constraints

| Field | Constraint |
|---|---|
| `name` | MUST equal `"prompt-lib"`. MUST be kebab-case. |
| `version` | MUST be omitted (commit SHA versioning). |
| `description` | SHOULD be present (non-blocking warning otherwise). |
| `skills`, `commands`, `agents`, `hooks`, `mcpServers`, `outputStyles`, `lspServers` | MUST all be OMITTED — defaults used so Claude Code auto-discovers from default locations. |

---

## Required component layout — under `global/`

The following structure MUST exist at the plugin root (i.e. inside `global/`) for auto-discovery to find everything:

```
global/
├── .claude-plugin/
│   └── plugin.json           ← Entity 3, this contract
├── skills/
│   ├── <name>.md             ← flat-file skills (legacy commands/ shape, but Claude Code accepts in skills/ too)
│   └── <name>/SKILL.md       ← directory-style skill (e.g. infographics-design/SKILL.md)
├── agents/
│   └── <name>.md             ← each subagent is a single markdown file
├── output-styles/
│   └── <name>.md             ← each output style is a single markdown file
├── hooks/
│   ├── hooks.json            ← see hooks contract below
│   ├── command_guard.py
│   ├── file_write_guard.py
│   ├── write_audit.py
│   ├── session-start.ps1
│   └── stop-session.ps1
└── .mcp.json                 ← see MCP contract below
```

### Required files for the v1 plugin

(Validation MUST verify all of these exist.)

**Skills** (19 entries — exact list MAY change as new skills are added; the *count* and any specific listed file are testable assertions):

`commit.md`, `css.md`, `design.md`, `docs.md`, `executing-plans.md`, `finishing-a-development-branch.md`, `git.md`, `lovable-cleanup.md`, `pr.md`, `react-init.md`, `react-perf.md`, `react-review.md`, `react-safe.md`, `react-test.md`, `review.md`, `skill-create.md`, `ui-component.md`, `using-git-worktrees.md`, `infographics-design/SKILL.md`

**Agents** (15 entries):

`code-plan-verifier.md`, `dotnet-architect.md`, `dotnet-tester.md`, `frontend-architect.md`, `frontend-css.md`, `gitignore-auditor.md`, `init-project.md`, `load-project.md`, `pi-arduino-architect.md`, `python-architect.md`, `python-tester.md`, `react-architect.md`, `secret-auditor.md`, `tanstack-architect.md`, `unity-architect.md`

**Output styles** (4 entries):

`architect.md`, `concise.md`, `review.md`, `technical.md`

---

## Hooks contract — `global/hooks/hooks.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.ps1\"" }
        ]
      }
    ],
    "PreToolUse": [
      { "matcher": "Bash",       "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py\"" } ] },
      { "matcher": "PowerShell", "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/command_guard.py\"" } ] },
      { "matcher": "Write",      "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py\"" } ] },
      { "matcher": "Edit",       "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/file_write_guard.py\"" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Write", "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py\"" } ] },
      { "matcher": "Edit",  "hooks": [ { "type": "command", "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/write_audit.py\"" } ] }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "powershell -ExecutionPolicy Bypass -File \"${CLAUDE_PLUGIN_ROOT}/hooks/stop-session.ps1\"" }
        ]
      }
    ]
  }
}
```

### Hooks constraints

- Event names MUST be exactly: `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`. Case-sensitive.
- Every `command` MUST start with the binary, followed by quoted path using `${CLAUDE_PLUGIN_ROOT}`.
- The `${CLAUDE_PLUGIN_ROOT}` token MUST be wrapped in double quotes inside the command string.
- The set of (event, matcher, script) tuples MUST equal the set extracted from `global/settings.json` `hooks` block at the time of authoring. Any divergence is a violation of FR-206.

---

## MCP contract — `global/.mcp.json`

```json
{
  "mcpServers": {
    "context7":     { "type": "stdio", "command": "pnpm", "args": ["dlx", "@context7/mcp-server@latest"] },
    "github":       { "type": "stdio", "command": "pnpm", "args": ["dlx", "@modelcontextprotocol/server-github@latest"], "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}" } },
    "figma":        { "type": "stdio", "command": "pnpm", "args": ["dlx", "@figma/mcp-server@latest"], "env": { "FIGMA_ACCESS_TOKEN": "${FIGMA_ACCESS_TOKEN}" } },
    "playwright":   { "type": "stdio", "command": "pnpm", "args": ["dlx", "@playwright/mcp@latest"] },
    "azure-devops": { "type": "stdio", "command": "pnpm", "args": ["dlx", "@tiberriver256/mcp-server-azure-devops@latest"], "env": { "AZURE_DEVOPS_ORG_URL": "${AZURE_DEVOPS_ORG_URL}", "AZURE_DEVOPS_TOKEN": "${AZURE_DEVOPS_TOKEN}" } },
    "supabase":     { "type": "stdio", "command": "pnpm", "args": ["dlx", "@supabase/mcp-server-supabase@latest"], "env": { "SUPABASE_ACCESS_TOKEN": "${SUPABASE_ACCESS_TOKEN}" } },
    "obsidian":     { "type": "stdio", "command": "pnpm", "args": ["dlx", "obsidian-mcp@latest"], "env": { "OBSIDIAN_API_KEY": "${OBSIDIAN_API_KEY}", "OBSIDIAN_HOST": "${OBSIDIAN_HOST}", "OBSIDIAN_PORT": "${OBSIDIAN_PORT}" } },
    "docker":       { "type": "stdio", "command": "uvx", "args": ["docker-mcp"] }
  }
}
```

### MCP constraints

- The set of server keys MUST equal the set of keys under `mcpServers` in `global/settings.json` (parity rule — see mcp-sync contract below).
- `command` MUST be a binary discoverable on PATH at plugin runtime (`pnpm` or `uvx`).

---

## Cross-file parity contract — `mcp-sync.contract`

**Invariant**: For every key K, `global/.mcp.json.mcpServers[K]` MUST be byte-equal (after JSON normalization) to `global/settings.json.mcpServers[K]`.

**Why**: The plugin path reads `.mcp.json`; the apply path produces `~/.claude/settings.json` from `global/settings.json`. Both paths MUST present the same MCP server inventory to the user.

**Test** (one-liner, exit 0 on parity):

```bash
diff <(jq -S '.mcpServers' global/.mcp.json) <(jq -S '.mcpServers' global/settings.json)
```

---

## Hooks parity contract — `hooks-sync.contract`

**Invariant**: For every event E in `{SessionStart, PreToolUse, PostToolUse, Stop}`, the set of (matcher, script-basename) tuples in `global/hooks/hooks.json[E]` MUST equal the set in `global/settings.json.hooks[E]`, ignoring the path prefix difference (`${CLAUDE_PLUGIN_ROOT}/hooks/` vs `$USERPROFILE/.claude/hooks/` etc.).

**Why**: Same reason as MCP parity.

**Test**: A small Python script that loads both JSON files, normalizes paths to script basenames, and compares the sets.

---

## Validation procedure (full)

1. `claude plugin validate .` from repo root — exit 0, no errors.
2. `[ "$(jq -r .name global/.claude-plugin/plugin.json)" = "prompt-lib" ]` — exit 0.
3. `[ "$(jq -r .plugins[0].name .claude-plugin/marketplace.json)" = "prompt-lib" ]` — exit 0.
4. For every expected skill / agent / output-style file: `test -f global/skills/<name>.md` etc.
5. MCP parity diff exit 0.
6. Hooks parity test exit 0.
7. `claude --plugin-dir ./global` smoke test: starts, no errors in `--debug` output.
8. Inside the smoke-test session: `/plugin list` includes `prompt-lib`; `/help` shows at least one `/prompt-lib:*` skill; `/agents` shows at least one `prompt-lib:*` agent.
