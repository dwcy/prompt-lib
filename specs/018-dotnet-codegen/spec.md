# Feature Specification: dotnet-codegen — fast, cheap C# backend generation

**Feature Branch**: `018-dotnet-codegen`
**Created**: 2026-08-14
**Status**: Draft
**Input**: Apply the cost-engineering principles proven by Aider, Cursor, Lovable and Bolt to .NET/C# backend generation. Greenfield first, brownfield second. Pluggable model providers including local models. Delivery form (skill vs. MCP server vs. standalone CLI) deliberately left open for the planning phase to resolve.

## Why this exists

Generating C# backend code with an LLM today is slow and expensive for four measurable reasons, not one:

| Cost centre | How it is wasted today |
|---|---|
| **Output tokens** (~5× input price, serial, sets latency) | The model re-emits unchanged code it was already shown |
| **Input tokens** (cheap, cacheable — so waste is optional) | Whole files are read speculatively; context is ordered so the cache self-destructs every turn |
| **Round trips** (each re-runs inference over the full context) | Sequential single-file reads; no intent routing, so questions cost as much as changes |
| **Retries** (full cost, zero progress) | Edits that fail to apply; builds that break; unbounded repair loops |

The "vibe coding" tools solved this for React. Nobody has applied it to a strongly-typed compiled backend — where the feedback signal is **strictly better** than a browser console, because a compiler names the exact symbol, file and line that broke, deterministically and for free.

This feature is the design and delivery of that pipeline for .NET.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stand up a new backend service without bootstrapping (Priority: P1)

The developer describes a service in one sentence ("an order service with CRUD over orders and a status webhook") and picks a template from a short closed list. The tool proposes what it will build, the developer approves, and it then produces a complete, building, test-passing, runnable .NET solution unattended — without improvising a folder layout and without generating a solution from an empty directory one file at a time. The template choice is made once and is locked for that project's lifetime.

**Why this priority**: This is the scope-deletion principle (Principle E), the single largest cost lever and the one that requires no new machinery beyond a template set and a locked convention set. It is also the path the developer asked to build first. It delivers standalone value even if nothing else in this spec ships.

**Independent Test**: Give the tool a one-sentence service description on a machine with only the .NET SDK installed. Measure wall-clock to first green build, wall-clock to a service answering a health request, and total tokens consumed. Compare against generating the same service in an unassisted session.

**Acceptance Scenarios**:

1. **Given** an empty directory, a one-sentence service description, and a chosen template, **When** the developer approves the proposed plan, **Then** a solution exists that compiles, passes its generated tests, and serves a health endpoint — with no further questions asked during the run.
2. **Given** a request that contradicts the chosen template ("use a different data access library"), **When** the tool processes it, **Then** it states the locked choice and its reason and proceeds with the template, rather than silently redesigning the solution.
3. **Given** the same description and template run twice, **When** both runs complete, **Then** the produced project structure is materially the same — the template determines layout, not per-run model improvisation.
4. **Given** an existing project whose template was chosen at creation, **When** any later run touches it, **Then** the template is read from the project rather than re-decided, and no architecture reasoning is performed.

---

### User Story 2 - Add a feature to an existing solution without re-reading it (Priority: P2)

The developer asks for a change to a solution the tool already knows ("add a cancel endpoint"). The tool locates the affected types from a compact structural map rather than reading files speculatively, edits only what changes, and never re-emits untouched code.

**Why this priority**: This is where the per-turn cost actually accumulates. A greenfield scaffold is a one-off; feature edits happen hundreds of times. Depends on P1 existing (or on a real solution to point at), which is why it is second.

**Independent Test**: Point the tool at a solution of known size, request a feature touching 2–4 types, and measure tokens consumed, the proportion of the codebase sent to the model, and how many proposed edits applied cleanly on first attempt.

**Acceptance Scenarios**:

1. **Given** a solution larger than fits in context, **When** the developer requests a change, **Then** the tool identifies the correct target types without any full-solution read.
2. **Given** a change confined to one method, **When** the tool writes the edit, **Then** unchanged members of that file are not re-emitted as output.
3. **Given** a proposed edit whose anchor text has drifted (whitespace, formatting, an intervening edit), **When** the edit is applied, **Then** it still applies rather than failing and costing a repair turn.
4. **Given** the developer asks a question rather than requesting a change ("what does this handler do?"), **When** the tool responds, **Then** it answers without entering the change pipeline.

---

### User Story 3 - A repair loop that provably cannot run away (Priority: P3)

When the build or tests fail, the tool feeds the failure back and repairs itself — but under a hard, visible budget. When the budget is exhausted it stops, reports what it tried, and hands back to the developer rather than continuing to spend.

**Why this priority**: This is the documented failure mode of the frontend tools — users report paying full price for the tool to fix its own breakage. A self-healing loop with no ceiling is a cost amplifier, not a cost saving. Without this, P1 and P2 are unsafe to run unattended.

**Independent Test**: Inject a deliberate compile error and a deliberate test failure. Confirm each is repaired within budget. Then inject a failure the tool cannot fix (e.g. a missing external dependency) and confirm it aborts cleanly at the budget ceiling with a useful report and no further spend.

**Acceptance Scenarios**:

1. **Given** a change that fails to compile, **When** verification runs, **Then** the failure detail is routed back to the writing step — not to the reasoning step — and repaired without re-deciding the design.
2. **Given** repeated failures, **When** the retry budget is reached, **Then** the run halts, reports every attempt and the remaining error, and leaves the working tree in a state the developer can inspect.
3. **Given** a failure caused by the environment rather than the code (missing SDK, restore failure, no network), **When** it is detected, **Then** the tool distinguishes it from a code defect and does not spend repair attempts on it.
4. **Given** any completed run, **When** the developer reviews it, **Then** the number of repair attempts consumed is visible.

---

### User Story 4 - Choose which model does which job, including local ones (Priority: P4)

The developer binds each pipeline stage to a provider and model independently — a strong hosted model for reasoning, a cheap or locally-hosted model for the mechanical writing step — and can change those bindings without altering the pipeline.

**Why this priority**: This is where the cost curve actually bends, and the developer named it explicitly. It is P4 rather than P1 because the pipeline must exist and be measurable before routing choices can be evaluated — you cannot demonstrate that a cheaper writer is good enough until you can measure build-green rate.

**Independent Test**: Run an identical feature request under at least three stage-binding configurations (all-hosted-strong; strong reasoner + cheap hosted writer; strong reasoner + local writer). Compare cost, wall-clock, and first-attempt build-green rate across the three.

**Acceptance Scenarios**:

1. **Given** a configuration binding the reasoning and writing stages to different providers, **When** a change runs, **Then** each stage uses its bound model and the run completes normally.
2. **Given** a locally-hosted model bound to the writing stage, **When** a change runs, **Then** no per-token cost is incurred for that stage.
3. **Given** a bound provider is unavailable or rate-limited mid-run, **When** the stage executes, **Then** the tool reports the failure clearly and, if a fallback is configured, uses it — rather than failing the whole run silently.
4. **Given** a new provider the developer wants to use, **When** they add it, **Then** no change to the pipeline stages themselves is required.

---

### User Story 5 - See exactly what a run cost (Priority: P5)

After any run, the developer can see tokens spent split by stage, how much context was served from cache, how many edits applied first time, how many repair attempts were consumed, and total wall-clock.

**Why this priority**: Every success criterion in this spec is stated in these terms. Without this the feature cannot be evaluated, tuned, or defended — but it is P5 because it measures the other stories rather than delivering the outcome itself.

**Independent Test**: Run one greenfield scaffold and one feature edit; confirm the report accounts for all four cost centres and that the numbers reconcile against the provider's own reported usage.

**Acceptance Scenarios**:

1. **Given** any completed run, **When** the developer inspects the run record, **Then** tokens are broken down by pipeline stage.
2. **Given** a sequence of runs against one solution, **When** the developer inspects them, **Then** the proportion of context served from cache is reported per run and is comparable across runs.
3. **Given** a run that consumed repair attempts, **When** it is inspected, **Then** the cost of repair is attributable separately from the cost of the original attempt.

---

### User Story 6 - Work inside a large existing solution (Priority: P6)

The developer points the tool at an established .NET solution it did not generate, and adds features to it with the same cost profile as P2.

**Why this priority**: Explicitly deferred behind greenfield by the developer. It is the harder problem — no locked template to lean on, existing conventions to infer and respect — and it is the case where the structural map matters most.

**Independent Test**: Point the tool at a real multi-project solution, request a feature, and compare cost and correctness against the same request made in an unassisted session.

**Acceptance Scenarios**:

1. **Given** a solution whose conventions differ from the locked template, **When** a feature is added, **Then** the new code matches the surrounding solution's conventions rather than imposing the template.
2. **Given** a solution too large to map within the context budget, **When** the map is built, **Then** the most relevant parts are retained and the developer is told what was omitted rather than silently truncated.

### Edge Cases

- A requested change conflicts with a locked convention (architecture, file-size cap, Command/Query separation). Does it refuse, negotiate, or comply?
- A file grows past the size where rewriting it whole is affordable, or past the size where a writing model stays reliable.
- The developer edits files by hand while a run is in progress, invalidating the structural map and the edit anchors.
- The structural map is stale because the solution changed since it was built.
- A change requires configuration or secrets. The tool must never write `.env` files (standing global rule) and must instead emit copy-paste instructions.
- Generated code compiles but the generated tests are vacuous — passing without asserting anything meaningful.
- A locally-hosted model produces malformed edit output repeatedly, exhausting the retry budget on formatting rather than logic.
- The request is ambiguous enough that any assumption would produce the wrong service; the tool must ask rather than guess.
- Two pipeline stages disagree — the writing step cannot express what the reasoning step asked for.
- A solution uses a language or project type outside the supported set.

## Requirements *(mandatory)*

### Functional Requirements

**Scope locking (attacks: retries, output tokens)**

- **FR-001**: The greenfield path MUST generate from one of a small closed set of architecture templates, not from per-run architectural improvisation. The set MUST be small enough that every member is maintained and tested.
- **FR-001a**: The template MUST be chosen once, at project creation, and MUST then be recorded in the project and treated as locked for that project's lifetime.
- **FR-001b**: Once a project's template is recorded, subsequent runs MUST read it rather than re-deciding it, and MUST perform no architecture reasoning.
- **FR-001c**: Changing a project's template after creation is out of scope; the tool MUST refuse rather than attempt a migration.
- **FR-002**: The tool MUST state and hold its locked conventions rather than silently accepting a conflicting instruction; where a conflict exists it MUST surface it explicitly.
- **FR-003**: The greenfield path MUST begin from a pre-existing runnable project skeleton, so that the first model turn edits a working solution rather than creating one.
- **FR-004**: Conventions already established in this repository's C# rules — one type per file, the file-size soft/hard caps, Command/Query separation, domain layer with zero external dependencies — MUST be enforced by the pipeline as cost controls, not merely stated as style preferences.

**Context assembly (attacks: input tokens, round trips)**

- **FR-005**: The tool MUST be able to represent a solution's structure — types, members, signatures and their relationships — without sending the bodies of those members.
- **FR-006**: That structural representation MUST be constrained to a configurable token budget, and when the solution exceeds it, MUST retain the most-referenced parts and report what was omitted.
- **FR-007**: The tool MUST NOT re-read content it has already been given within a run.
- **FR-008**: Context MUST be ordered from least-volatile to most-volatile so that a cacheable prefix is preserved across turns.
- **FR-009**: The tool MUST locate code by targeted search and read bounded ranges, rather than reading whole files to find something.

**Intent routing (attacks: round trips)**

- **FR-010**: The tool MUST distinguish a question from a change request and MUST NOT enter the change pipeline for a question.

**Approval gate (attacks: retries, output tokens)**

- **FR-010a**: Every change run MUST pause after the reasoning step and present the proposed change intent to the developer for approval before any code is written.
- **FR-010b**: The intent presented MUST be readable prose naming the files and types to be touched and why — not code, and not a diff.
- **FR-010c**: On rejection or amendment, the run MUST return to the reasoning step without having spent any tokens on writing code.
- **FR-010d**: After approval, the run MUST proceed unattended through writing, verification, and repair up to the retry ceiling, without further interruption.
- **FR-010e**: The gate applies uniformly to the greenfield and feature-edit paths.

**Reasoning / writing separation (attacks: output tokens, retries)**

- **FR-011**: Deciding *what* to change and expressing *how* it is written MUST be separate steps, each independently bindable to a model.
- **FR-012**: The reasoning step MUST NOT be required to emit syntactically valid edits, and the writing step MUST NOT re-decide the design.
- **FR-013**: The writing step MUST NOT be required to reason about correctness beyond faithfully expressing the stated intent.

**Edit expression and application (attacks: retries)**

- **FR-014**: Edits MUST NOT rely on line numbers.
- **FR-015**: Edits MUST be expressed at the granularity of whole coherent units (a complete member or type) rather than interleaved individual changed lines.
- **FR-016**: Edit application MUST be tolerant of common formatting drift — whitespace, indentation, and minor anchor mismatch — and MUST attempt progressively looser matching before declaring failure.
- **FR-017**: The tool MUST NOT re-emit unchanged code as output when a targeted edit is possible.
- **FR-018**: Every edit that fails to apply MUST be recorded, because failed application is a measured cost, not an invisible retry.

**Verification loop (attacks: retries)**

- **FR-019**: Every change MUST be verified by compiling and by running the tests affected by it, before the run is reported as complete.
- **FR-020**: Verification failures MUST be routed back to the writing step, not to the reasoning step, unless the failure indicates the intent itself was wrong.
- **FR-021**: The repair loop MUST have a hard, configurable attempt ceiling, and MUST halt and report when it is reached.
- **FR-022**: The tool MUST distinguish environment/toolchain failures from code defects and MUST NOT consume repair attempts on the former.
- **FR-023**: On abort, the working tree MUST be left in a state the developer can inspect, with every attempt reported.

**Provider abstraction**

- **FR-024**: Each pipeline stage MUST be independently bindable to a model provider and model.
- **FR-025**: The tool MUST support hosted providers and locally-hosted models through the same binding mechanism.
- **FR-026**: Adding a provider MUST NOT require changes to the pipeline stages.
- **FR-027**: Provider failure or unavailability MUST be surfaced clearly and MUST support a configured fallback.

**Measurement**

- **FR-028**: Every run MUST produce a record accounting for tokens by stage, cached-context proportion, first-attempt edit success rate, repair attempts consumed, and wall-clock.
- **FR-029**: Repair cost MUST be attributable separately from initial-attempt cost.

**Extensibility**

- **FR-030**: Language-specific concerns — how structure is extracted, how code is verified — MUST be separable from the language-agnostic pipeline, so that a second language can be added without redesigning the pipeline.
- **FR-031**: Only .NET/C# is in scope for this feature. Python and frontend targets MUST NOT be built here.

**Integration**

- **FR-032**: The feature MUST coexist with the existing `@dotnet-architect` agent, `@dotnet-tester` agent, and `/dotnet-class` and `/dotnet-test` commands. It MUST NOT modify, retire, or thin any of them.
- **FR-032a**: The existing C# rules (`global/rules/csharp.md`, `global/rules/_size-discipline.md`) MUST be consumed as-is and MUST NOT be rewritten by this feature.
- **FR-032b**: Consolidating the two overlapping paths is explicitly a follow-up feature, to be decided from real usage data rather than up front.
- **FR-033**: The tool MUST NOT write `.env` or any environment file; where configuration values are needed it MUST emit copy-paste instructions instead.

### Key Entities

- **Architecture Template**: The locked, pre-decided project shape a greenfield service is generated from — layout, layering, and the conventions that go with it. Chosen once, not per run.
- **Project Skeleton**: A pre-existing runnable solution the greenfield path starts from, so no run begins from an empty directory.
- **Structural Map**: A compact, ranked, budget-bounded representation of a solution's types and their relationships, without member bodies. The thing sent instead of source.
- **Change Intent**: The output of the reasoning step — what should change and why, in prose, containing no code.
- **Edit Operation**: A single proposed modification to one file, anchored by content rather than position, expressed at whole-member granularity.
- **Verification Result**: The outcome of compiling and testing a change — pass, code defect, or environment failure — with the diagnostics that justify the classification.
- **Retry Budget**: The hard ceiling on repair attempts for a run, and the count consumed against it.
- **Stage Binding**: The mapping from a pipeline stage to the provider and model that executes it.
- **Run Record**: The per-run accounting of all four cost centres.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer describes a new backend service in one sentence, picks a template, and approves one proposed plan — and has the service compiling, passing tests, and answering requests in under 10 minutes of wall-clock, with no further input required after approval.
- **SC-002**: Delivering an equivalent feature costs no more than 40% of the tokens consumed by an unassisted single-model session performing the same task on the same solution.
- **SC-003**: At least 90% of proposed edits apply successfully on the first attempt.
- **SC-004**: At least 70% of changes compile successfully on the first attempt, before any repair attempt is consumed.
- **SC-005**: Across a sequence of five or more consecutive runs against one solution, at least 70% of served context is drawn from cache.
- **SC-006**: For a solution of at least 20,000 lines, the structure supplied to the model before any file is opened is under 2% of the size of the solution's source.
- **SC-007**: No run exceeds its configured repair-attempt ceiling; every run that reaches it halts and reports rather than continuing to spend.
- **SC-008**: Binding the writing stage to a locally-hosted model reduces the run's per-token cost by at least 50% while keeping first-attempt build-green rate within 10 percentage points of the all-hosted configuration.
- **SC-009**: A question receives an answer without any file being written and without the change pipeline running.
- **SC-010**: Every completed run produces a cost record that reconciles with the provider's own reported usage to within 5%.
- **SC-011**: No run writes code before the developer has approved its stated intent, and a rejected plan costs less than 10% of a completed run.
- **SC-012**: Adding a new project with an existing template consumes no tokens on architecture reasoning — measurably zero for that stage.

## Assumptions

- **Audience is a single developer on this machine.** This is personal tooling in the spirit of the rest of this repository, not a shared or multi-tenant product. No authentication, quotas, or team features.
- **The .NET SDK is present and working.** The tool detects and reports toolchain problems but does not install or manage SDKs.
- **The cost baseline for SC-002 is an unassisted Claude Code session** performing the same task on the same solution, measured once and held as the reference.
- **"Local model" means an OpenAI-compatible endpoint served locally** (Ollama, LM Studio, or equivalent). No model fine-tuning is in scope — the speed gains available from a purpose-trained apply model are noted as prior art but not reproduced here.
- **Full offline operation is a goal, not a hard requirement.** Every stage must be bindable to a local model, but the tool is not required to produce equivalent quality with all stages local.
- **Generated tests are real tests.** The verification step's value depends on them; vacuous passing tests are treated as a defect, not a success.
- **Existing repository conventions are inputs, not open questions.** The C# rules file and size-discipline rules are taken as given and enforced.
- **Which templates make up the closed set is a planning decision.** The spec fixes that the set is small, closed, and per-project-locked; naming its members (and how many) belongs to `/speckit-plan`, informed by what `@dotnet-architect` already covers.
- **The approval gate is a pause, not a conversation.** One approve/amend/reject decision per run is assumed; an extended back-and-forth at the gate is not designed for.
- **Overlap with the existing .NET assets is accepted for now.** Two ways to generate C# will coexist until real usage shows which wins; that consolidation is a separate future feature.
- **Brownfield support (P6) may be descoped** to a follow-up feature if the greenfield path alone justifies the delivery form chosen in planning.
- **The delivery form is deliberately unresolved.** Whether this ships as prompt-only assets, a semantic-analysis service plus a driving skill, a standalone agent, or a hybrid is the primary question `/speckit-plan` must answer, with the tradeoffs costed against these success criteria.

## Dependencies

- The .NET SDK and its build/test tooling, as the verification signal.
- A semantic or syntactic source of C# structure for the structural map. Existing open-source prior art (Roslyn-based analysis servers) is to be evaluated for reuse before anything equivalent is built.
- At least one model provider; local-model support additionally depends on a locally-running compatible server.
- Existing repository assets: `global/rules/csharp.md`, `global/rules/_size-discipline.md`, `global/agents/dotnet-architect.md`, `global/agents/dotnet-tester.md`, and the `/dotnet-class` and `/dotnet-test` commands.

## Out of Scope

- Python and frontend targets. The pipeline must not preclude them; this feature must not build them.
- Training or fine-tuning any model.
- Deployment, hosting, or infrastructure provisioning for generated services.
- Editor or IDE integration.
- Multi-developer or shared-service operation.
