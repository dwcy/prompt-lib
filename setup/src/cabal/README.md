# cabal

**Claude Code Setup Wizard.** A Textual TUI that deploys [prompt-lib](https://github.com/dwcy/prompt-lib)'s `global/` tree (skills, agents, hooks, output styles, project templates) into `~/.claude/`, manages MCP servers via `claude mcp`, scaffolds `.claude/` in other projects, and runs drift / restore against your local Claude Code config.

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

## What it does

| Mode | Purpose |
|---|---|
| Update | Deploy `global/` → `~/.claude/` with dry-run preview, multi-select component toggles, env-var status panel, timestamped backups. |
| Initialize env vars | Prompt for each var, write via `setx` (Windows) or shell rc (Unix). |
| MCP | Live status from `claude mcp list`. Toggle = `claude mcp add/remove`. |
| Doctor | Compare `~/.claude/` against the bundled `global/`, report drift. |
| Restore | Roll back `~/.claude/settings.json` from a timestamped backup. |
| Local | In another project: scaffold `.claude/`, apply a `CLAUDE.md` template, set up git repo template, optionally `specify init`. |
| Tools | Install / update companion CLIs (Claude CLI, GitHub CLI, Specify CLI, claude-devtools). |

## Naming

There is also a Haskell build tool called `cabal` distributed via Hackage. The two have no package-registry overlap (PyPI vs Hackage), but the shell binary is `cabal` in both. If you have both installed, whichever directory comes first on `PATH` wins. If you need them side-by-side, install this one into a dedicated venv and invoke it with the venv-qualified path.

## Source

- Repo: <https://github.com/dwcy/prompt-lib>
- License: MIT
