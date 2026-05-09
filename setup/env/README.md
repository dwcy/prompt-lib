# setup/env/

Initializes machine-level environment variables that MCP servers in `global/settings.json` depend on (e.g. `GITHUB_PERSONAL_ACCESS_TOKEN`, `FIGMA_ACCESS_TOKEN`, `AZURE_DEVOPS_TOKEN`).

## Files

| File | Purpose |
|---|---|
| `setup.env.json` | Source of truth — fill in your values here |
| `setup.py` | Reads `setup.env.json` and applies values via `setx` on Windows or shell rc files on Unix |
| `setup.sh` | Bash wrapper that locates `python3` / `python` and runs `setup.py` |

## Usage

**Recommended:** go through `setup/apply.py` and pick **Initialize env vars**. It prompts for each variable interactively, writes the values back into `setup.env.json`, then applies them.

**Standalone:** edit `setup.env.json` directly, then run:

```bash
python setup/env/setup.py    # any platform
bash setup/env/setup.sh      # Unix shells
```

Restart your terminal afterwards so child processes pick up the new vars.

## Notes

- `setup.env.json` is intended to be gitignored once filled in (it contains secrets). Verify your `.gitignore` covers it before committing.
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
