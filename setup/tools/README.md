# setup/tools/

Supporting scripts for `setup/apply.py`. Not interactive — meant for CI, debugging, or when the wizard isn't available.

## Files

| File | Purpose |
|---|---|
| `apply-global-claude-settings.sh` | Non-interactive bash fallback. Copies `global/` → `~/.claude/` deterministically. Use in CI or when running headless. |
| `_smoketest.py` | Regression test — imports `apply.py` and checks core helpers (`detect_env`, `find_env_vars`, `diff_component`) work without raising. Run after editing `apply.py` or `global/hooks/command_guard.py`. |

## Usage

```bash
# Bash fallback (no UI, no preview, no backup prompts)
bash setup/tools/apply-global-claude-settings.sh

# Smoke test (after editing apply.py)
python setup/tools/_smoketest.py
```
