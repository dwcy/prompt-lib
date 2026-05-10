# Plan — Feature Planning & Task Breakdown

Invoke before any non-trivial implementation task. Produces a reviewed task list and, for full-stack features, spawns parallel frontend and backend sub-agents working from an agreed API contract.

**Usage:** `/plan <description of the feature or task>`

---

## Step 1 — Classify the work

Determine what type of work `$ARGUMENTS` describes.

**Project setup** — scaffolding a new project, initialising a repo, configuring CI/CD, setting up environments, installing the base stack. This is infrastructure work and must never be mixed with feature implementation in the same planning session.

**Feature implementation** — adding or modifying functionality in an existing project.

If the description sounds like project setup, say:

> "This looks like project setup, not a feature. Setup should be its own task before feature work begins — mixing them makes both harder to reason about. Should I plan the setup separately first?"

Stop and wait for the user's decision. Do not proceed to a feature breakdown until setup is either complete or explicitly out of scope.

---

## Step 2 — Assess scope

Ask:

> "Is this a single focused feature, or does it span multiple features or user journeys?"

If the answer suggests multiple distinct features or the description cannot be summarised in one sentence, say:

> "This is large enough that I'd recommend planning each feature separately. Which one do you want to start with?"

Stop here. Do not produce a breakdown for a scope that is too large to ship as a unit. A feature that cannot be described in one sentence is probably two features.

---

## Step 3 — Discover the stack

Ask these three questions. Wait for all answers before continuing.

1. Does this touch the **frontend**? (yes / no / unsure)
2. Does this touch the **backend** or any APIs? (yes / no / unsure)
3. Are there **external services** involved? (e.g. auth provider, payments, storage, email) — list them or say none.

If the user says "unsure" for frontend or backend, ask: "What does the user see or do that triggers this feature?" — the answer will usually clarify it.

Set one of three modes based on the answers:
- **Frontend only** → proceed to Step 5 (single-track)
- **Backend only** → proceed to Step 5 (single-track)
- **Full-stack** → proceed to Step 4 (contract-first, dual-track)

---

## Step 4 — Define the API contract (full-stack only)

The contract is the single source of truth both tracks work from. It must be agreed before any tasks are written or any code is touched.

Work with the user to define each endpoint the feature requires:

1. **Method + path + purpose** — e.g. `POST /api/orders — create a new order`
2. **Request shape** — key fields and types (informal prose or a small JSON example)
3. **Response shape** — what the frontend receives on success, and the error format
4. **Auth** — is the endpoint protected? what role or scope is required?

Write the full contract as a single code block in the conversation. Then ask:

> "Does this contract look right? Once confirmed I'll use it to brief both agents — any change after this point will require both tracks to be updated."

Do not proceed until the user explicitly confirms the contract.

---

## Step 5 — Produce the task breakdown

Break the feature into discrete, independently deliverable tasks. Each task must be completable in a single focused session without leaving the system in a broken state.

Rules:
- Tasks are sequenced — earlier tasks must not depend on later ones
- For full-stack: backend tasks come first (they implement the contract), then frontend tasks (they consume it)
- Each task has three things: a **title**, a **one-sentence description of what is built**, and a **done condition** (the observable outcome that confirms it is complete)

Create each task using the `TaskCreate` tool.

Then present the numbered list to the user and ask:

> "Does this breakdown look right? Should any tasks be merged, split, or reordered?"

Revise the list until the user approves it. Do not spawn agents or begin implementation before approval.

---

## Step 6 — Execute

### Single-track (frontend only or backend only)

Report the approved task list and stop. Implementation happens in the main session. Say:

> "Plan approved. Start with Task 1 when ready."

### Full-stack

Detect the backend and frontend stacks by reading project files (e.g. `*.csproj`, `pyproject.toml`, `package.json`, framework config).

Spawn two agents in parallel:

**Backend agent**

- Use `subagent_type: dotnet-architect` for .NET projects, `subagent_type: python-architect` for Python projects, or `subagent_type: general-purpose` if the stack is unclear.
- Brief with:
  - The confirmed contract (copy it verbatim)
  - The backend tasks from the approved breakdown
  - The detected backend stack
  - This instruction: *"Implement the contract exactly as defined. If you discover the contract needs to change, stop and report the conflict — do not silently deviate."*

**Frontend agent**

- Use `subagent_type: frontend-architect`.
- Brief with:
  - The confirmed contract (copy it verbatim)
  - The frontend tasks from the approved breakdown
  - The detected frontend stack (framework, state management, component library if present)
  - This instruction: *"Implement against the contract. If the contract is ambiguous or appears wrong, stop and report it — do not invent your own endpoint shapes."*

Set `run_in_background: true` on the backend agent so both run in parallel. Seed the frontend agent with a note that the backend is implementing the same contract simultaneously.

---

## Step 7 — Report

After agents complete (or for single-track, immediately after the plan is approved):

- List the tasks that were created with their IDs
- Note any risks or open questions surfaced during planning
- For full-stack: summarise what each agent was asked to build
- Ask: "Should I write an ADR for any architectural decision made during this planning session?"
