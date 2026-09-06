# Feature Specification: Codegen & Eval Workspace Modules

**Feature Branch**: `021-codegen-eval-modules`  
**Created**: 2026-08-29  
**Status**: Draft  
**Input**: User description: "Two subsystems landed alongside the workspace. They run from the command line; these notes tell you where to look. [.NET code generation — CLI: python -m cabal.dotnetgen, or the /dotnet-codegen skill. Agent eval harness — CLI: python -m cabal.evals.] Figure out a proper GUI and views for them!"

## Context

Two subsystems ship complete and CLI-only. The workspace's own Release news screen files them under *"Shipped in this release, used outside the app"* — the app tells you the features exist and then tells you to leave the app to use them. This feature closes that gap by giving each one a first-class module in the workspace.

Neither subsystem's behaviour changes. Both already expose the seams a GUI needs — an approval gate expressed as a token-issuing plan step redeemed by a separate apply step, a per-run cost record on disk, a durable results tree per eval run — so this is a presentation and orchestration feature over existing capability, not new capability.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate .NET code and decide at the approval gate (Priority: P1)

Someone selects a project, describes in prose what they want built or changed, and starts the generation pipeline. The pipeline classifies the request and drafts an architecture plan, then **stops**. The person reads the plan — what files it intends to create or modify, what it intends to do to each — and either approves it or rejects it. Nothing reaches disk until they approve. On approval the pipeline writes the code and verifies it, and the outcome is reported as one of a small set of distinguishable end states: succeeded, rejected at the gate, halted at the retry ceiling, or blocked by a broken toolchain.

**Why this priority**: The approval gate is the whole safety story of the code generator, and it is the single thing a text-scrolling terminal presents worst. A plan worth approving is a structured document — a file list with intents — and it deserves to be read as one. Without this story the module has no reason to exist; with only this story it is already a complete, useful generator.

**Independent Test**: Select a project, submit a change request in prose, confirm the run pauses with a readable plan and writes nothing to the working tree, reject it, and confirm the working tree is still untouched. Then repeat and approve, and confirm the described files — and only those — were written.

**Acceptance Scenarios**:

1. **Given** a selected project and a prose change request, **When** the run reaches the architect stage, **Then** the run pauses and presents the proposed plan as a reviewable list of intended file changes, with an explicit approve control and an explicit reject control.
2. **Given** a paused run awaiting approval, **When** the user inspects the project's working tree, **Then** no file has been created or modified by the run.
3. **Given** a paused run awaiting approval, **When** the user rejects it, **Then** the run ends in a distinct "rejected" state, the working tree remains unmodified, and the rejection is recorded in the run history.
4. **Given** a paused run awaiting approval, **When** the user approves it, **Then** the write and verify stages proceed and the run's outcome is reported on completion.
5. **Given** a run whose verification fails because the toolchain itself is broken, **When** the outcome is presented, **Then** it is shown as an environment problem and visibly distinguished from a run that failed because the generated code was wrong.
6. **Given** a run that exhausted its repair attempts, **When** the outcome is presented, **Then** it is shown as having halted at the retry ceiling rather than as a generic failure.
7. **Given** a plan has been presented for approval, **When** the underlying project changes on disk before the user approves, **Then** approval is refused and the user is told the plan is stale rather than having it applied against changed content.

---

### User Story 2 - Read the A/B verdict for a completed eval run (Priority: P1)

Someone has run an eval and wants the answer to one question: did the candidate configuration beat the baseline? They open a finished run and see the comparison — how each configuration scored on the deterministic checks, what the pairwise judge concluded, and what each configuration cost in tool calls, tokens and wall time. Where the evidence is weak or contested, the view says so rather than presenting a clean winner.

**Why this priority**: This is the payload of the entire harness. Everything else the eval subsystem does exists to produce this comparison. It is also independently deliverable: run directories already exist on disk from CLI runs, so this view can be built and tested with no ability to launch a run at all.

**Independent Test**: Point the module at an existing completed run directory produced by the CLI and confirm the comparison renders — per-metric baseline vs candidate figures, the judge verdict, and an honest treatment of ties and errors — without launching anything.

**Acceptance Scenarios**:

1. **Given** a completed run with results for both configurations, **When** the comparison is opened, **Then** each metric is shown for baseline and candidate side by side, per task and aggregated across the matrix.
2. **Given** a metric aggregated from fewer than three samples, **When** it is displayed, **Then** no spread or standard deviation is claimed for it.
3. **Given** the judge disagreed with itself across the two A/B presentation orders, **When** the verdict is displayed, **Then** it is shown as a tie attributable to order disagreement, not as a win for either side.
4. **Given** some pairs produced judge errors, **When** the win rate is displayed, **Then** those pairs are excluded from the rate and the exclusion is visible, so the number is not read as covering more evidence than it does.
5. **Given** a run where some cells failed outright, **When** the aggregate is displayed, **Then** those failures are reflected in the task pass rate and excluded from quality averages, and both facts are legible.
6. **Given** a completed run, **When** the user drills into a single cell, **Then** they can see that cell's individual check outcomes and the agent's own metrics for it.

---

### User Story 3 - Launch and watch an eval matrix (Priority: P2)

Someone picks a baseline profile, a candidate profile, a subset of tasks and a repetition count, and starts the matrix. The workspace shows per-cell progress as it runs. The run continues whether or not they keep watching it, and they can navigate elsewhere in the app and come back.

**Why this priority**: Launching from the GUI removes the last reason to open a terminal, but the comparison view (User Story 2) already delivers value against CLI-produced runs, so this can follow it. A matrix run is long — potentially hours — which makes "you may leave and come back" a hard requirement rather than a nicety.

**Independent Test**: Launch a small matrix (one task, one repetition), navigate to a different module mid-run, return, and confirm the run is still progressing and its state is accurate.

**Acceptance Scenarios**:

1. **Given** a valid benchmark definition tree, **When** the user opens the launch view, **Then** the available config profiles and tasks are listed for selection.
2. **Given** a launched matrix, **When** cells complete, **Then** per-cell progress updates without the user reloading or re-entering the module.
3. **Given** a running matrix, **When** the user navigates to another module and returns, **Then** the run's live state is shown accurately and no progress was lost.
4. **Given** a running matrix, **When** the user closes and reopens the workspace, **Then** the run is still listed with its state, rather than disappearing.
5. **Given** a running matrix, **When** the user requests cancellation, **Then** the run stops, its partial results remain readable, and any temporary worktrees it created are cleaned up.
6. **Given** any launched run, **When** it executes, **Then** the workspace makes visible that the run used an isolated configuration directory and did not read or write the user's real agent configuration.

---

### User Story 4 - See what a generation run cost, stage by stage (Priority: P2)

After a run, someone opens its cost record and sees where the money went — which stage spent what, and how much of the total was initial generation versus repair attempts. The premise of the routed pipeline is that a cheap model does the cheap stages; this view is where that premise is confirmed or falsified.

**Why this priority**: Cost transparency is the claim the whole routing design rests on, and a single total figure cannot confirm or refute it. It depends on runs existing, so it follows User Story 1.

**Independent Test**: Open the cost view for a previously completed run and confirm every stage appears with its own spend, that repair spend is separated from initial spend, and that the figures reconcile against the run's recorded total.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** its cost record is opened, **Then** each pipeline stage is listed with its own spend, and a stage that did not run shows an explicit zero rather than being absent.
2. **Given** a run that made repair attempts, **When** cost is displayed, **Then** repair spend is presented separately from initial-generation spend rather than merged into one figure.
3. **Given** a stage that ran on a locally hosted model, **When** its cost is displayed, **Then** it shows as genuinely costing nothing, visibly distinct from a stage whose price is simply unknown.
4. **Given** a provider that does not report cache usage, **When** cost is displayed, **Then** no cache figure is shown for it rather than a fabricated or zero one.
5. **Given** a list of recent runs, **When** the user browses it, **Then** they can open any past run's cost record without needing its identifier.

---

### User Story 5 - Validate the benchmark definitions before spending on a run (Priority: P2)

Before launching anything, someone checks that the benchmark definition tree is well-formed. If it is not, the workspace shows what is wrong and where, precisely enough to go and fix it.

**Why this priority**: A matrix run is expensive in time and tokens. Discovering a malformed task definition after an hour of running is the worst possible time to discover it. Validation is cheap, fast, and gates the launch.

**Independent Test**: Introduce a deliberate error into a benchmark definition, run validation from the module, and confirm the reported location is specific enough to find and fix the error without further searching.

**Acceptance Scenarios**:

1. **Given** a well-formed definition tree, **When** validation runs, **Then** it reports success and summarises what was found — how many tasks, how many profiles.
2. **Given** a definition tree containing an error, **When** validation runs, **Then** each problem is reported with the file it occurred in and enough locating detail to fix it.
3. **Given** a definition tree that fails validation, **When** the user attempts to launch a matrix, **Then** the launch is prevented and the validation failures are shown as the reason.

---

### User Story 6 - Author a benchmark definition without leaving the workspace (Priority: P2)

Someone wants to add a task to the benchmark, adjust a rubric, or define a new config profile to test. They do it in the workspace: fill in the definition, see it validated as they go, and save. What lands on disk is an ordinary version-controlled file the command-line tool reads without knowing a GUI was involved.

**Why this priority**: Adding a task is the act that starts most eval work, and it is currently the one step that forces a context switch out of the app. It sits below the run and comparison stories because a benchmark can be authored by hand and still be run and read from the workspace — but above the P3 inspection views, because without it the module can only ever measure benchmarks someone else wrote.

**Independent Test**: Create a new task definition entirely in the workspace, save it, then run and validate it using the command-line tool with the workspace closed, and confirm the tool accepts it exactly as if it had been written by hand.

**Acceptance Scenarios**:

1. **Given** the definition tree, **When** the user creates a new task, rubric, or config profile in the module and saves it, **Then** it is written to the same on-disk location and format the command-line tool reads.
2. **Given** a definition being edited, **When** it would fail validation, **Then** saving is refused and the specific problem is reported.
3. **Given** a definition open for editing, **When** the same file changes on disk outside the workspace, **Then** the user is told before their edit can overwrite the external change.
4. **Given** a definition referenced by a stored run's results, **When** the user deletes it, **Then** that run's comparison remains readable against the definition it actually executed with.
5. **Given** definitions with uncommitted changes, **When** the user views the definition tree, **Then** those definitions are marked as not yet committed.
6. **Given** a definition authored in the workspace, **When** the command-line tool validates the tree with the workspace closed, **Then** it passes without modification.

---

### User Story 7 - Confirm which model each pipeline stage is bound to (Priority: P3)

Someone wants to check that the routing is configured the way they think it is: a cheap model doing classification and routing, an expensive one only doing architecture. They open a view that lists each stage and the provider and model currently bound to it.

**Why this priority**: This is a configuration inspection view, valuable for trust and debugging but not on the path to generating any code. It also answers "why did that run cost what it did" as a companion to User Story 4.

**Independent Test**: Open the stage-binding view and confirm every pipeline stage is listed with its bound provider and model, and that a locally hosted binding is identifiable as such.

**Acceptance Scenarios**:

1. **Given** the current configuration, **When** the bindings view is opened, **Then** every pipeline stage is listed with the provider and model bound to it.
2. **Given** a stage bound to a locally hosted model, **When** the bindings are displayed, **Then** that stage is identifiable as running locally.
3. **Given** a stage whose configured provider is unreachable or misconfigured, **When** the bindings are displayed, **Then** that stage is flagged rather than shown as healthy.

---

### User Story 8 - Come back to a run that was already in flight (Priority: P3)

Someone starts a long run, closes the workspace, and comes back later. Their runs are still there — finished ones browsable, unfinished ones identified as resumable — and an interrupted matrix can be picked up from where it stopped rather than restarted from zero.

**Why this priority**: This turns both modules from session-scoped tools into durable ones. It matters most for the eval harness, where a matrix can run for hours and restarting from zero is expensive enough to discourage using the feature at all.

**Independent Test**: Start a matrix, terminate the workspace mid-run, restart it, and confirm the run appears as interrupted-and-resumable, then resume it and confirm completed cells are not re-executed.

**Acceptance Scenarios**:

1. **Given** runs from previous sessions, **When** the user opens either module, **Then** the run history is listed with each run's outcome, most recent first.
2. **Given** a matrix interrupted mid-run, **When** the workspace restarts, **Then** the run is listed as interrupted and offers resumption.
3. **Given** an interrupted matrix is resumed, **When** it continues, **Then** already-completed cells are not re-executed.
4. **Given** a generation run interrupted while awaiting approval, **When** the workspace restarts, **Then** the pending plan is either still approvable or clearly marked as expired — never silently applied.

---

### Edge Cases

- **No project selected.** Both modules need a target; the generation module must state that plainly rather than offering a disabled form with no explanation.
- **Selected project is not a .NET project.** The generation module must say so before the user writes a request and spends a routing call finding out.
- **Benchmark definition tree absent entirely.** The eval module must distinguish "no benchmark defined here" from "benchmark is broken" — the first is a setup state with a next step, the second is an error.
- **A run is already in progress in the same module.** Starting a second concurrent run must be either prevented with a reason or supported explicitly; it must not silently interleave two runs' output.
- **The underlying CLI is missing, the wrong version, or its dependencies are unavailable.** The module must report the subsystem as unavailable with the reason, the same way other workspace modules report unavailability — not fail as though the user's request was invalid.
- **A run produces an enormous volume of output.** Streaming output must remain navigable and must not degrade the workspace as the run progresses.
- **A run's on-disk artifacts are partially written or corrupt.** Reading a malformed run record must produce a stated error about that run, not break the history list for every other run.
- **An eval leaves a temporary worktree behind after a crash.** Orphaned worktrees must be discoverable and removable from the workspace rather than silently accumulating.
- **The approval gate's plan references a file that no longer exists** by the time approval is granted.
- **Judge unavailable when reporting.** A comparison must still render its deterministic-check half rather than showing nothing.
- **A definition is edited in the workspace while a matrix using it is running.** The in-flight run must continue against the definition it started with; the edit must not retroactively change what a running or completed run measured.
- **A definition file is hand-written in a form the module's editor cannot represent** — an unusual but valid shape. Opening it must not silently discard the parts the editor does not model.
- **The definition tree is read-only on disk**, or the user lacks write permission. Authoring controls must report that rather than failing at save time.
- **New-service creation targets a path inside the project that is already tracked by git** with uncommitted changes.

## Requirements *(mandatory)*

### Functional Requirements

#### Both modules

- **FR-001**: The workspace MUST present the .NET code generation subsystem and the agent eval harness as first-class modules, reachable from the primary navigation alongside existing modules.
- **FR-002**: Each module MUST report the subsystem as unavailable — with the reason — when its underlying command-line tooling is missing or unusable, rather than presenting controls that cannot work.
- **FR-003**: Long-running operations MUST stream their progress into the workspace without blocking interaction with the rest of the application.
- **FR-004**: A user MUST be able to navigate away from a running operation and return to it with its state intact.
- **FR-005**: Run history MUST survive a workspace restart and remain browsable after the fact.
- **FR-006**: Every operation that changes state MUST be recorded in the workspace's audit trail, identifying what was run, against what, when, and with what outcome.
- **FR-007**: Neither module may alter the behaviour of the underlying command-line subsystems; where a needed capability is missing from a subsystem's interface, that gap MUST be recorded as a finding rather than worked around by reimplementing the behaviour in the module.
- **FR-008**: Where a subsystem reports a value as unknown, unpriced, or unreported, the module MUST display that distinction rather than substituting zero or a fabricated figure.

#### .NET code generation module

- **FR-010**: Users MUST be able to submit a generation request in prose against a selected project.
- **FR-011**: Users MUST be able to create a new service from one of the available locked architecture templates, and to request changes to an existing one.
- **FR-011a**: A new service MUST be created inside the currently selected project's directory. The module MUST NOT offer a free-roaming filesystem destination picker.
- **FR-011b**: Creating a new service MUST be refused when the chosen destination inside the project already exists and is non-empty, rather than writing into or over it.
- **FR-012**: The module MUST pause at the approval gate and present the proposed plan as a structured, reviewable list of intended file changes before anything is written.
- **FR-013**: The module MUST offer explicit approve and reject decisions at the gate, and MUST NOT proceed on timeout, navigation, or any implicit action.
- **FR-014**: No file in the target project may be created or modified before approval is granted.
- **FR-015**: Approval MUST be refused if the target project changed after the plan was produced, and the user MUST be told the plan is stale.
- **FR-016**: Run outcomes MUST be presented as distinguishable end states covering at least: succeeded, rejected at the gate, halted at the retry ceiling, and blocked by an environment problem.
- **FR-017**: A failed verification MUST be classified as either an environment problem or a genuine code defect, and the classification MUST be visible to the user.
- **FR-018**: The module MUST present per-run cost broken down by pipeline stage, with stages that did not run shown as explicit zeros.
- **FR-019**: Repair spend MUST be presented separately from initial-generation spend.
- **FR-020**: The module MUST present which provider and model each pipeline stage is currently bound to, and flag any binding that is unreachable or misconfigured.
- **FR-021**: Users MUST be able to browse recent runs and open any past run's plan, outcome, and cost record without knowing its identifier.

#### Agent eval harness module

- **FR-030**: Users MUST be able to validate the benchmark definition tree and see each problem with the file it occurred in and enough locating detail to fix it.
- **FR-031**: The module MUST prevent launching a matrix while the definition tree fails validation, and show the failures as the reason.
- **FR-032**: Users MUST be able to select a baseline profile, a candidate profile, a subset of tasks, and a repetition count, then launch the matrix.
- **FR-033**: The module MUST show per-cell progress while a matrix runs.
- **FR-034**: The module MUST make visible that each run executed against an isolated configuration directory and did not read or write the user's real agent configuration.
- **FR-035**: Users MUST be able to cancel a running matrix; partial results MUST remain readable and temporary worktrees MUST be cleaned up.
- **FR-036**: Interrupted runs MUST be identifiable as resumable and resumable without re-executing already-completed cells.
- **FR-037**: The module MUST present the A/B comparison for a completed run: deterministic check outcomes, the pairwise judge verdict, and agent metrics, for baseline and candidate, per task and aggregated.
- **FR-038**: Judge ties arising from disagreement across the two presentation orders MUST be presented as ties, never as a win for either configuration.
- **FR-039**: Pairs excluded from the pairwise win rate — ties and judge errors — MUST be visibly excluded, so the rate is not read as covering more evidence than it does.
- **FR-040**: Cells that failed outright MUST be reflected in the task pass rate and excluded from quality averages, with both facts legible in the view.
- **FR-041**: Spread MUST NOT be claimed for a metric aggregated from fewer than three samples.
- **FR-042**: Users MUST be able to drill from the aggregate into a single cell's individual check outcomes and agent metrics.
- **FR-043**: A comparison MUST render its deterministic-check half even when judge results are absent or unavailable.
- **FR-044**: Orphaned temporary worktrees left by crashed runs MUST be discoverable and removable from within the module.
- **FR-045**: The module MUST support browsing and comparing runs produced outside the workspace by the command-line tool, not only runs it launched itself.

#### Benchmark definition authoring

- **FR-050**: Users MUST be able to create, edit, and delete tasks, rubrics, and config profiles from within the module.
- **FR-051**: Definitions MUST be written back to the same on-disk, version-controlled files the command-line tool reads, in the same format, so that a definition authored in the workspace and one authored by hand are indistinguishable to the harness.
- **FR-052**: The module MUST validate a definition before saving it and MUST refuse to save one that would fail validation, reporting what is wrong.
- **FR-053**: A definition changed on disk outside the workspace while open for editing MUST be detected, and the user MUST be told rather than having their in-progress edit silently overwrite the external change.
- **FR-054**: Deleting a definition that a stored run's results refer to MUST NOT break that run's comparison view; the run MUST remain readable with the definition it actually executed against.
- **FR-055**: The module MUST show which definitions have uncommitted changes, since the benchmark tree is version-controlled and an uncommitted task definition is not yet a reproducible benchmark.

### Key Entities

- **Generation run**: One execution of the code generation pipeline against a project. Carries the originating request, the selected template, the stages executed, the gate decision, the end state, and the cost record. Durable and browsable after completion.
- **Plan (pending approval)**: The architecture stage's output — a set of intended file changes awaiting a decision. Redeemable exactly once, invalidated if the target project changes underneath it.
- **Stage cost**: One pipeline stage's spend within a run: the provider and model used, the volume consumed, whether it was priced at all, and whether it belonged to initial generation or to a repair attempt.
- **Stage binding**: The current mapping from a pipeline stage to the provider and model that serves it, plus whether that provider is locally hosted and whether it is reachable.
- **Benchmark definition tree**: The versioned set of tasks, rubrics, and configuration profiles that defines what an eval measures. Consumed by the module; its validity gates launching.
- **Config profile**: A named agent configuration used as either the baseline or the candidate side of a comparison. Materialised into an isolated directory per run.
- **Matrix run**: One execution of task × configuration × repetition. Has a state (running, complete, interrupted, cancelled), a durable results tree, and an identifier by which it can be resumed, judged, and reported.
- **Cell**: A single task run under a single configuration at a single repetition, executed in a throwaway worktree pinned to a commit. Carries its deterministic check outcomes and its agent metrics.
- **Comparison verdict**: The pairwise judge's conclusion for one baseline/candidate pair, including whether the two presentation orders agreed and whether the judgement errored.
- **Matrix report**: The reduction of a run's cells and verdicts into per-metric aggregates for each configuration, with the sample counts each aggregate rests on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can take a .NET change request from prose to approved, written, and verified code without leaving the workspace or opening a terminal.
- **SC-002**: A user can determine whether a candidate agent configuration beat its baseline, and on which metrics, without leaving the workspace or opening a terminal.
- **SC-003**: Zero files are written to a target project before the user approves a plan, verified by inspecting the working tree at the paused gate.
- **SC-004**: For any completed generation run, a user can identify which pipeline stage consumed the largest share of the run's cost within 30 seconds of opening the run.
- **SC-005**: For any failed verification, a user can tell whether the cause was a broken toolchain or a genuine code defect without reading raw log output.
- **SC-006**: A malformed benchmark definition is located precisely enough that a user can fix it on the first attempt, without additional searching.
- **SC-007**: A run in progress survives navigating away from its module and returning, and survives a workspace restart, with no loss of progress in either case.
- **SC-008**: An interrupted matrix resumes without re-executing any cell that had already completed.
- **SC-009**: Every metric presented in a comparison shows the number of samples it was computed from, and no aggregate claims a spread it does not have the samples to support.
- **SC-010**: Comparison figures rendered in the workspace match those produced by the command-line report for the same run, with no divergence in any aggregate.
- **SC-011**: No eval run reads or writes the user's real agent configuration, and the workspace shows the user that this held for the run they are looking at.
- **SC-012**: Both subsystems can be removed from the Release news screen's "used outside the app" section, because neither requires the command line for any of its primary workflows.
- **SC-013**: A benchmark task authored entirely in the workspace validates and runs under the command-line tool with no hand-editing, and a definition written by hand opens in the workspace editor without losing any of its content.
- **SC-014**: A new service can be scaffolded into the selected project without the user typing or browsing to a filesystem path outside that project.

## Assumptions

- **The underlying subsystems are complete and unchanged.** This feature wraps existing command-line capability. Where the workspace needs something a subsystem does not expose, the gap is recorded as a finding for that subsystem rather than reimplemented in the module.
- **The generation module targets the currently selected project**, consistent with how other project-scoped modules in the workspace behave. Greenfield service creation is in scope but stays inside that project's directory, so the module never needs a free-roaming filesystem picker.
- **Benchmark definitions remain files, not database rows.** The module is a second editor for the existing version-controlled tree, never an alternative store. Round-tripping is the correctness test: a definition authored in the workspace and one written by hand must be indistinguishable to the harness.
- **One run at a time per module.** Concurrent runs within a single module are out of scope for a first delivery; a second launch is refused with a reason while one is in flight. The two modules may run independently of each other.
- **The approval gate reuses the workspace's existing confirmation-guarded mutation pattern** — a prepared ticket carrying a precondition digest, redeemed by an explicit execute — rather than introducing a second, parallel approval mechanism. This is what makes FR-015 (stale plan refusal) fall out of existing behaviour instead of being built again.
- **Run artifacts stay where the subsystems already write them.** The modules read the existing on-disk run records and results trees; run output is not migrated into a new store. This is what makes FR-045 (reading CLI-produced runs) possible at no extra cost.
- **Cost figures are displayed, not enforced.** Budget ceilings and retry limits remain configuration owned by the generation subsystem; the module reports what was spent and shows when a ceiling was hit, but does not become a second place to set limits.
- **The eval harness's existing adapter seam is respected.** Adapter selection is exposed as a choice where the subsystem already offers it; no new adapters are added.
- **Judge and provider availability are external dependencies.** Both modules depend on services that can be unreachable; unavailability is a presented state, not a crash.
- **Users of these modules are the people who configure this machine's agent setup** — comfortable with the concepts of a baseline and a candidate configuration, and of an architecture template. The modules do not need to teach these concepts from zero, but must not assume familiarity with either subsystem's command-line flags.

## Out of Scope

- Changing the generation pipeline's stages, routing logic, or repair strategy.
- Changing the eval harness's methodology — task execution, check semantics, judging protocol, or aggregation rules.
- Adding new agent adapters, providers, or architecture templates.
- Any write access to the user's real agent configuration from within an eval run.
- Replacing either command-line interface; both remain fully supported and usable independently.
- Version control operations on the benchmark tree. The module shows which definitions are uncommitted (FR-055); committing them remains the user's own git workflow.
- Scaffolding a new service anywhere outside the currently selected project's directory.
