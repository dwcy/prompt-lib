# Quickstart — Install prompt-lib as a Claude Code Plugin

**Feature**: 004-github-plugin
**Audience**: Anyone who wants to use prompt-lib without cloning the repo. Two install paths are documented; pick one.

---

## Path A — Plugin install (no clone, recommended for new users)

### Prerequisites

- Claude Code installed (any recent version with `/plugin` support).
- `gh auth login` configured (only required if the prompt-lib repo is private, or for background auto-updates).
- The following on PATH for hooks and MCP servers to work fully:
  - Python 3 (for `command_guard.py`, `file_write_guard.py`, `write_audit.py`).
  - PowerShell (`powershell` on Windows, `pwsh` elsewhere) for `session-start.ps1` and `stop-session.ps1`.
  - `pnpm` (for `pnpm dlx` Node.js MCP servers) and `uvx` (uv) for MCP servers.
- The following environment variables set if you want the corresponding MCP server to start:

  | Server | Env var(s) |
  |---|---|
  | `github` | `GITHUB_PERSONAL_ACCESS_TOKEN` |
  | `figma` | `FIGMA_ACCESS_TOKEN` |
  | `azure-devops` | `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_TOKEN` |
  | `supabase` | `SUPABASE_ACCESS_TOKEN` |
  | `obsidian` | `OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT` |

  Servers without env vars set will fail to start individually but won't block the plugin or other servers.

### Install

Inside a Claude Code session, run:

```text
/plugin marketplace add <owner>/prompt-lib
/plugin install prompt-lib@prompt-lib
```

Replace `<owner>` with the GitHub owner of the repo.

That's it. The plugin is installed at user scope by default; available in every project on this machine.

### Verify

```text
/plugin list
```

You should see:

```
prompt-lib@prompt-lib   enabled   <commit-sha>
```

```text
/help
```

You should see `/prompt-lib:git`, `/prompt-lib:commit`, `/prompt-lib:review`, etc.

```text
/agents
```

You should see `prompt-lib:python-architect`, `prompt-lib:react-architect`, `prompt-lib:code-plan-verifier`, etc.

### Update later

```text
/plugin update prompt-lib@prompt-lib
```

### Uninstall

```text
/plugin uninstall prompt-lib@prompt-lib
```

`~/.claude/` is not modified — only the plugin cache is cleaned up.

---

## Path B — Apply-script install (existing power-user workflow)

This path is unchanged from before the plugin feature. It deploys the full prompt-lib to `~/.claude/` including global `CLAUDE.md`, permissions, theme, statusline, rules, project templates — items the plugin model cannot ship.

### Prerequisites

- Git clone of the repo.
- Python 3 on PATH.

### Install / update

```bash
git pull
python setup/settings-configurator-ui.py
```

(Or `bash setup/tools/apply-global-claude-settings.sh` for the non-interactive fallback.)

Restart Claude Code.

### Verify

Skills appear without namespace prefix (`/git`, `/commit`, `/review`).

---

## Scope split — what each path ships

| Item | Plugin (Path A) | Apply (Path B) |
|---|:-:|:-:|
| Skills (`global/skills/`) | ✅ namespaced `/prompt-lib:*` | ✅ flat `/*` |
| Agents (`global/agents/`) | ✅ namespaced `prompt-lib:*` | ✅ flat `*` |
| Output styles (`global/output-styles/`) | ✅ | ✅ |
| Hooks (`global/hooks/`) | ✅ via plugin manifest | ✅ via `~/.claude/settings.json` |
| MCP servers | ✅ via `.mcp.json` | ✅ via `~/.claude/settings.json` |
| Global `CLAUDE.md` (behavioural rules) | ❌ — plugin model doesn't auto-load | ✅ |
| `global/rules/*.md` (path-conditional rules) | ❌ | ✅ |
| `global/project-templates/*.md` | ❌ | ✅ |
| Global `settings.json` permissions / model / theme / statusLine / defaultMode | ❌ — plugin can only set `agent` and `subagentStatusLine` | ✅ |
| `global/keybindings.json` | ❌ | ✅ |

If you want **everything** (the full power-user setup), use Path B. If you want the **skills, agents, hooks, MCP servers** without modifying your global Claude config, use Path A.

You can run **both**: plugin skills appear under `/prompt-lib:*`, apply skills appear flat. Hooks may double-fire — pick one path or be aware.

---

## Smoke test (for maintainers — verifies install paths still work)

On a clean machine or VM:

### Path A smoke test

1. `claude` (start a session).
2. `/plugin marketplace add <owner>/prompt-lib` — succeeds.
3. `/plugin install prompt-lib@prompt-lib` — succeeds.
4. `/plugin list` — shows `prompt-lib` enabled.
5. `/help` — shows ≥ 10 `/prompt-lib:*` entries.
6. `/agents` — shows ≥ 5 `prompt-lib:*` entries.
7. Invoke a representative skill, e.g. `/prompt-lib:git`. Skill runs.
8. Invoke a representative agent, e.g. `@prompt-lib:python-architect` with a small task. Agent runs.
9. Edit any file in a project — `PreToolUse` hook on `Edit` fires (visible via Claude Code debug log or by the hook's own side effects).
10. Inspect MCP server initialization in `--debug` output — `context7`, `playwright`, `docker` start; others start only if env vars are set.

### Path B smoke test

1. From a clone: `python setup/settings-configurator-ui.py` — wizard completes without error.
2. Restart Claude Code.
3. `/help` — shows flat skills (`/git`, `/commit`, etc.).
4. `/agents` — shows flat agents (`@python-architect`, etc.).
5. Hooks fire (same behaviour as before the feature).
6. MCP servers start (same as before).
7. Diff `~/.claude/settings.json` against a saved pre-feature snapshot — `mcpServers`, `hooks`, `permissions`, `statusLine`, `model`, `theme`, `defaultMode` keys MUST match.

### Local dev smoke test (for plugin contributors)

From the repo root:

```bash
claude --plugin-dir ./global
```

Inside the session: same Path A verification (steps 4–8).

`/reload-plugins` to pick up edits without restart.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/plugin marketplace add` reports "marketplace not found" | Repo is private and `gh auth login` not configured | Run `gh auth login`. Or set `GITHUB_TOKEN` for background updates. |
| Skills don't appear after install | `/reload-plugins` not run after a fresh install | Run `/reload-plugins`. If still missing, check `claude --debug` output for plugin load errors. |
| MCP server X fails to start | Required env var unset, or `pnpm` / `uvx` not on PATH | Set the env var or install pnpm / uv. Other servers continue working. |
| Hook script doesn't fire | `python` or `powershell` not on PATH | Install the prerequisite. |
| Both Path A and Path B installed; hooks double-fire | Both copies of the hooks active | Uninstall one path: either `/plugin uninstall prompt-lib@prompt-lib` or `rm -rf ~/.claude/hooks/` (Path B) followed by removing the hooks block from `~/.claude/settings.json`. |
