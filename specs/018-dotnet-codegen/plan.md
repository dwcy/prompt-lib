# Implementation Plan: dotnet-codegen

**Branch**: `018-dotnet-codegen` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-dotnet-codegen/spec.md`

## Summary

Build a five-stage code generation pipeline for .NET backends — **route, architect, gate, write, verify** — that attacks the four cost centres identified in [research.md](./research.md) with machinery rather than discipline.

**The delivery-form question the spec deferred is resolved here: option (d), a staged hybrid.** The pipeline is owned as a Python package inside the existing `cabal` codebase, entered through a thin Claude Code skill, with the Roslyn semantic map deferred to a brownfield Phase B. The reasoning is in *Delivery Form Decision* below: a prompt-only slice cannot meet five of the twelve success criteria for structural reasons, not for want of effort.

Phase A delivers US1-US5 (greenfield). Phase B delivers US6 (brownfield) and is separately gated.

## Technical Context

**Language/Version**: Python 3.14+ for the pipeline (matches root `pyproject.toml` `requires-python = ">=3.14"`); C# / **.NET 10** as the *generated* target
**Primary Dependencies**: .NET SDK (`dotnet new` / `build` / `test`) as scaffold and verification signal; **four hand-rolled provider paths** (CLI-shell via the `claude`/`codex` CLIs using existing subscription auth and needing no API key; OpenAI-compatible via `base_url` — covers hosted OpenAI plus local Ollama and LM Studio; Anthropic; Google) rather than a broker such as LiteLLM, because per-stage *cached-token* counts are required by SC-005 and SC-010 and brokers normalise usage fields lossily; existing `cabal.session_pricing` for cost lookup. No new frontend or web dependencies.
**Storage**: Files on disk. Per-project state (locked template, structural-map cache, run records) in `.dotnetgen/` inside the generated solution; no database. **Stage bindings live in `global/dotnetgen-bindings.toml`** — one per-machine file, deployed and version-controlled like every other `global/` asset, with an optional per-project override. It holds provider and model *names only*; API keys stay in the environment, are read at runtime, and are never written by the tool (standing env-file rule).
**Testing**: `pytest` under `setup/tests/` for the pipeline; generated solutions are verified by `dotnet build` + `dotnet test`, which is the pipeline's own feedback signal
**Target Platform**: Windows-first (developer's machine), POSIX-compatible. Local-model support requires a locally-running OpenAI-compatible endpoint.
**Project Type**: CLI pipeline (library + headless command surface) plus one Claude Code skill as the entry point
**Performance Goals**: SC-001 under 10 minutes to a running service after one approval; structural map under 2% of source size (SC-006); 70%+ of served context from cache across 5+ runs (SC-005)
**Constraints**: Hard retry ceiling, default **3**, that cannot be exceeded (SC-007); no code written before approval (SC-011); cost record reconciling within 5% (SC-010); must not modify any existing .NET asset in `global/` (FR-032a)
**Scale/Scope**: Phase A targets solutions the tool generated (hundreds to low thousands of lines). Phase B targets 20k+ line existing solutions.

## Delivery Form Decision

The spec left this open deliberately. Each option is scored against every success criterion. `--` means *structurally cannot*, not *harder*.

| Criterion | (a) Prompt-only skill | (b) MCP + skill | (c) Standalone agent | (d) Staged hybrid |
|---|---|---|---|---|
| SC-001 under 10 min to running service | yes | yes | yes | **yes** |
| SC-002 <=40% of unassisted tokens | **--** no cheap writer, no cache control | partial | yes | **yes** |
| SC-003 >=90% first-attempt edit apply | **--** host edit tool is exact-match only | yes | yes | **yes** |
| SC-004 >=70% first-attempt compile | yes | yes | yes | **yes** |
| SC-005 >=70% context from cache | **--** cannot order the host prefix | **--** map arrives as a volatile tool result | yes | **yes** |
| SC-006 map under 2% of source | **--** no ranked, budgeted map | yes | yes | **yes** (Phase B) |
| SC-007 retry ceiling never exceeded | weak — unenforced prompt discipline | weak | yes | **yes** |
| SC-008 local writer halves cost | **--** no per-stage provider routing | **--** host still writes | yes | **yes** |
| SC-009 questions bypass the pipeline | yes | yes | yes | **yes** |
| SC-010 cost record within 5% | **--** no per-stage token accounting | partial | yes | **yes** |
| SC-011 no code before approval | yes | yes | yes | **yes** |
| SC-012 zero architecture tokens | yes | yes | yes | **yes** |

**Option (a) is rejected.** It fails SC-002, SC-003, SC-005, SC-008 and SC-010 outright and is weak on SC-007. The common cause is that a skill executing inside a host session does not own the things these criteria measure: it cannot order the cache prefix, cannot bind a stage to a different provider, cannot account tokens per stage, and cannot substitute a fuzzy applier for the host's exact-match edit tool. Note this is *not* a claim that (a) is worthless — per research 1.4, the architect/editor split alone is worth roughly three points even on one model, so much of the *quality* benefit is reachable from prompts. It is the *cost* benefit that is not.

**Option (b) alone is rejected.** An MCP server fixes the structural map and can host a proper applier, but the host session still performs the writing on the host's model, so SC-008 and SC-010 stay out of reach. It also activates Constitution Gates 1 and 3 (MCP is an external protocol) — real cost that buys nothing for greenfield, where the solution's shape is already known from the template (research R2).

**Option (c) is rejected as a starting point, not on capability.** It meets everything, but it rebuilds a tool loop that already exists, and it moves the developer's entry point outside Claude Code — which orphans the feature from the repository whose entire purpose is Claude Code assets.

**Option (d) is chosen.** Own the loop where control is genuinely required (provider routing, prefix ordering, retry ceiling, cost ledger, edit application); keep the entry point inside Claude Code as a thin skill; reuse `dotnet new` for the scaffold and `cabal.session_pricing` for cost; defer the Roslyn map until brownfield actually needs it.

### Locked template set (FR-001 requires naming it)

**Three templates.** Chosen once at project creation, recorded in the project, never re-decided (FR-001a/b/c).

| Template | Shape | Use when | Projects |
|---|---|---|---|
| `minimal-service` | Single project, minimal API, feature folders, EF Core, no mediator | Small service, few endpoints, fastest to green | 2 (Api, Tests) |
| `vertical-slice` (**default**) | Feature-folder slices, one handler per slice, EF Core | Most services — the default recommendation | 3 (Api, Domain, Tests) |
| `clean-arch` | Domain / Application / Infrastructure / Api layering with CQRS | Larger service, multiple consumers, long life | 5 (4 + Tests) |

Three is the maximum that can be kept genuinely maintained and tested. All three inherit `global/rules/csharp.md` unchanged — one type per file, the size caps, Command/Query separation, domain layer with zero external dependencies — which is what makes them a cacheable band-2 constant (research R5).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Per `.specify/memory/constitution.md` v1.1.0:

- **Gate 1 — Spec-First Conformance**: **N/A for Phase A** — no external protocol is implemented. The pipeline is a local CLI plus a skill. **Applies to Phase B**: if the Roslyn map ships as an MCP server, the MCP specification becomes authoritative, must be linked, and a conformance scope must be stated at that time. Recorded as a Phase B entry condition, not deferred silently.
- **Gate 2 — Subagent Delegation**: Satisfied — see the delegation table below, drawn from `.specify/memory/agents.md`.
- **Gate 3 — Contract Tests Before Implementation**: **Applies.** Two surfaces need contract tests written and observed failing first: (1) the **headless CLI command surface** (`contracts/cli-surface.md`) — its `--json` output is consumed by the skill, making it a real wire contract; (2) the **edit-operation schema** (`contracts/edit-operation.schema.json`) — the boundary between the writing stage and the applier, and the thing SC-003 is measured on. Phase B adds MCP tool schemas.
- **Gate 4 — Reversible Config Changes**: **Applies.** This feature adds `global/skills/dotnet-codegen/`. Rollback: delete that directory and re-run `python setup/settings-configurator-ui.py` (or `bash setup/tools/apply-global-claude-settings.sh`). No existing file under `global/` is modified, so rollback is a pure deletion with no restore step — this is a direct consequence of the coexist decision (FR-032a) and was a factor in choosing it.
- **Gate 5 — Minimal Skill & Agent Surface**: **Justified.** One new skill, `/dotnet-codegen`. It cannot be an extension of an existing asset: `/dotnet-class` generates a single type from a prompt with no verification loop, retry ceiling, or cost accounting; `@dotnet-architect` is a reasoning agent with no execution surface and explicitly defers architecture to each project's CLAUDE.md, which is the opposite of a locked template; `@dotnet-tester` owns test authoring only. The new skill is a *driver* for a pipeline that has no existing home. No new agent is added — the existing agents are reused as owners (see delegation table). `/review-conflicts` to be run before merge per Principle V.
- **Gate 6 — Parallel Isolation**: **Applies** — see the Parallel Execution Map below. Two phases dispatch concurrent writers.

No unresolved violations. Complexity Tracking is empty.

## Subagent Delegation

*Owners drawn from `.specify/memory/agents.md`. No invented names.*

| Phase / concern | Owner | Why |
|---|---|---|
| Pipeline package structure, stage orchestration, provider abstraction | `@python-architect` | Python service-layer and DI structure decisions in `setup/src/cabal/` |
| Context banding + structural map extractor | `@python-architect` | Python module design; the banding rule is a structural concern |
| Edit applier + relaxation ladder | `@python-architect` | Pure Python algorithm work |
| Verification adapter + diagnostic classification | `@python-architect` | Wraps `dotnet` subprocess calls from Python |
| Cost ledger (reusing `session_pricing`) | `@python-architect` | Extends existing Python module |
| All pipeline tests | `@python-tester` | pytest; architects must not write their own tests (agents.md anti-pattern) |
| The three C# template contents | `@dotnet-architect` | `.csproj` / `.cs` layering and CQRS structure — the decision matrix maps `.cs` to this owner |
| Generated-solution test scaffolding inside templates | `@dotnet-tester` | xUnit structure; every .NET test task goes here |
| `global/skills/dotnet-codegen/SKILL.md` | `main` | Skill authoring is a prompt-asset concern with no specialist owner in the roster |
| Cache-band ordering decision, cost-centre accounting design, ADRs | `main` | Cross-cutting; spans Python, C#, and prompt assets |
| Post-implementation audit against this plan | `@code-plan-verifier` | Read-only gate before merge |

### Parallel Execution Map

*GATE 6.*

| Phase | Concurrent agents | Tasks (IDs) | Integration branch |
|---|---|---|---|
| Phase A — templates vs. pipeline core | `@dotnet-architect` (C# templates), `@python-architect` (pipeline package) | assigned in `tasks.md` | `018-dotnet-codegen` |
| Phase A — verification adapter vs. edit applier | `@python-architect` (x2, independent modules) | assigned in `tasks.md` | `018-dotnet-codegen` |

Both rows are genuinely independent file sets — the C# templates and the Python package share nothing, and the applier and verifier are separate modules behind separate interfaces. Every writer in these batches is dispatched with `isolation: "worktree"`; the matching tasks in `tasks.md` MUST carry `Parallel: yes`. Test tasks run **sequentially after** their implementation, so `@python-tester` never races a writer.

## Project Structure

### Documentation (this feature)

```text
specs/018-dotnet-codegen/
├── plan.md                          # This file
├── spec.md
├── research.md                      # Phase 0
├── data-model.md                    # Phase 1
├── quickstart.md                    # Phase 1
├── contracts/                       # Phase 1
│   ├── cli-surface.md
│   ├── edit-operation.schema.json
│   └── run-record.schema.json
├── checklists/requirements.md
└── tasks.md                         # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
setup/src/cabal/dotnetgen/           # NEW — the pipeline
├── __init__.py
├── cli.py                           # headless surface; mirrors cabal/headless.py argparse + --json shape
├── pipeline.py                      # stage orchestration, approval gate, retry ceiling
├── stages/
│   ├── route.py                     # FR-010  question vs change
│   ├── architect.py                 # FR-011  prose intent, no code
│   ├── write.py                     # FR-011  intent -> EditOperations
│   └── verify.py                    # FR-019  build + test
├── context/
│   ├── bands.py                     # FR-008  five-band stable-to-volatile assembly
│   └── map_csharp.py                # FR-005  signatures-only extractor (syntax level, Phase A)
├── edits/
│   ├── model.py                     # EditOperation
│   ├── anchor_csharp.py             # R1  symbol anchoring
│   └── applier.py                   # FR-016  relaxation ladder
├── verify/
│   └── dotnet.py                    # R4  diagnostic-ID classification
├── providers/
│   ├── base.py                      # FR-024/026  stage-bindable interface
│   ├── cli_shell.py                 # subscription auth, persistent subprocess, no API key
│   └── <one module per provider>    # Anthropic, OpenAI, Google, local OpenAI-compatible
├── ledger.py                        # FR-028  run record; reuses cabal.session_pricing
├── templates/                       # the three locked templates
│   ├── minimal-service/
│   ├── vertical-slice/
│   └── clean-arch/
└── state.py                         # per-project locked template + map fingerprint

global/skills/dotnet-codegen/        # NEW — the entry point
└── SKILL.md

setup/tests/dotnetgen/               # NEW — pipeline tests
├── contract/                        # Gate 3 — written and failing first
├── integration/
└── unit/
```

**Structure Decision**: The pipeline lives at `setup/src/cabal/dotnetgen/` rather than as a new top-level package, because `cabal` is already this repo's Python home, already ships a headless CLI pattern (`cabal/headless.py`), and already owns the cost-lookup module the ledger needs (`cabal/session_pricing.py`). Tests follow the existing `setup/tests/` root. The only addition under `global/` is one new skill directory, which keeps Gate 4 rollback to a single deletion.

The `context/`, `edits/`, `verify/` and `providers/` packages are the **language-agnostic seam required by FR-030**: only `map_csharp.py`, `anchor_csharp.py` and `verify/dotnet.py` know about C#. A future Python or frontend target adds sibling modules without touching `pipeline.py`, `bands.py`, `applier.py`, `providers/` or `ledger.py`. FR-031 holds — no second language is built here.

## Phase Gating

**Phase A (this feature)** — US1 through US5, greenfield. Exit criteria: SC-001, SC-002, SC-003, SC-004, SC-005, SC-007, SC-008, SC-009, SC-010, SC-011, SC-012 measured and met.

**SC-006 is now measured in Phase A, as a number rather than a target** (revised — tasks.md T075). The original reasoning stands for the *edit* path: a template-generated solution's structure is known rather than discovered, so exercising the map's ranking against one proves nothing (research R2). But `map` is read-only. Pointing it at a real large solution for measurement alone — no `change` run, no edit application, no convention inference — costs a corpus solution and yields the ratio before Phase 4's design is committed to, instead of after Phase B begins. If the ratio misses 2%, that is recorded as a Phase B entry finding, not tuned away.

**Phase B (separately gated, may become its own feature)** — US6, brownfield. Entry conditions: Phase A exit criteria met; Gate 1 satisfied if the map ships as MCP; Gate 3 contract tests for any MCP tool schema; fork-before-build evaluation of the three named Roslyn MCP candidates completed; **and a resolution for the template-shaped state model described below.** Exit criterion: SC-006 on a 20k-line solution, met rather than merely measured.

**Phase B blocker discovered during Phase A implementation** — `ProjectState` cannot represent a brownfield project. `state.py` requires `template_id` on creation and rejects any state file whose `template_id` is outside `TEMPLATE_IDS` on load; the architect stage and `context/bands.py` both lean on that locked template for their conventions. A solution the tool did not generate has no template, and US6-AS1 requires new code to *match the surrounding solution's conventions rather than impose the template* — the opposite of what the current model encodes. Phase B therefore needs a no-template, inferred-conventions mode across `state.py` and `bands.py`, designed rather than patched in. This is an entry condition, not an implementation detail, because it changes a data model that Phase A treats as immutable by design (FR-001c).

## Gate verification results

**Gate 4 - Reversibility (T070).** Verified 2026-08-19. The apply flow copies every
`global/skills/<name>/` directory, so `global/skills/dotnet-codegen/` deploys without further
change. `global/dotnetgen-bindings.toml` did **not** deploy: the script copies named top-level
files individually and had no clause for it, so on an installed (non-checkout) machine the
pipeline would have found no bindings at `~/.claude/dotnetgen-bindings.toml` and fallen back to a
repo path that does not exist there. A copy clause was added. Both assets install on apply and
leave nothing behind when deleted - they are a directory and a single file, with no registry entry,
no settings key, and no hook referencing them.

**Gate 5 - Minimal Skill & Agent Surface (T071).** Reviewed 2026-08-19 by reading every `.NET`
asset's frontmatter rather than by running `/review-conflicts`, and recorded as such. One new
skill, no new agent. No trigger overlap found:

| Asset | Scope | Overlap with `/dotnet-codegen` |
|---|---|---|
| `/dotnet-class` | Generates one type from a prompt | None - no verification loop, no ceiling, no cost record |
| `/dotnet-test` | Authors one integration test | None - does not scaffold or route |
| `@dotnet-architect` | Reasoning about design | None - has no execution surface, and defers architecture to each project's CLAUDE.md, which is the opposite of a locked template |
| `@dotnet-tester` | Test authoring and review | None |
| `/dependency-audit` | Mentions `dotnet list package --vulnerable` | None - vulnerability scanning, unrelated trigger |

The new skill's description is scoped to the pipeline's own verbs (scaffold a service, add a
feature to a generated solution, what a run cost, which model is bound) so it does not compete
with the reasoning agents for a general "help me design this .NET thing" request.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*
