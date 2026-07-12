# Quickstart: OpenCode Setup

1. Run Cabal with `python setup/settings-configurator-ui.py`.
2. Open the Home screen and choose **OpenCode Setup**.
3. If the terminal CLI is missing, press **Install CLI**.
4. If the desktop app is missing, press **Install Desktop App**.
5. Review the preview table.
6. Press **Apply Global** to write `~/.config/opencode` assets.
7. Press **Apply Project** to write project `opencode.json` and `.opencode/` assets.
8. Restart OpenCode and run:

```powershell
opencode --version
opencode mcp list
```

9. Confirm Codex MCP and bridge tools are permission-gated before use.
