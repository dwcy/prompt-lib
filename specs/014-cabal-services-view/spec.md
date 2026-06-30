# Feature Specification: Local Agent Services in the Cabal UI

**Feature Branch**: `014-cabal-services-view`
**Created**: 2026-06-30
**Status**: Draft
**Input**: User description: "Surface the three local agent services (orchestrator, a2a-bridge, mcp-bus) as first-class apps in the cabal TUI so a maintainer can see and run them from the wizard instead of remembering CLI commands."

> **Update 2026-06-30 (supersedes parts of FR-001/FR-011 below)**: mcp-bus is **no longer shown in the Local Agent Services view** — it is already surfaced in the Tools **MCP** group, so duplicating it here was redundant. Only the two runnable services (orchestrator, a2a-bridge) appear in this view. References to mcp-bus in the requirements below are retained as original-design record; the `info-only` status machinery remains in the code as a general capability but no service currently uses it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the local agent services in one place (Priority: P1)

A maintainer opens the cabal TUI and wants to know, at a glance, which local agent services exist on this machine, what each one does, the command that runs it, what it depends on, and whether it is currently set up and/or running — without grepping the repo or remembering CLI invocations. The three services (orchestrator, a2a-bridge, mcp-bus) appear together as a recognizable group, each with a description, its run command, its source link, and a live status.

**Why this priority**: Discoverability is the foundational, independently useful slice. Even with no start/stop controls, a maintainer who can see the three services, what they do, and their current state has already replaced "remember the commands." Every later story (run, prepare, open dashboard) depends on this presentation existing.

**Independent Test**: Launch the cabal TUI, navigate to the services presentation, and confirm all three services are listed together, each showing its name, a description of what it does, its run command, its source link, and a current status, without launching anything.

**Acceptance Scenarios**:

1. **Given** the cabal TUI is open, **When** the maintainer navigates to the services presentation, **Then** orchestrator, a2a-bridge, and mcp-bus are shown together as a group, each with a name, a one-line description of what it does, its run command, and a link to its source.
2. **Given** a service is set up on the machine, **When** the services presentation is shown, **Then** that service's status reflects that it is ready (and, where applicable, whether it is currently running).
3. **Given** a service is not set up on the machine, **When** the services presentation is shown, **Then** that service's status reflects "not set up" rather than appearing healthy.
4. **Given** orchestrator depends on a2a-bridge, **When** the services presentation is shown, **Then** that dependency relationship is visible to the maintainer.

---

### User Story 2 - Start and stop a runnable service from the wizard (Priority: P2)

A maintainer who has the orchestrator or a2a-bridge set up wants to start it from inside cabal and later stop it, instead of opening a separate terminal and typing the serve command with its arguments and environment. Starting the service reflects a "running" status; stopping it returns the status to "stopped". When a service cannot start because a prerequisite is missing (auth, token, peer, or configuration), cabal surfaces a clear, actionable message instead of a silent failure.

**Why this priority**: This is the "run them from the wizard" payload the maintainer asked for. It depends on Story 1 (the services must be presented to be controllable) and is independently testable once Story 1 exists. mcp-bus is excluded from start/stop here because it is a message-bus server launched on demand by its clients, not a standalone daemon (see Story 3 and Assumptions).

**Independent Test**: From the services presentation, start a2a-bridge (or orchestrator); confirm the status flips to "running"; stop it; confirm the status returns to "stopped". Separately, attempt to start a service with a known-missing prerequisite and confirm a clear actionable message appears.

**Acceptance Scenarios**:

1. **Given** a runnable service is set up and stopped, **When** the maintainer triggers start, **Then** the service starts and its status updates to "running".
2. **Given** a runnable service is running, **When** the maintainer triggers stop, **Then** the service stops and its status updates to "stopped".
3. **Given** a runnable service requires a prerequisite that is missing (for example, an auth login, a required token, a reachable peer, or required configuration), **When** the maintainer triggers start, **Then** cabal does not start the service and shows a clear, actionable message explaining what is missing and how to resolve it.
4. **Given** orchestrator requires a2a-bridge to be reachable, **When** the maintainer starts orchestrator while a2a-bridge is not running, **Then** the dependency is reflected in the status or message so the maintainer knows to start a2a-bridge first.
5. **Given** the maintainer started a service from cabal during this session, **When** the maintainer leaves the services presentation and returns, **Then** the running/stopped status it shows is consistent with the service's actual state.

---

### User Story 3 - Prepare a service and reach its native view (Priority: P3)

A maintainer wants to get a not-yet-set-up service ready from inside cabal (so it can then be run), and, for a service that has its own dashboard or logs, reach that view without leaving the wizard. The orchestrator ships its own live dashboard; a service's recent activity or log location is surfaced so the maintainer can observe what it is doing.

**Why this priority**: Setup and observability round out the lifecycle but are not required to demonstrate the core value (see + run). They depend on Stories 1 and 2 and are independently testable.

**Independent Test**: From the services presentation, prepare a service that is not yet set up and confirm its status moves to "ready". Separately, for the service that has a native dashboard, trigger "open dashboard" and confirm its dashboard is reachable, or that a clear pointer to its logs/recent activity is shown.

**Acceptance Scenarios**:

1. **Given** a service is not set up, **When** the maintainer triggers prepare/setup, **Then** the service's dependencies are provisioned (or a clear, actionable message explains what is needed) and the status moves to "ready".
2. **Given** a service has its own dashboard, **When** the maintainer triggers "open dashboard", **Then** that dashboard is launched or reachable from cabal.
3. **Given** a service exposes recent activity or a log, **When** the maintainer asks to view it, **Then** cabal surfaces the recent activity or a clear pointer to where it can be observed.

---

### Edge Cases

- A service's run command needs arguments or environment that are not present (for example, a2a-bridge requires a bearer token and an agent target; orchestrator requires auth, a notification endpoint, and a reachable peer) → cabal surfaces the missing prerequisite with an actionable message rather than starting and crashing.
- A maintainer starts orchestrator before a2a-bridge → the unmet dependency is reflected so the maintainer knows the correct order.
- mcp-bus is a client-launched message-bus server, not a standalone daemon → it is presented for visibility and its availability/registration state is shown, but it is not given a standalone start/stop control that would conflict with how it is actually launched.
- A service appears "running" but has actually exited (crashed or was killed outside cabal) → the status reconciles to the true state on the next refresh rather than reporting a stale "running".
- A maintainer stops cabal while a service it started is still running → the boundary of cabal's responsibility for that process is defined (see Assumptions) and not left ambiguous to the maintainer.
- Adding the services presentation must not change the rendering or behavior of the existing Tools or MCP screens (no regression), including mcp-bus's existing place in the MCP group.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The cabal TUI MUST present orchestrator, a2a-bridge, and mcp-bus together as a recognizable group of local agent services.
- **FR-002**: For each service, the presentation MUST show a name, a one-line description of what it does, the command used to run it, and a link to its source.
- **FR-003**: For each service, the presentation MUST show a current status that distinguishes at least "not set up", "ready/stopped", and (for runnable services) "running".
- **FR-004**: The presentation MUST make visible that orchestrator depends on a2a-bridge.
- **FR-005**: A maintainer MUST be able to start a runnable service (orchestrator, a2a-bridge) from the cabal TUI, after which its status reflects "running".
- **FR-006**: A maintainer MUST be able to stop a service that cabal started, after which its status reflects "stopped".
- **FR-007**: When a runnable service cannot start because a prerequisite is missing (auth, required token, required configuration, or an unreachable dependency), cabal MUST refuse to start it and present a clear, actionable message describing what is missing.
- **FR-008**: The running/stopped status MUST reconcile to the service's actual state on refresh, so a service that has exited is not reported as still running.
- **FR-009**: A maintainer MUST be able to prepare/set up a service that is not yet set up from the cabal TUI, or receive a clear, actionable message when it cannot be prepared automatically.
- **FR-010**: For a service that provides its own dashboard, the maintainer MUST be able to reach that dashboard from cabal; for a service that exposes recent activity or a log, cabal MUST surface that activity or a clear pointer to it.
- **FR-011**: mcp-bus MUST be presented for visibility consistent with its nature as a client-launched message-bus server, and MUST NOT be given a standalone start/stop control that conflicts with how it is actually launched; its existing presence in the MCP group MUST be preserved.
- **FR-012**: Adding the services presentation MUST NOT change the behavior or rendering of the existing Tools or MCP screens (no regression).
- **FR-013**: The services presentation MUST follow the same interaction and presentation conventions already used for managed tools and MCP servers in cabal, so it is consistent for the maintainer.

### Key Entities *(include if feature involves data)*

- **Local service entry**: The catalog record that makes a service discoverable in the services presentation — its display name, description, run command, prerequisites, dependency relationships, source link, and the means to check its status.
- **Service status**: The current state of a service as shown to the maintainer — at minimum: not set up, ready/stopped, running, and an error/blocked state with an actionable reason.
- **Service lifecycle action**: An action a maintainer can take on a service — prepare/set up, start, stop, and (where available) open its dashboard / view its activity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can see all three services — each with its description, run command, source, and current status — in one place in cabal without leaving the wizard and without remembering any CLI command.
- **SC-002**: A maintainer can start a runnable service from cabal and observe its status change to "running", then stop it and observe its status return to "stopped", entirely within the wizard.
- **SC-003**: When a service cannot start because a prerequisite is missing, the maintainer receives a clear, actionable message and the service is not left in a misleading "running" state.
- **SC-004**: A maintainer can go from "service not running" to "service running" in a single action (after prerequisites are met), with no manual command entry.
- **SC-005**: The reported running/stopped status matches the service's actual state after a refresh in at least the common cases (started by cabal, stopped by cabal, exited outside cabal).
- **SC-006**: All existing managed tools and MCP servers — including mcp-bus's current place in the MCP group — continue to render and operate exactly as before the change.

## Assumptions

- "Run them from the wizard" is scoped, for this feature, to **session-oriented lifecycle**: cabal can start a runnable service, show whether it is running, and stop a service it started. A full background supervisor with automatic restart, crash recovery, or persistence of running state across separate cabal launches is out of scope for this iteration and may be a later feature.
- The runnable services for start/stop are **orchestrator** and **a2a-bridge**. **mcp-bus** is a stdio message-bus server launched on demand by its MCP clients (and already registered through the existing MCP machinery), so it is presented for visibility and availability but is not given a conflicting standalone start/stop control.
- Each service is set up using the same package-manager mechanism already used for the other locally-sourced managed tools in cabal, installing from its in-repo location, with prerequisites surfaced rather than silently assumed.
- Services require their own runtime prerequisites to actually start (for example, a2a-bridge requires a bearer token and an agent target and binds a local port; orchestrator requires auth, a notification endpoint, and a reachable a2a-bridge peer). Cabal surfaces these as actionable prerequisites; it does not invent or store new secrets beyond the existing environment/secret handling.
- The services presentation reuses cabal's existing presentation and interaction conventions for managed tools / MCP servers (grouping, status indicators, action buttons, source links) rather than introducing a new interaction paradigm.
- The orchestrator's own live dashboard is the "native dashboard" referenced for that service; a2a-bridge has no separate dashboard, so its observability is satisfied by surfacing its activity/log location.
- This feature does not change any service's own behavior, protocol, or CLI; it only surfaces and controls them from cabal.
