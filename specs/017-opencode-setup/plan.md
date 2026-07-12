# Implementation Plan: OpenCode Setup

**Branch**: `feat/opencode-setup` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

## Summary

Add first-class OpenCode setup to Cabal. The implementation creates a dedicated OpenCode screen, explicit CLI and desktop-app install actions, repo-owned OpenCode assets under `global/opencode`, conversion helpers that deploy compatible `global/codex` skills/references to OpenCode, JSON merge behavior for reversible config, and bridge tooling for Codex MCP plus Claude/Gemini/Antigravity command wrappers.

## Technical Context

**Language/Version**: Python 3.14 target, stdlib helpers, Textual UI
**Primary Dependencies**: Textual/Rich, existing npm installer helper, official OpenCode Desktop download/cask paths
**Storage**: Files under `~/.config/opencode` and optional project `.opencode/` assets
**Testing**: pytest helper tests and Textual `run_test` smoke test
**Target Platform**: Windows primary; cross-platform paths use `Path.home()/.config/opencode`
**Constraints**: Preserve existing OpenCode JSON keys; no direct `~/.claude` mutation; external CLI bridges stay ask-gated

## Constitution Check

- **Gate 1 - Spec-First Conformance**: PASS. OpenCode config/MCP/custom-tool shapes follow OpenCode docs; this feature owns only local config generation.
- **Gate 2 - Subagent Delegation**: PASS. Python implementation belongs to `@python-architect`, tests to `@python-tester`, cross-cutting source decisions to `main`.
- **Gate 3 - Contract Tests**: PASS. Tests cover generated config merge, project target shape, Codex MCP config detection, and screen mounting.
- **Gate 4 - Reversible Config Changes**: PASS. Applies through Cabal preview/apply and preserves unrelated JSON keys.
- **Gate 5 - Minimal Skill & Agent Surface**: PASS. No new Claude skill/agent; OpenCode assets are generated for another harness.
- **Gate 6 - Parallel Isolation**: N/A. Implementation is sequential.

## Implementation Notes

- `global/opencode/` contains curated OpenCode config and command tools.
- `setup/src/cabal/opencode_setup/` owns path constants, status probes, preview plans, JSON merge, and apply logic.
- `setup/src/cabal/views/opencode_setup.py` owns the Textual screen and delegates all I/O to helpers/installers.
- OpenCode CLI install uses npm `opencode-ai`; OpenCode Desktop install uses the official macOS cask or OpenCode download endpoints.
- Home wiring adds a new OpenCode Setup section and drift marker.

## Test Plan

- `setup/tests/test_opencode_setup.py`: global apply, JSON merge, project target plan, Codex MCP detection.
- `setup/tests/test_opencode_screen.py`: Textual screen mounts and renders preview rows.
- Focused command: `uv run --with pytest --with pytest-asyncio python -m pytest setup/tests/test_opencode_setup.py setup/tests/test_opencode_screen.py`

## Assumptions

- Existing Codex-compatible skills are the canonical safe conversion source.
- Claude/Gemini/Antigravity bridges are command tools, not native OpenCode agents.
- Codex is the only bridge exposed as an MCP server because `codex mcp-server` is available locally.
