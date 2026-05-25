# setup/tools/

Supporting scripts for `setup/settings-configurator-ui.py`. Not interactive — meant for CI, debugging, or when the wizard isn't available.

## Files

| File | Purpose |
|---|---|
| `apply-global-claude-settings.sh` | Non-interactive bash fallback. Copies `global/` → `~/.claude/` deterministically. Use in CI or when running headless. |
| `install-dev-tools.py` | Cross-platform bulk installer for dev prerequisites (Python, .NET SDK, Node, GitHub CLI, pnpm, Claude CLI, Gemini CLI, Codex CLI, **`uv` + Specify CLI**). Windows uses `winget`, Linux uses `dnf`. |
| `validate-plugin.py` | Validates the prompt-lib plugin manifest against `specs/004-github-plugin/contracts/plugin-manifest.contract.md`. |
| `_smoketest.py` | Regression test — imports `settings-configurator-ui.py` and checks core helpers (`detect_env`, `find_env_vars`, `diff_component`) work without raising. Run after editing `settings-configurator-ui.py` or `global/hooks/command_guard.py`. |

## Usage

```bash
# Bash fallback (no UI, no preview, no backup prompts)
bash setup/tools/apply-global-claude-settings.sh

# Bulk install dev tools (winget on Windows, dnf on Fedora-family)
python setup/tools/install-dev-tools.py

# Spec Kit only — manual install:
#   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
#   specify init --here --integration claude    # run inside the target project

# Smoke test (after editing settings-configurator-ui.py)
python setup/tools/_smoketest.py
```
