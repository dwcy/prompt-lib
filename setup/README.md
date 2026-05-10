# setup/

One-stop entry point for setting up this machine's Claude Code environment.

## Primary

**`apply.py`** — interactive TUI wizard. Deploys `global/` config to `~/.claude/`, initializes machine env vars, runs drift checks, restores backups, and scaffolds `.claude/` in other projects.

```bash
python setup/apply.py        # any shell
setup\apply.cmd              # Windows convenience launcher
```

First run auto-installs `rich` + `questionary` via pip.

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
├── README.md           ← this file
├── apply.py            ← primary wizard
├── apply.cmd           ← Windows launcher
├── env/                ← machine env var initialization
└── tools/              ← supporting scripts (bash fallback, smoke test)
```

See `env/README.md` and `tools/README.md` for subfolder details.
