# Contract: DashboardPanel widget + HomeScreen integration

**Module**: `setup/src/cabal/widgets/dashboard_panel.py`
**Touches**: `setup/src/cabal/views/home.py`

A Textual `Widget` mounted on `HomeScreen`. Owns `compose()`, worker dispatch, and
render only — **no `subprocess`/network** (those live in the services). Follows the
`ClaudeStatsPanel` / `EnvPanel` shape.

## Widget surface

```python
class DashboardPanel(Widget):
    DEFAULT_CSS = "..."                       # height: auto; per-section blocks
    def compose(self) -> ComposeResult: ...   # title bar + 4 section Static bodies + Refresh button
    def on_mount(self) -> None: ...           # paint cached snapshot, then start workers
    def refresh_dashboard(self) -> None: ...  # re-fetch all sections (manual + on project change)
    def on_button_pressed(self, event) -> None: ...  # Refresh + open-link actions
```

### Naming guard (Textual shadow rule)
Helper methods are named by role, never with framework verb prefixes
(`_render*`/`_compose*`/`_on_*`/`_watch_*`). Use `_build_git_text`,
`_format_github_body`, `_apply_section`, `_fetch_section`. The public override is
`render`-free; the repo `.githooks/pre-commit` will block a collision.

## Behavioural contract

- **C-P1 (cache-first paint)**: `on_mount` reads
  `widget_cache.load_entry("dashboard:<hash(project_path)>")` and paints it before any
  worker starts. With a warm cache, the first frame shows last-known values + a
  "refreshing…" marker (SC-001, FR-050). With no cache, sections show "loading…".
- **C-P2 (non-blocking)**: each section is fetched in
  `run_worker(self._fetch_<s>, thread=True, exclusive=True)`; results applied via
  `self.app.call_from_thread(self._apply_<s>, section)`. The UI thread never runs a
  CLI/HTTP call (FR-051).
- **C-P3 (isolation)**: a worker exception sets only its section to `ERROR`; the other
  three render normally and the rest of Home is unaffected (FR-053, SC-004).
- **C-P4 (project re-scope)**: when `app.selected_project` differs from the snapshot's
  `project_path` (checked on mount / `on_screen_resume`), the panel re-keys the cache
  and re-fetches (FR-003).
- **C-P5 (placeholder)**: `selected_project is None` → panel shows "select a project to
  see its dashboard" and starts no workers (FR-001).
- **C-P6 (links)**: dashboard/PR/run/schema URLs render as `[@click=...]` action links
  that call `webbrowser.open`, and also as copyable text (D7).
- **C-P7 (no secrets cached)**: the snapshot saved via `widget_cache.save_entry` is
  `snapshot.to_cacheable()` — never contains a token (SC-005, FR-054).

## HomeScreen integration (`home.py`)

- `compose()` mounts `DashboardPanel(id="dashboard")` within the home scroll (a panel,
  per the surface decision), near the existing `EnvPanel` / `ClaudeStatsPanel`.
- Add `Binding("ctrl+d", "refresh_dashboard", "Refresh dashboard")` and an
  `action_refresh_dashboard` that calls the panel's `refresh_dashboard()` (guarded by
  try/except like the existing `action_refresh_claude_stats`).
- `on_screen_resume` triggers a project-change check so re-opening Home after switching
  projects re-scopes the dashboard.

## Tests (own these in `tests/integration/`, Textual `Pilot`)

- **C-P-T1**: Mount `HomeScreen` (or the panel in a host App) with `selected_project`
  set to a temp git repo; `await pilot.pause()`; assert the Git section renders the
  branch. (At least one `pilot.pause()` per the Textual smoke-test rule.)
- **C-P-T2**: Warm-cache mount paints cached values without awaiting workers
  (cache-first paint).
- **C-P-T3**: Each `AvailabilityState` permutation renders its hint, no traceback
  (services monkeypatched to return canned sections).
- **C-P-T4**: `selected_project = None` → placeholder, no workers started.
- **C-P-T5 (shadow smoke)**: the panel mounts and renders without a
  `Visual.to_strips` / `_render_content` crash (guards against Textual method-shadow).

## Public-API / facade contract (`tests/contract/`)

- **C-P-C1**: If any new name is re-exported through `cabal.wizard` (e.g. for parity
  with how screens/widgets are surfaced), extend
  `tests/contract/test_wizard_public_api.py` so `cabal.wizard.<name>` resolves to the
  defining module. If nothing is re-exported, no change — the dashboard is reached via
  `HomeScreen`, not the facade. This contract task is ordered before implementation in
  `tasks.md` (Constitution Gate 3, scoped to the public surface).
