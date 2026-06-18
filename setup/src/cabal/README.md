# cabal

**Local agent control panel.** Cabal is the control room for a machine's Claude Code and Codex setup: it deploys [prompt-lib](https://github.com/dwcy/prompt-lib)'s `global/` tree into `~/.claude/`, manages MCP servers via `claude mcp`, scaffolds `.claude/` in other projects, and manages curated Codex assets from `global/codex/`.

## Install

```bash
uv tool install cabal
# or
pipx install cabal
```

Then run:

```bash
cabal
```

From a source checkout, use the bootstrap launchers when Python may not already
be installed:

```bash
# Windows
setup\settings-configurator-ui.cmd

# Linux
sh setup/settings-configurator-ui.sh
```

## What it does

| Mode | Purpose |
|---|---|
| Update | Deploy `global/` → `~/.claude/` with dry-run preview, multi-select component toggles, env-var status panel, timestamped backups. |
| Initialize env vars | Prompt for each var, write via `setx` (Windows) or shell rc (Unix). |
| MCP | Live status from `claude mcp list`. Toggle = `claude mcp add/remove`. |
| Restore | Roll back `~/.claude/settings.json` from a timestamped backup. |
| Local | In another project: scaffold `.claude/`, apply a `CLAUDE.md` template, set up git repo template, optionally `specify init`. |
| Codex | Deploy `global/codex/` to `~/.codex`, scaffold `.agents/`, and inspect Claude -> Codex conversion diffs. |
| Tools | Install / update companion CLIs (Claude CLI, GitHub CLI, Specify CLI, claude-devtools). |

## Identity

Cabal is meant to feel like a local control room: one focused place for agents,
hooks, skills, MCP servers, project scaffolding, and setup drift. The TUI opens
directly into useful controls; the name provides the frame, not a splash screen.

## Source

- Repo: <https://github.com/dwcy/prompt-lib>
- License: MIT
