![Cabal header: pink elephant logo beside the Cabal wordmark](../docs/assets/cabal-header.png)

# setup/

Local agent control panel for this machine's Claude Code and Codex environment.

The control panel is published to PyPI as **`cabal`** and bundled into a standalone `.exe`. Source checkout launchers and install paths cover every host:

| Path | Command | Notes |
|---|---|---|
| Repo root (source checkout) | `./run` on POSIX, `.\run.cmd` on Windows | Convenience entry point that delegates to the platform-specific source launcher below. |
| Install from PyPI (recommended) | `uv tool install cabal` then `cabal` | Single command. Needs only a Python >= 3.14. Works on any OS that `uv` / `pipx` support. |
| Terminal (source) | `python setup/settings-configurator-ui.py` | Dev mode when Python is already installed. First run asks before installing `textual` + `rich` via pip. |
| Terminal (Windows convenience) | `setup\settings-configurator-ui.cmd` | Finds Python or asks to install the latest Python via `winget`, then launches the wizard. |
| Terminal (Linux convenience) | `sh setup/settings-configurator-ui.sh` | Finds Python or asks to install Python via the system package manager (`apt`, `dnf`, `yum`, `zypper`, `pacman`, or `apk`), then launches the wizard. |
| Standalone exe | `setup/build/dist/cabal[.exe]` | One-file binary that bundles Python, `textual`, `rich`, `global/`, and `setup/env/`. **No Python install required on the target machine.** Build with `python setup/build/build_exe.py`. See [`build/README.md`](build/README.md). |

> **Alternative**: if you only need the shareable Claude Code surface (skills, agents, hooks, MCP servers, output styles) and don't need the global `CLAUDE.md` / permissions / theme / `rules/` / `project-templates/`, you can install prompt-lib as a Claude Code marketplace plugin instead. No Python required. See [`docs/plugin-install.md`](../docs/plugin-install.md). The two install paths ship different surfaces — the PyPI tool deploys the global config; the plugin only registers slash commands and agents inside Claude Code.

## Publishing status

The package metadata and release workflow exist, but a real package release is
gated on the checklist in [`docs/release-readiness.md`](../docs/release-readiness.md).
Do not create a `v*.*.*` tag until the package name, PyPI Trusted Publishing
setup, root test orchestration, local wheel inspection, and executable smoke
test are all complete.

## Primary

**`cabal`** — interactive local agent control panel. Deploys `global/` config to `~/.claude/`, deploys `global/codex/` assets to `~/.codex/`, initializes machine env vars, shows inline drift markers, restores backups, and scaffolds `.claude/` or `.agents/` in other projects.

### Modes

| Mode | Purpose |
|---|---|
| Update global settings | Deploy `global/` → `~/.claude/` with dry-run preview, multi-select component toggles, env-var status panel, and timestamped backups. |
| Initialize env vars | Prompt for each var in `env/setup.env.json`, write to `setx` (Windows) or shell rc (Unix). |
| Restore | Roll back `~/.claude/settings.json` from a timestamped backup. |
| Local project setup | In the current cwd: scaffold `.claude/`, pick a `CLAUDE.md` template, apply git repo-init template, run `specify init` to bootstrap Spec Kit (`.specify/`). |
| Codex setup | Deploy Codex skills to `~/.codex/skills`, scaffold project `.agents/skills`, apply an `AGENTS.md` template, and inspect conversion diffs. |
| Tools | Install / update optional companion tools (Claude CLI, GitHub CLI, **Specify CLI** for GitHub Spec Kit, `claude-devtools`, **Headroom** context-compression CLI). Spec Kit's `specify` is installed via `uv tool install` from the upstream git repo and offers an OS-package `uv` install if missing. Headroom installs via `uv tool install "headroom-ai[mcp]"`; on Windows it builds from source and auto-provisions Rust + VS Build Tools (multi-GB first run). It also registers as an opt-in `headroom` MCP server — see [`../global/MCP.md`](../global/MCP.md). |

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
├── settings-configurator-ui.cmd    ← Windows launcher/bootstrapper for the dev shim
├── settings-configurator-ui.sh     ← POSIX launcher/bootstrapper for the dev shim
├── build/                          ← PyInstaller spec + driver for the .exe
├── env/                            ← machine env var initialization
├── mcp-templates.json              ← MCP server templates (bundled into wheel + exe)
└── tools/                          ← supporting scripts (bash fallback, smoke test, dev installer)
```

The repo root also contains `run` and `run.cmd`; keep them as thin delegators so the setup logic stays inside this folder.

See `build/README.md`, `env/README.md`, and `tools/README.md` for subfolder details.
