# setup/env/

Initializes machine-level environment variables that MCP servers in `global/settings.json` depend on (e.g. `GITHUB_PERSONAL_ACCESS_TOKEN`, `FIGMA_ACCESS_TOKEN`, `AZURE_DEVOPS_TOKEN`).

## Files

| File | Purpose |
|---|---|
| `setup.env.example.json` | Reference only — lists all expected variable names. Never written to or read for values. |
| `setup.py` | Reads variable values from the system environment and writes them to shell rc files (Unix) or sets them via `setx` (Windows). |
| `setup.sh` | Bash wrapper that locates `python3` / `python` and runs `setup.py` |

## Usage

**Recommended:** go through `setup/settings-configurator-ui.py` and pick **Env vars**. It pre-fills each field from the current system environment, lets you edit values, then applies them.

**Standalone:** set the variables in your environment first, then run:

```bash
python setup/env/setup.py    # any platform
bash setup/env/setup.sh      # Unix shells
```

Restart your terminal afterwards so child processes pick up the new vars.

## Notes

- Values are always read from the system environment — never from `setup.env.example.json`. That file is a reference for which variables are expected; it contains no secrets and is safe to commit.
- On Windows, `setx` writes to the user-level registry — values persist across sessions but not into the current shell. Hence the restart requirement.
- On Unix, the script appends `export` lines under a `# claude-code-env` marker in `~/.bashrc`, `~/.zshrc`, and `~/.profile` (skipping any that don't exist). Re-running replaces the previous block, so it's idempotent.

## Special key: `GIT_LINE_ENDINGS`

Controls Git's `core.autocrlf` config (line-ending normalization). Unlike the other keys, this one has a side-effect beyond setting the env var: the wizard runs `git config --global core.autocrlf <value>` when applied.

| Value | Meaning | Best for |
|---|---|---|
| `auto` *(default)* | Picks `true` on Windows, `input` on Unix. | Most users. |
| `true` | Commit LF, check out CRLF. | Windows-only repos. |
| `input` | Commit LF, no conversion on checkout. | Mac/Linux machines, cross-platform teams. |
| `false` | No conversion at all. | Special cases (mixed-ending repos, manual control). |

For per-file overrides, use a `.gitattributes` file in each repo (the `/git init` skill drops one in from `global/git/.gitattributes`). `.gitattributes` rules **always win** over `core.autocrlf`, so you can keep `core.autocrlf=true` globally and still force LF or CRLF on specific patterns.
