# setup/

One-stop entry point for setting up this machine's Claude Code environment.

> **Alternative**: if you only need the shareable surface (skills, agents, hooks, MCP servers, output styles) and don't need the global `CLAUDE.md` / permissions / theme / `rules/` / `project-templates/`, you can install prompt-lib as a Claude Code plugin instead of running this wizard. No clone, no Python required. See [`docs/plugin-install.md`](../docs/plugin-install.md).

## Primary

**`settings-configurator-ui.py`** — interactive TUI wizard. Deploys `global/` config to `~/.claude/`, initializes machine env vars, runs drift checks, restores backups, and scaffolds `.claude/` in other projects.

Two run modes:

| Mode | Command | Notes |
|---|---|---|
| Terminal (source) | `python setup/settings-configurator-ui.py` | Any shell. First run auto-installs `textual` via pip. |
| Terminal (Windows convenience) | `setup\settings-configurator-ui.cmd` | Same as above, finds `py` or `python` on PATH. |
| Standalone exe | `setup/build/dist/HextravagantSetup[.exe]` | One-file binary that bundles Python, `textual`, `rich`, `global/`, and `setup/env/`. **No Python install required on the target machine.** Build with `python setup/build/build_exe.py`. See [`build/README.md`](build/README.md). |

### Modes

| Mode | Purpose |
|---|---|
| Update global settings | Deploy `global/` → `~/.claude/` with dry-run preview, multi-select component toggles, env-var status panel, and timestamped backups. |
| Initialize env vars | Prompt for each var in `env/setup.env.json`, write to `setx` (Windows) or shell rc (Unix). |
| Doctor | Compare `~/.claude/` against `global/` and report drift (missing, changed, extra files). |
| Restore | Roll back `~/.claude/settings.json` from a timestamped backup. |
| Local project setup | In the current cwd: scaffold `.claude/`, pick a `CLAUDE.md` template, apply git repo-init template. |
| Tools | Install / update optional companion tools (currently `claude-devtools` — desktop GUI for visualizing Claude Code session logs). Pulls the latest release from GitHub and runs the platform-native installer. |

## Structure

```
setup/
├── README.md                       ← this file
├── settings-configurator-ui.py     ← primary wizard (terminal mode)
├── settings-configurator-ui.cmd    ← Windows launcher for terminal mode
├── build/                          ← PyInstaller spec + driver for the .exe
├── env/                            ← machine env var initialization
└── tools/                          ← supporting scripts (bash fallback, smoke test)
```

See `build/README.md`, `env/README.md`, and `tools/README.md` for subfolder details.
