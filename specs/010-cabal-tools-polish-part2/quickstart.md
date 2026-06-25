# Quickstart: Cabal Tools View Polish Part 2

## Prerequisites

- Python environment that can run the Cabal test suite.
- Optional for manual database checks: Docker or Podman installed and running.
- Optional for Windows-only checks: winget, Visual Studio Installer, and Windows desktop session.

## Automated validation

Run the focused tests expected from this feature after tasks are implemented:

```powershell
python -m pytest setup/tests/test_tools_catalog.py
python -m pytest tests/unit/test_database_container_specs.py
python -m pytest tests/unit/test_tool_versions.py
python -m pytest tests/unit/test_runtime_backups.py
python -m pytest tests/integration/test_tools_screen_copy.py
python -m pytest tests/integration/test_tools_screen_versions.py
```

Run the existing guard tests that should remain green:

```powershell
python -m pytest tests/integration/test_ctrl_c_quits.py setup/tests/test_clipboard.py tests/unit/test_vllm_tools.py setup/tests/test_tools_vercel_plugin.py
```

## Manual Tools view walkthrough

1. Launch Cabal:

   ```powershell
   python -m cabal
   ```

2. Open the Tools view.
3. Confirm every visible row has:
   - label
   - short description
   - status text
   - read-more/source action or explicit source-unavailable state
4. Confirm the new sections exist:
   - Database Clients
   - Azure Local Tools
   - Developer Tools
5. Confirm Local AI includes LM Studio, Hermes agent, OpenCode, Ollama, and vLLM.
6. Confirm IDE/editor entries include Zed, Rider, Visual Studio, Cursor, Windsurf, Antigravity, and VS Code.
7. Select description/status/error text and press Ctrl+C. Paste into a scratch buffer and confirm the copied text matches the visible text.

## Database service walkthrough

With Docker or Podman running:

1. Open the Databases section.
2. Install or dry-run Redis, MariaDB, Qdrant, Weaviate, and Milvus.
3. Confirm each flow reports:
   - container engine readiness
   - image/name/port/volume checks
   - health status
   - logs guidance
   - cleanup guidance
4. Stop the container engine and repeat one install attempt. Confirm Cabal reports the engine problem and does not claim success.
5. Bind a required port with another process or container and confirm Cabal reports the conflict.
6. Confirm SQLite and DuckDB are labelled as embedded/file-oriented rather than daemon services.

## Runtime version and backup walkthrough

1. Open version selectors for Bun, npm, pnpm, Python, Node, and dotnet.
2. Confirm installed/current version appears even if fresh metadata is unavailable.
3. Confirm latest versions appear when metadata is available.
4. Confirm Node and dotnet highlight LTS channels where upstream metadata defines them.
5. Confirm Python shows supported branch status without fake LTS labels.
6. Start an update with backup enabled.
7. Confirm Cabal records previous version, executable path, install channel, and restore guidance before changing anything.

## OpenCode and Hermes checks

1. If OpenCode desktop app is installed but CLI is not on PATH, confirm Cabal shows app-present and CLI-missing separately.
2. If OpenCode CLI is installed but desktop app is not present, confirm Cabal shows CLI-present and app-missing separately.
3. Confirm Hermes agent is visible but automated install is blocked unless a verified official source URL/install channel is configured.

## Acceptance checklist

- [ ] 100% of rendered rows have descriptions.
- [ ] 100% of rendered rows have verified source links or explicit source-required/unavailable state.
- [ ] Requested new tools appear in the expected sections.
- [ ] Database service installs no longer use direct host server package installs for service databases.
- [ ] Ctrl+C copies selected Tools view text.
- [ ] Runtime version selectors and backup records work for the six requested runtimes.
- [ ] No token-shaped string is displayed in status, logs, copied output, or backup records.

## Local validation notes

- 2026-06-25: Focused feature suite passed in `.venv` with `26 passed`.
- 2026-06-25: Existing guard suite passed in `.venv` with `18 passed`.
- 2026-06-25: Broader `setup/tests tests/unit tests/integration` run timed out locally before producing actionable failures.
