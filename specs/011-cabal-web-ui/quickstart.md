# Quickstart: Cabal Web UI

This feature is a local read-only browser UI for Cabal.

## Start the Local Web UI

Run from the repository root or the `011-cabal-web-ui` worktree:

```powershell
.\run-web-ui.cmd
```

POSIX shells can use:

```bash
./run-web-ui
```

Direct module fallback:

```powershell
python -m cabal.web --host 127.0.0.1 --port 8765 --project .
```

Then open:

```text
http://127.0.0.1:8765/
```

## Expected First Screen

- Dark application shell.
- Overview metrics for Tools, Knowledge, Project Health, and Diagnostics.
- Section-level loading or error states instead of a blank app.
- Navigation for Overview, Tools, Knowledge, Project Health, and Diagnostics.

## Tools Scenario

1. Open `http://127.0.0.1:8765/`.
2. Select Tools.
3. Search for `git`, filter by category/status/channel, then select a result.
4. Confirm the detail drawer shows catalog metadata, platform support, status detail, source state, version metadata, backup policy, and safety notes.

## Knowledge and Project Health Scenario

1. Select Knowledge and verify either graph routes render or the missing-graph empty state appears.
2. Use the search, node-type, and relation filters.
3. Select Project Health and confirm Git, GitHub, Supabase, and Vercel sections render independent availability states.

## Verify Backend Endpoints

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
Invoke-RestMethod http://127.0.0.1:8765/api/tools
Invoke-RestMethod http://127.0.0.1:8765/api/knowledge
Invoke-RestMethod http://127.0.0.1:8765/api/project-health
Invoke-RestMethod http://127.0.0.1:8765/api/diagnostics
```

Each response should include `schema_version`, `captured_at`, `status`, `source`, `data`, and `error`.

## Run Planned Tests

```powershell
python -m pytest tests/contract/test_cabal_web_api_contract.py
python -m pytest tests/contract/test_cabal_web_frontend_contract.py
python -m pytest tests/contract/test_cabal_web_redaction_contract.py
python -m pytest tests/unit/test_cabal_web_serializers.py tests/unit/test_cabal_web_redaction.py
python -m pytest tests/integration/test_cabal_web_server.py tests/integration/test_cabal_web_assets.py
```

Before completing implementation, also run the existing focused Cabal tests that cover tool catalog, dashboard, and OKF behavior.

## Existing Focused Cabal Tests

```powershell
python -m pytest setup/tests/test_tools_catalog.py tests/unit/test_dashboard_git_service.py tests/unit/test_dashboard_github_service.py tests/unit/test_dashboard_supabase_service.py tests/unit/test_dashboard_vercel_service.py tests/contract/test_okf_analytics_contract.py tests/integration/test_dashboard_panel.py
```

## Manual Visual Check

1. Open the app on a desktop viewport.
2. Open it again on a narrow mobile-like viewport.
3. Confirm no text overlaps, labels clip, or controls jump when loading/error states appear.
4. Disconnect or stop the backend and confirm the UI shows section errors without losing the application shell.
5. Confirm selected/copied text contains only redacted visible values.

## Final Verification Results

Recorded on 2026-06-29 from `C:\projects\prompt-lib\.worktrees\011-cabal-web-ui`.

- System `python -m pytest ...` could not run because the active Python 3.14 environment did not have `pytest` installed.
- Focused web suite run with `uv run --no-project --with pytest --with rich --with textual python -m pytest --basetemp .pytest-tmp\focused-final ...`: 59 passed.
- Existing focused Cabal regression slice run with `uv run --with pytest --with pytest-asyncio python -m pytest --basetemp .pytest-tmp\existing-project ...`: 107 passed, 2 failed. The failures are in `tests/contract/test_okf_analytics_contract.py` because the existing `python -m cabal.okf` CLI currently exposes `export`, `doctor`, `graph`, and `recommend`, but those tests expect `index` and `analytics`.
- Secret audit over `setup/src/cabal/web/` and the new web tests found no raw token-shaped values with the credential-value scan.
- Launch verification using `.venv\Scripts\python -m cabal.web --host 127.0.0.1 --port 8765 --project .`: `/api/health` returned `ok`, `/` returned HTTP 200 with the app shell, and `/api/tools` returned 57 catalog items.
- Browser smoke verification with Playwright using system Chrome at 1440x960 and 390x844: all five views loaded with schema `cabal-web.v1`, no console errors, and no flagged control or panel overflow.
