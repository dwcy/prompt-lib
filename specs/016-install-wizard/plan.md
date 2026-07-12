# Implementation Plan: Installable Distribution with Installation Wizard

**Branch**: `016-install-wizard` | **Date**: 2026-07-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-install-wizard/spec.md`

## Summary

Most of the installable already exists: the `cabal` package (root `pyproject.toml`, hatchling, wheel force-includes `global/` as `cabal/_data/global`), the Textual wizard with dry-run preview / component toggles / timestamped backups / restore / config doctor / cleanup, the PyInstaller exe build, and a tag-triggered release workflow (PyPI Trusted Publishing + GitHub Release + Windows exe). What is missing to satisfy the spec is: (1) an **installation manifest** so upgrade/doctor/uninstall can distinguish managed files from user files and detect interrupted applies, (2) a **non-interactive CLI mode** (`cabal apply/doctor/uninstall/--version`) beside the wizard, (3) a true **uninstall** (today's cleanup only removes stale extras), (4) **interrupted-apply detection and resume/rollback**, and (5) **execution of the release-readiness checklist** — where research found a hard blocker: the PyPI name `cabal` is already taken by an unrelated package. The technical approach is to extend the existing `setup/src/cabal/` services (`diff_apply`, `cleanup_service`, `config_doctor`) headlessly rather than build anything parallel, add an argparse layer in `__main__.py` that defaults to the TUI, and gate the first `v*` tag on the user's name decision + Trusted Publishing setup documented in the runbook.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: Textual >=0.50,<7 and Rich >=13,<15 (runtime); hatchling (build backend); PyInstaller (frozen exe); argparse (stdlib, new CLI layer)
**Storage**: Filesystem only — deploy target `~/.claude/`, new install manifest at `~/.claude/.cabal/install-manifest.json`, existing timestamped backups
**Testing**: pytest (root orchestrator `python scripts/test-all.py --strict-missing`; suites in `setup/tests/`, `tests/`, `global/hooks/tests`)
**Target Platform**: Windows, macOS, Linux terminals (three run-modes already supported by `_paths.py`: source checkout / wheel / frozen exe)
**Project Type**: CLI + TUI tool distributed as a PyPI package, standalone Windows exe, and GitHub Release artifacts
**Performance Goals**: Wizard start-to-verified-install under 10 minutes on a fresh machine (SC-001); non-interactive apply comparable to interactive apply
**Constraints**: Never write env/secret files (FR-011); never modify unmanaged files (FR-010); no one-way changes to `~/.claude/` (constitution IV); no personal identity in the distributed artifact (FR-018 — identity-injection filter already strips it)
**Scale/Scope**: ~5 new/changed modules in `setup/src/cabal/`, 1 workflow file already in place, 1 release runbook, docs updates; single-user tool

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: `N/A — no external protocol`. The CLI surface is documented in `contracts/cli-contract.md`, but it is a tool contract, not a wire protocol (no A2A/MCP/JSON-RPC/OpenAPI surface).
- **Gate 2 — Subagent Delegation**: Delegation table below maps every phase to an owner from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: `N/A — no protocol surface`. The constitution binds this rule to protocol surfaces only. The CLI contract still gets test-first coverage in `tasks.md` (CLI behaviour tests ordered before the argparse implementation) as good practice, not as a constitutional requirement.
- **Gate 4 — Reversible Config Changes**: This feature does **not** edit content under `global/`; all machinery lives in `setup/`, `scripts/`, `.github/`, and `docs/`. Changes it makes *to* `~/.claude/` at runtime remain reversible by design: every overwrite is backed up (existing behaviour), the new manifest adds restore metadata, and uninstall offers backup restoration. Rollback path for the feature itself: `git revert` — nothing deploys to `~/.claude/` until a user runs the tool.
- **Gate 5 — Minimal Skill & Agent Surface**: `N/A — no new skill or agent`. All work extends the existing `cabal` package.
- **Gate 6 — Parallel Isolation**: `N/A`. Implementation dispatches one writing subagent at a time (sequential); no concurrent writers are planned.

No violations → Complexity Tracking table omitted.

## Subagent Delegation

*Owners come from `.specify/memory/agents.md`.*

| Phase / concern | Owner | Why |
|---|---|---|
| Install manifest module + apply integration (`setup/src/cabal/`) | `@python-architect` | Python service-layer design; touches `diff_apply`, new `install_manifest.py` |
| Non-interactive CLI layer (`__main__.py` argparse + headless runners) | `@python-architect` | Python CLI structure decision, reuse of existing services |
| Uninstall service + wizard screen | `@python-architect` | Python + Textual view/worker split per house rules |
| Interrupted-apply detection / resume | `@python-architect` | State-journal design inside the apply flow |
| All pytest suites for the above | `@python-tester` | Every Python test task goes to the tester per constitution II |
| Release workflow verification, runbook, release-readiness execution | `main` | No DevOps agent exists in `.specify/memory/agents.md`; cross-cutting release/CI work is orchestration glue |
| Docs updates (`setup/README.md`, `docs/release-readiness.md`, quickstart) | `main` | Cross-cutting documentation spanning package, CI, and repo conventions |
| Post-implementation verification | `@code-plan-verifier` | Read-only audit gate before commit |

### Parallel Execution Map

`N/A` — all writing tasks are dispatched sequentially; only the read-only `@code-plan-verifier` runs as an additional agent.

## Project Structure

### Documentation (this feature)

```text
specs/016-install-wizard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # Phase 1 output — CLI surface, exit codes, JSON schemas
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
setup/src/cabal/
├── __main__.py              # CHANGED: argparse layer — no args → TUI; subcommands → headless
├── __init__.py               # UNCHANGED: __version__ is now the single source, read via [tool.hatch.version]
├── install_manifest.py      # NEW: manifest read/write/journal (in_progress → complete)
├── apply_service.py         # NEW: shared apply orchestration (build_plan/apply_plan) + manifest recording
│                            #      — extracted here instead of growing diff_apply.py, per the LoC-budget option
├── recovery_service.py      # NEW: interrupted-apply detection/resume/rollback (separate module to
│                            #      avoid an apply_service <-> install_manifest import cycle)
├── manifest_doctor.py       # NEW: manifest-vs-disk health checks (missing/stale/user-modified/
│                            #      interrupted/version-skew) — config_doctor.py was near its LoC cap
├── repair_service.py        # NEW: targeted repair of missing/stale managed files
├── headless.py              # NEW: non-interactive runners (apply/doctor/uninstall) reusing services
├── uninstall_service.py     # NEW: manifest-driven managed-file removal + backup restore offer
├── diff_apply.py            # UNCHANGED: stays the diff/backup primitive layer apply_service builds on
├── cleanup_service.py       # UNCHANGED (stale-extras cleanup remains a separate concern)
├── config_doctor.py         # UNCHANGED (manifest checks live in manifest_doctor.py instead)
└── views/
    ├── uninstall.py         # NEW: wizard screen for uninstall flow (preview → confirm → report)
    ├── recovery_modal.py    # NEW: interrupted-apply Resume/Roll back/Review modal
    ├── update.py            # CHANGED: apply routed through apply_service; recovery guard added
    └── home.py               # CHANGED: startup interrupted-apply check; Uninstall menu entry

setup/tests/
├── test_install_manifest.py # NEW
├── test_headless_cli.py     # NEW (CLI behaviour tests, ordered before argparse impl)
├── test_recovery_service.py # NEW
├── test_recovery_modal.py   # NEW
├── test_manifest_doctor.py  # NEW
├── test_doctor_panel.py     # NEW
└── test_uninstall_service.py# NEW

docs/
├── release-readiness.md     # CHANGED: record name-collision finding + updated checklist state
└── release-runbook.md       # NEW: step-by-step first-release procedure (name, Trusted Publishing, tag)

.github/workflows/release.yml # CHANGED only if the distribution name changes (URL + wheel glob)
pyproject.toml                # CHANGED only when the user confirms the distribution name
```

**Structure Decision**: Extend the existing single-package layout under `setup/src/cabal/` — no new top-level project. New logic follows the house service-module pattern (services own I/O; Textual views stay thin) and the Python LoC budgets in `~/.claude/rules/python.md`.

## Release Blocker (user decision required before first tag)

Research (2026-07-11) confirmed **`cabal` is already taken on PyPI** by an unrelated, actively-maintained package (exact-real-arithmetic library, v0.2.1, June 2026). The first release cannot ship to PyPI under the current name. Recommendation recorded in `research.md`: distribution name **`cabal-panel`** with the console command staying `cabal` (PyPI distribution name and command name are independent). The rename decision, PyPI project creation, and Trusted Publishing environment setup are user-owned steps captured in `docs/release-runbook.md`; implementation proceeds without blocking on them, and no `v*` tag is created as part of this feature.
