# Implementation Plan: Project Dashboard Panel

**Branch**: `008-project-dashboard` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-project-dashboard/spec.md`

## Summary

Add a per-project **dashboard panel to the cabal HomeScreen** that aggregates
status for `CabalApp.selected_project` from four sources — local git, GitHub,
Supabase, and Vercel — each as a labelled section in one widget. Data comes from
already-authenticated local CLIs (`git`, `gh`, `supabase`, `vercel`) plus each
project's local link files, enriched from the Supabase/Vercel management APIs when
an access-token env var is present. All I/O runs in Textual worker threads behind
the existing stale-while-revalidate cache (`widget_cache.py`), so the HomeScreen
never blocks. The technical approach mirrors the established cabal patterns:
service modules own subprocess/HTTP I/O, a thin panel widget owns compose + render,
and integration tests use Textual `Pilot`.

## Technical Context

**Language/Version**: Python 3.11+ (`from __future__ import annotations` everywhere)
**Primary Dependencies**: Textual (TUI), Rich (markup); stdlib `subprocess`,
`json`, `pathlib`, `urllib.request` for management-API calls (no new HTTP dep —
match existing zero-extra-dependency posture unless `requests` is already vendored)
**External tools (optional, detected at runtime)**: `git`, `gh`, `supabase`, `vercel`
**Storage**: `~/.cabal/cache.json` via existing `widget_cache.py` (payload keyed by
project path); no new persistence. Tokens are NEVER cached.
**Testing**: pytest + Textual `Pilot` (`App.run_test()` with `pilot.pause()`), under
`tests/integration/` and `tests/unit/`; contract test for the public surface under
`tests/contract/`
**Target Platform**: Cross-platform desktop terminal (Windows / macOS / Linux) —
cabal runs everywhere; subprocess argv must resolve via `shutil.which`
**Project Type**: Desktop TUI application (single project, `setup/src/cabal/`)
**Performance Goals**: First paint from warm cache within one frame of HomeScreen
mount; no worker blocks the UI thread; bounded per-section subprocess/HTTP timeouts
**Constraints**: Read-only (no deploy/migrate/mutate); graceful degradation for every
missing-CLI / not-linked / no-token / token-rejected permutation; no token persisted
**Scale/Scope**: 1 panel widget + 4 sections; ~4 service modules; ~5 data sources;
single selected project at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: N/A — no external protocol is *implemented*
  here. The Supabase and Vercel management APIs are *consumed* read-only over their
  documented REST shapes; we conform to them as clients but publish no protocol
  surface of our own. Contract tests cover our internal public API surface only.
- **Gate 2 — Subagent Delegation**: PASS — delegation table below maps every phase to
  an owner from `.specify/memory/agents.md`. All Python work → `@python-architect`;
  all tests → `@python-tester`; verification → `@code-plan-verifier`.
- **Gate 3 — Contract Tests Before Implementation**: PASS (scoped) — there is no wire
  protocol surface we publish, so Principle III's binding clause (protocol surfaces)
  is N/A. We DO extend the existing public-API contract test
  (`tests/contract/test_wizard_public_api.py`) for any names re-exported via
  `cabal.wizard`; that contract task is ordered before implementation in `tasks.md`.
- **Gate 4 — Reversible Config Changes**: N/A — this feature adds source under
  `setup/src/cabal/` (the application), NOT under `global/`. It does not change any
  file deployed to `~/.claude/`. No rollback path needed beyond reverting the branch.
- **Gate 5 — Minimal Skill & Agent Surface**: N/A — no new skill or agent is added.
  The feature adds application widgets/services to cabal, reusing existing agents.
- **Gate 6 — Parallel Isolation**: N/A — implementation is sequential single-agent
  dispatch (`@python-architect` then `@python-tester`, one writer at a time). No phase
  dispatches two or more writing subagents concurrently. See Parallel Execution Map.

No violations → Complexity Tracking table is empty.

## Subagent Delegation

*GATE: References `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Data models (`DashboardSnapshot`, section dataclasses, `AvailabilityState`) | `@python-architect` | Python dataclass/domain design in a Python project |
| Service modules (git / gh / supabase / vercel I/O + management-API clients) | `@python-architect` | Subprocess + HTTP service-layer design, async/worker patterns |
| Dashboard panel widget + HomeScreen integration | `@python-architect` | Textual widget structure, worker dispatch, render pipeline |
| Unit tests (service parsers, link-file detection, URL derivation) | `@python-tester` | pytest unit tests with fixtures, no live network |
| Integration tests (Pilot mount/render per AvailabilityState; cache paint) | `@python-tester` | Textual `Pilot` integration tests |
| Contract test extension (public API surface via `cabal.wizard`) | `@python-tester` | Extends existing `tests/contract/` surface |
| Verification of implementation against this plan | `@code-plan-verifier` | Read-only plan-compliance gate before commit |
| Cross-cutting orchestration / this plan / ADR notes | `main` | Spans models + services + UI + tests |

No specialist gap → no `Owner: main` implementation rows.

### Parallel Execution Map

*GATE 6.*

N/A — no phase dispatches two or more writing subagents concurrently. Implementation
is sequential: `@python-architect` builds models → services → widget, then
`@python-tester` writes tests, then `@code-plan-verifier` audits. One writer at a time
on the shared tree; no worktree isolation required.

## Project Structure

### Documentation (this feature)

```text
specs/008-project-dashboard/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal module contracts)
│   ├── dashboard_models.md
│   ├── dashboard_services.md
│   └── dashboard_panel.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
setup/src/cabal/
├── models/
│   └── dashboard.py                 # DashboardSnapshot + section dataclasses + AvailabilityState
├── dashboard_git_service.py         # local git: branches, remotes, current branch (subprocess)
├── dashboard_github_service.py      # gh: actions runs + PRs for current branch; GitHub remote detection
├── dashboard_supabase_service.py    # supabase CLI + config.toml link + management-API client
├── dashboard_vercel_service.py      # vercel CLI + .vercel/project.json + REST client
├── dashboard_links.py               # parse supabase/config.toml + .vercel/project.json; URL derivation
├── widgets/
│   └── dashboard_panel.py           # DashboardPanel widget: compose + 4 sections + workers + render
└── views/
    └── home.py                      # MODIFIED: mount DashboardPanel; add refresh binding

setup/src/cabal/wizard.py            # MODIFIED (if any name is part of the public facade)

tests/
├── contract/
│   └── test_wizard_public_api.py    # MODIFIED: assert any newly re-exported names resolve
├── unit/
│   ├── test_dashboard_links.py      # link-file parsing + URL derivation (no network)
│   ├── test_dashboard_git_service.py# branch/remote parsing from canned git output
│   └── test_dashboard_services.py   # gh/supabase/vercel parsers + AvailabilityState logic
└── integration/
    └── test_dashboard_panel.py      # Pilot: mount + render across AvailabilityState permutations; cache paint
```

**Structure Decision**: Single-project layout under `setup/src/cabal/`. Per the
project's Python size rules and concern-separation triggers, **all subprocess / HTTP
I/O lives in `dashboard_*_service.py` modules**; the `DashboardPanel` widget owns only
`compose()`, worker dispatch, and rendering (no direct `subprocess.run` / network in
the widget). Data shapes live in `models/dashboard.py`. Link-file parsing and URL
derivation are isolated in `dashboard_links.py` so they are unit-testable without any
CLI or network. This keeps every file under its soft cap and each module
single-responsibility (mirrors the 005 `*_service.py` + widget + view split).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
