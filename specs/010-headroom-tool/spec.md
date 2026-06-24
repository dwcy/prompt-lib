# Feature Specification: Headroom as a Managed Tool

**Feature Branch**: `010-headroom-tool`
**Created**: 2026-06-21
**Status**: Draft
**Input**: User description: "Integrate Headroom (chopratejas/headroom, a context-compression layer for AI agents) into prompt-lib as a first-class managed tool inside the cabal TUI — installer + tool registry rows + MCP server template + an investigate-only research spike on the proxy/subscription-auth path + docs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install Headroom from the cabal Tools view (Priority: P1)

A maintainer opens the cabal TUI and wants Headroom available on their machine without leaving the wizard or remembering install commands. Headroom appears as a featured tool with its description, homepage, and current install status. One action installs (or upgrades) it; the status then reflects the installed version.

**Why this priority**: Without the tool installed there is nothing to register as an MCP server and nothing to investigate. This is the foundational slice and is independently useful — it makes Headroom discoverable and one-click installable like every other managed CLI.

**Independent Test**: Launch the cabal TUI, open the Tools view, confirm a Headroom row is present with description and status; trigger install; confirm the status flips to "installed" with a version and that `headroom --version` succeeds in a fresh shell.

**Acceptance Scenarios**:

1. **Given** Headroom is not installed, **When** the maintainer opens the cabal Tools view, **Then** a Headroom row is shown with status "not installed", a description of what it does, and links to its homepage and repository.
2. **Given** the Headroom row is shown, **When** the maintainer triggers install, **Then** Headroom is installed on the machine and the row updates to show "installed" with a version.
3. **Given** Headroom is already installed, **When** the maintainer triggers install again, **Then** the action upgrades it (or reports already-current) without error.
4. **Given** the underlying package manager prerequisite is missing, **When** the maintainer triggers install, **Then** the prerequisite is provisioned automatically or a clear, actionable message explains what to do.

---

### User Story 2 - Register Headroom as an opt-in MCP server (Priority: P2)

A maintainer who has installed Headroom wants to expose its compression tools to Claude Code. From the cabal MCP manager, Headroom is listed as an available server (not enabled by default), and a single action registers it for the current user so its tools appear in new Claude Code sessions.

**Why this priority**: This is the payload that makes Headroom usable from within Claude Code, but it depends on Story 1 (the tool must exist to be served). It is independently testable once Story 1 is done.

**Independent Test**: Open the cabal MCP manager, confirm Headroom is listed and shown as not-yet-enabled by default; register it; confirm it is reported as connected and that its compression / retrieval / stats tools are available in a new Claude Code session.

**Acceptance Scenarios**:

1. **Given** Headroom is defined as an available MCP server, **When** the maintainer views the MCP manager, **Then** Headroom appears in the list and is not enabled by default.
2. **Given** Headroom is installed, **When** the maintainer registers the Headroom MCP server, **Then** it is registered for the user scope and reported as connected.
3. **Given** the Headroom MCP server is registered, **When** the maintainer starts a new Claude Code session, **Then** the compression, retrieval, and stats tools are available and a round-trip (compress a large input, then retrieve the original) succeeds.

---

### User Story 3 - Know whether the transparent-proxy path is worth pursuing (Priority: P2)

A maintainer needs an evidence-based answer to "can Headroom transparently cut my interactive Claude Code token usage on my subscription login?" before any future work assumes the headline savings apply. A research spike investigates the proxy/wrap mode against subscription/OAuth auth and records a clear verdict.

**Why this priority**: It prevents wasted future effort and corrects the marketing claim for this specific setup. It is investigate-only — no shipped behavior depends on its outcome — so it is decoupled from Stories 1 and 2.

**Independent Test**: A findings document exists that states whether the proxy/wrap mode works on subscription auth, what risks exist, any measured savings, and a pursue / shelve / reject recommendation.

**Acceptance Scenarios**:

1. **Given** the maintainer reads the findings document, **When** they look for the proxy verdict, **Then** they find a clear pursue/shelve/reject recommendation with the reasoning and any measured evidence.
2. **Given** the proxy path is found not to apply on subscription auth, **When** future work is scoped, **Then** the document is explicit enough that no one re-assumes the headline savings apply here.

---

### Edge Cases

- The install prerequisite (package manager used to install Headroom) is absent → it is auto-provisioned, or a clear message tells the maintainer how to proceed.
- Headroom is registered as an MCP server but not actually installed → the manager surfaces the not-connected/failed state rather than silently appearing healthy.
- The maintainer is on a platform/shell where command wrapping differs → registration applies the same platform-appropriate wrapping the existing managed MCP servers use, so it works without manual editing.
- Adding Headroom to the registries must not break the existing Tools or MCP screens (no regression in rendering or other tools).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The cabal Tools view MUST list Headroom as a featured tool with a name, a description of what it does, its homepage, and its source repository.
- **FR-002**: The Tools view MUST report Headroom's current install state (not installed / installed with version).
- **FR-003**: The maintainer MUST be able to install Headroom from the cabal TUI in a single action, and the same action MUST upgrade it when already installed.
- **FR-004**: Installation MUST auto-provision its prerequisite when missing, or return a clear, actionable failure message when it cannot.
- **FR-005**: Headroom MUST also appear in the environment-tools listing grouped with the other AI command-line tools.
- **FR-006**: The cabal MCP manager MUST present Headroom as an available MCP server that is NOT enabled by default (opt-in).
- **FR-007**: The maintainer MUST be able to register the Headroom MCP server for the user scope from the cabal TUI, reusing the existing registration mechanism (including platform-appropriate command wrapping).
- **FR-008**: Once registered, Headroom's compression, retrieval, and statistics tools MUST be available to a new Claude Code session, and a compress→retrieve round-trip MUST succeed.
- **FR-009**: The feature MUST produce a research findings document that states whether the transparent proxy / wrap mode works with Claude Code subscription/OAuth authentication (no API key), notes risks and any measured savings, and gives a pursue/shelve/reject recommendation.
- **FR-010**: No shipped behavior in this feature may depend on the outcome of the proxy investigation (FR-009).
- **FR-011**: Documentation MUST describe the Headroom MCP server, its tools, the fact that compression is invoked on demand (not automatic), and its opt-in default.
- **FR-012**: Adding Headroom MUST NOT change the behavior or rendering of existing managed tools or MCP servers (no regression).
- **FR-013**: The feature MUST NOT introduce any always-on compression, auto-nudging behavior, or failure-mining behavior; those are explicitly deferred.

### Key Entities

- **Managed tool entry**: The catalog record that makes Headroom discoverable and installable in the Tools view — its display name, description, homepage, repository, install action, and status check.
- **Environment installer entry**: The grouped listing that places Headroom among the AI command-line tools with its install action.
- **MCP server template**: The reusable definition that lets the MCP manager present and register Headroom as a server, including how it is launched and whether it is enabled by default.
- **Research findings document**: The investigate-only deliverable recording the proxy/subscription-auth verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can go from "Headroom not present" to "Headroom installed" entirely within the cabal TUI in a single action, with no manual command entry.
- **SC-002**: After installation, the Tools view reflects the installed state (with version) on the next status refresh.
- **SC-003**: A maintainer can register the Headroom MCP server and, in a brand-new Claude Code session, successfully compress a large input and retrieve the original unchanged.
- **SC-004**: The Headroom MCP server is absent from sessions unless the maintainer explicitly registers it (opt-in verified).
- **SC-005**: The research findings document contains an unambiguous pursue/shelve/reject verdict on the proxy path for subscription auth.
- **SC-006**: All existing managed tools and MCP servers continue to render and operate exactly as before the change.

## Assumptions

- The target maintainer runs interactive Claude Code authenticated via a subscription/OAuth login (no Anthropic API key) on Windows; cross-platform behavior follows the patterns already used by the other managed tools.
- Headroom is installed via the same package-manager mechanism already used for other Python-based managed CLIs in cabal, with its prerequisite auto-provisioned when missing.
- The MCP server is registered through the existing MCP-template/registration machinery; no new registration subsystem is introduced.
- The exact launch invocation for the Headroom MCP server and the exact install/extra syntax are confirmed empirically during the Phase-0 spike before the template and installer are finalized.
- An automatic compression "nudge" (hook/skill) and the failure-mining capability are out of scope and will be evaluated in later, separate features.
- The investigation of the proxy/wrap path is exploratory only and may conclude that the path does not apply to this setup.
