# setup/

One-stop entry point for setting up this machine's Claude Code and Codex environment.

The wizard is published to PyPI as **`cabal`** and bundled into a standalone `.exe`. Three install paths cover every host:

| Path | Command | Notes |
|---|---|---|
| Install from PyPI (recommended) | `uv tool install cabal` then `cabal` | Single command. Needs only a Python ≥ 3.11. Works on any OS that `uv` / `pipx` support. Heads-up: there is also a Haskell tool called `cabal` distributed via Hackage — different registry, but the shell binary name collides. See the package README for mitigation. |
| Terminal (source) | `python setup/settings-configurator-ui.py` | Dev mode. Any shell, runs straight from a git checkout. First run auto-installs `textual` + `rich` via pip. |
| Terminal (Windows convenience) | `setup\settings-configurator-ui.cmd` | Same as above, finds `py` or `python` on PATH. |
| Standalone exe | `setup/build/dist/cabal[.exe]` | One-file binary that bundles Python, `textual`, `rich`, `global/`, and `setup/env/`. **No Python install required on the target machine.** Build with `python setup/build/build_exe.py`. See [`build/README.md`](build/README.md). |

> **Alternative**: if you only need the shareable Claude Code surface (skills, agents, hooks, MCP servers, output styles) and don't need the global `CLAUDE.md` / permissions / theme / `rules/` / `project-templates/`, you can install prompt-lib as a Claude Code marketplace plugin instead. No Python required. See [`docs/plugin-install.md`](../docs/plugin-install.md). The two install paths ship different surfaces — the PyPI tool deploys the global config; the plugin only registers slash commands and agents inside Claude Code.

## Primary

**`cabal`** — interactive TUI wizard. Deploys `global/` config to `~/.claude/`, deploys `global/codex/` assets to `~/.codex/`, initializes machine env vars, shows inline drift markers, restores backups, and scaffolds `.claude/` or `.agents/` in other projects.

### Modes

| Mode | Purpose |
|---|---|
| Update global settings | Deploy `global/` → `~/.claude/` with dry-run preview, multi-select component toggles, env-var status panel, and timestamped backups. |
| Initialize env vars | Prompt for each var in `env/setup.env.json`, write to `setx` (Windows) or shell rc (Unix). |
| Doctor | Compare `~/.claude/` against `global/` and report drift (missing, changed, extra files). |
| Restore | Roll back `~/.claude/settings.json` from a timestamped backup. |
| Local project setup | In the current cwd: scaffold `.claude/`, pick a `CLAUDE.md` template, apply git repo-init template, run `specify init` to bootstrap Spec Kit (`.specify/`). |
| Codex setup | Deploy Codex skills to `~/.codex/skills`, scaffold project `.agents/skills`, apply an `AGENTS.md` template, and inspect conversion diffs. |
| Tools | Install / update optional companion tools (Claude CLI, GitHub CLI, **Specify CLI** for GitHub Spec Kit, `claude-devtools`). Spec Kit's `specify` is installed via `uv tool install` from the upstream git repo and auto-installs `uv` if missing. |

## Structure

```
setup/
├── README.md                       ← this file
├── src/cabal/                      ← installable package (PyPI: `cabal`)
│   ├── __init__.py                 ← package metadata
│   ├── __main__.py                 ← `cabal` console entry point
│   ├── wizard.py                   ← the Textual TUI
│   └── README.md                   ← PyPI page README
├── settings-configurator-ui.py     ← dev shim — delegates to cabal.__main__
├── settings-configurator-ui.cmd    ← Windows launcher for the dev shim
├── build/                          ← PyInstaller spec + driver for the .exe
├── env/                            ← machine env var initialization
├── mcp-templates.json              ← MCP server templates (bundled into wheel + exe)
└── tools/                          ← supporting scripts (bash fallback, smoke test, dev installer)
```

See `build/README.md`, `env/README.md`, and `tools/README.md` for subfolder details.
