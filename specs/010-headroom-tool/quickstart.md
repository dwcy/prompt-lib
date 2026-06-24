# Quickstart / Verification: Headroom as a Managed Tool

**Feature**: 010-headroom-tool | **Date**: 2026-06-21

End-to-end manual verification. Maps to the spec's Success Criteria (SC-00x). Run from the repo root after implementing the feature and deploying with `python setup/settings-configurator-ui.py`.

## 0. Spike preconditions (Phase 0)
- [ ] `uv tool install "headroom-ai[<extra>]"` succeeds locally; `headroom --version` works in a fresh shell.
- [ ] Confirmed the MCP-serve invocation (expected `headroom mcp serve`) and recorded it in `research.md` §A3.
- [ ] `research.md` §B **Verdict** is filled (pursue/shelve/reject) — SC-005.

## 1. Tools view install (SC-001, SC-002 / US1)
1. Launch the TUI: `python setup/settings-configurator-ui.py`.
2. Open the **Tools** view.
   - [ ] A **Headroom** row is present with description, homepage, and repo link, status `not installed` (if not already installed).
3. Trigger **Install** on the Headroom row.
   - [ ] Action completes; status flips to `installed {version}` on refresh.
   - [ ] `headroom --version` works in a new shell.
4. Trigger install again while installed.
   - [ ] It upgrades or reports already-current, no error (US1 scenario 3).
5. Confirm Headroom also appears in the environment tools listing under the **AI CLIs** group (FR-005).

## 2. MCP register + tools in session (SC-003, SC-004 / US2)
1. Open the cabal **MCP manager**.
   - [ ] `headroom` is listed and **not enabled by default** (scope `template`) — SC-004 / FR-006.
2. Register the Headroom MCP server (user scope).
   - [ ] `claude mcp list` shows `headroom` as **Connected**.
3. Start a **new** Claude Code session.
   - [ ] `headroom_compress`, `headroom_retrieve`, `headroom_stats` are available.
4. Round-trip: call `headroom_compress` on a large input (e.g. a big file or log), note the returned hash + savings, then `headroom_retrieve` with that hash.
   - [ ] The original content comes back unchanged — SC-003 / US2 scenario 3.

## 3. Regression (SC-006 / FR-012)
- [ ] Existing Tools view rows still render and install/status correctly (no import or registry breakage from the new `Tool`/`ENV_INSTALLERS` entries).
- [ ] Existing MCP manager entries (context7, playwright, supabase, …) still enumerate and register.
- [ ] `python -c "import cabal.tools"` (or the cabal smoke test under `setup/`) imports cleanly.

## 4. Docs (FR-011)
- [ ] `global/MCP.md` documents the Headroom MCP server: the 3 tools, that compression is on-demand (not automatic), and the opt-in default.
- [ ] `setup/README.md` mentions Headroom where it enumerates featured tools/MCP coverage.

## Rollback (Constitution Gate 4)
- Source edits: `git checkout` / revert on `010-headroom-tool`.
- Deployed `global/MCP.md`: re-run the configurator (restore flow) or revert + re-apply.
- Registered server: cabal MCP manager remove, or `claude mcp remove -s user headroom`.
- Tool: `uv tool uninstall headroom-ai`.
