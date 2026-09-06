# Feature Specification: Environment Variables — Multi-Source Browser

**Feature Branch**: `020-env-variable-sources`
**Created**: 2026-08-29
**Status**: Draft
**Input**: User description: "Rename the Environment module to 'Environment variables' and expand it from a two-pill (Curated/System) view into a multi-source, read-only variable browser for the currently selected project — repo config files, Azure, Vercel, and GitHub — listing names and descriptions only, with an eye icon to fetch a single value on demand. Integration must be read-only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every config file the selected project actually carries (Priority: P1)

Someone opens a project and wants to know which environment/config files exist in it and what keys each one declares, without leaving the workspace and without opening a file explorer. Each discovered file becomes its own tab, named after the file, listing the keys it declares.

**Why this priority**: This is the only source that needs no external service, no authentication, and no network. It delivers the core promise — "show me the variables that affect this project" — entirely on its own, and it is the fallback view when every cloud source is absent or unreachable.

**Independent Test**: Select a project containing two or more config files, confirm one tab appears per file named after that file, and confirm each tab lists that file's keys with no values displayed. Fully testable offline.

**Acceptance Scenarios**:

1. **Given** a selected project containing `.env.local` and `appsettings.Development.json`, **When** the Environment variables module opens, **Then** a tab appears for each file, named after the file, listing the keys declared in it.
2. **Given** a selected project with no config files at all, **When** the module opens, **Then** no file tabs appear and the built-in Curated and System tabs remain fully usable.
3. **Given** a config file listing 40 keys, **When** its tab is opened, **Then** every key name is listed and no key's value is displayed anywhere on screen.
4. **Given** the user switches to a different project, **When** the module reloads, **Then** the file tabs are rebuilt from the newly selected project and no tab from the previous project remains.

---

### User Story 2 - Reveal one value, deliberately (Priority: P1)

Having found the key they care about, someone reveals that single value with an explicit click on an eye control. Nothing else on screen is revealed, and the reveal is a deliberate, auditable act rather than a side effect of opening a tab.

**Why this priority**: Names alone are often not enough to answer "is staging pointing at the right database?". Reveal is what turns the list from an inventory into a diagnostic tool. It pairs with User Story 1 to form the minimum viable feature.

**Independent Test**: Open any file tab, click the eye on one row, confirm only that row's value appears, and confirm the reveal is recorded in the audit trail.

**Acceptance Scenarios**:

1. **Given** a list of keys with no values shown, **When** the user activates the eye control on one row, **Then** only that row's value is displayed and every other row stays masked.
2. **Given** a value is revealed, **When** the user activates the same control again, **Then** the value is re-masked.
3. **Given** a value is revealed, **When** the user switches tabs or changes project, **Then** the value returns to its masked state without the user having to re-mask it.
4. **Given** any value reveal, **When** it completes, **Then** an audit record identifies which key from which source was revealed and when — without recording the value itself.
5. **Given** a revealed value, **When** the reveal completes, **Then** the value is not written to any file on disk and not persisted beyond the current view.

---

### User Story 3 - See what GitHub holds for this repository (Priority: P2)

Someone wants to know which environments the repository defines and which variables and secrets each one carries, so they can tell whether a deployment has the configuration it needs.

**Why this priority**: GitHub is the source most projects here actually have configured, and access is already established. It is also the source that most clearly demonstrates the "not retrievable" state, because secret values can never be read back.

**Independent Test**: Select a project whose origin is a GitHub repository, confirm tabs appear for repository-level variables/secrets and for each defined environment, and confirm secret rows show names with a permanently unavailable reveal control.

**Acceptance Scenarios**:

1. **Given** a project whose origin is a GitHub repository with two environments defined, **When** the module loads, **Then** a tab appears for each environment plus one for repository-level entries.
2. **Given** a GitHub variable row, **When** the user activates its eye control, **Then** the value is retrieved and displayed.
3. **Given** a GitHub secret row, **When** the row is rendered, **Then** its reveal control is permanently disabled and labelled to explain that the value can never be retrieved — this is not presented as an error or a failure.
4. **Given** a repository with no environments, variables, or secrets, **When** the module loads, **Then** the GitHub source reports that it is reachable but empty, rather than appearing broken or absent.
5. **Given** the project has no GitHub origin, **When** the module loads, **Then** no GitHub tabs appear.

---

### User Story 4 - See what Azure holds for this project (Priority: P2)

Someone working on an Azure-hosted project wants the names of the key vaults and the application environments that belong to it, and wants to reveal an individual setting when they have permission to do so.

**Why this priority**: Azure carries the configuration that most often differs between what a developer expects and what is actually deployed. It is lower priority than GitHub because linkage must be established first and permissions are frequently restricted.

**Independent Test**: Select an Azure-linked project, confirm key vault names and application environment names are listed, and confirm a permission-denied reveal degrades to an explanatory state rather than an error.

**Acceptance Scenarios**:

1. **Given** an Azure-linked project, **When** the module loads, **Then** the names of its key vaults and application environments are listed with no secret values retrieved.
2. **Given** a key vault secret row and the user holds the permission required to read secret values, **When** the user activates the eye control, **Then** the value is displayed.
3. **Given** a key vault secret row and the user does **not** hold that permission, **When** the user activates the eye control, **Then** the row explains that permission was denied and names what access would be required — the rest of the list stays usable.
4. **Given** an application setting whose value is a reference to a key vault entry rather than a literal, **When** it is revealed, **Then** it is shown as a reference and identified as such rather than presented as the resolved secret.
5. **Given** the local machine has no working Azure sign-in, **When** the module loads, **Then** Azure tabs report that sign-in is required and every other source continues to work.

---

### User Story 5 - See what Vercel holds for this project (Priority: P3)

Someone with a Vercel-linked project wants the names of its environment variables per deployment target, and wants to reveal a value where Vercel permits it.

**Why this priority**: The narrowest audience of the four sources, and the one whose tooling is least likely to be present on a given machine.

**Independent Test**: Select a Vercel-linked project, confirm variable names appear grouped by deployment target, and confirm variables Vercel marks as sensitive show a permanently unavailable reveal control.

**Acceptance Scenarios**:

1. **Given** a project with a linked Vercel project, **When** the module loads, **Then** its environment variable names are listed and grouped by deployment target.
2. **Given** a Vercel variable that is not marked sensitive, **When** the user activates the eye control, **Then** the value is displayed.
3. **Given** a Vercel variable marked sensitive, **When** the row is rendered, **Then** its reveal control is permanently disabled and labelled to explain that Vercel never returns the value.
4. **Given** no credential is available for Vercel, **When** the module loads, **Then** the Vercel source explains which credential is missing and every other source continues to work.
5. **Given** the project has no Vercel link, **When** the module loads, **Then** no Vercel tabs appear.

---

### User Story 6 - Correct or establish the Azure link by hand (Priority: P3)

When automatic detection points at the wrong Azure scope, or at nothing, someone records the correct subscription and resource group for this project once, and every later visit uses it.

**Why this priority**: A refinement that only matters after User Story 4 exists. It resolves the ambiguity of projects that carry infrastructure code for several environments, and of projects whose only Azure signal is the machine-wide default.

**Independent Test**: Record an Azure scope for a project that automatic detection got wrong, reopen the module, and confirm the recorded scope is used and shown as the reason for the link.

**Acceptance Scenarios**:

1. **Given** a project with a recorded Azure scope, **When** the module loads, **Then** the recorded scope is used in preference to every automatically detected signal.
2. **Given** any Azure-linked project, **When** the module displays its Azure source, **Then** it states which signal established the link.
3. **Given** a project whose only Azure signal is the machine-wide default sign-in, **When** the module loads, **Then** it is presented as a machine default rather than as a project link, and it is visibly distinguished from a genuine project link.
4. **Given** a recorded Azure scope, **When** the user clears it, **Then** the module falls back to automatic detection.

---

### User Story 7 - Follow a .NET project's configuration to where the values really are (Priority: P2)

Someone working on a .NET project wants the settings the application will actually read: the layered settings files, the environment variables its launch profiles inject, and the developer secrets the platform deliberately stores outside the repository. Settings files are hierarchical, so they want fully-qualified keys they can search for, not collapsed section names.

**Why this priority**: .NET is the one ecosystem where the values that matter are systematically *not* in the files the repository contains. A .NET developer looking at settings files alone sees empty connection strings and concludes the screen is broken. Listed after the P1 stories because it refines local discovery rather than replacing it, but it is what makes this feature honest for .NET work.

**Independent Test**: Select a .NET project that keeps a connection string in its developer secret store, confirm the key appears attributed to that store rather than to a settings file, and confirm hierarchical settings keys are listed fully qualified.

**Acceptance Scenarios**:

1. **Given** a settings file containing a nested section, **When** its tab is opened, **Then** each leaf is listed as a fully-qualified key path rather than as the section name alone.
2. **Given** a project declaring a developer secret store, **When** the module loads, **Then** that store appears as its own source, attributed as living outside the repository, listing its key names.
3. **Given** a project with launch profiles that inject environment variables, **When** the module loads, **Then** those variables are listed per profile.
4. **Given** a key defined in both the base settings file and an environment-specific one, **When** both are listed, **Then** each row states which layer it came from and which layer wins.
5. **Given** a project that declares no developer secret store, **When** the module loads, **Then** no such source appears and no error is reported.
6. **Given** a project that declares a secret store that has never been populated, **When** the module loads, **Then** the source reports itself as reachable and empty rather than missing.

---

### Edge Cases

- A monorepo contains dozens of config files across many packages — the tab strip must stay navigable rather than producing an unusable number of tabs.
- A config file is unreadable, malformed, or not valid for its format — its tab must report that rather than disappearing or breaking neighbouring tabs.
- A config file is empty, or contains only comments — the tab must distinguish "no keys declared" from "file could not be read".
- The same key name appears in several **unrelated** sources with different values — each occurrence stays attributed to its own source; the module never merges them into one row or declares one authoritative.
- The same key name appears in several layers of **one framework's own configuration stack**, where that framework defines which layer wins — the rows stay separate, but each states its layer and which one takes effect. Declaring them equal peers would be actively misleading (see FR-043).
- A hierarchical settings document nests keys several levels deep, or contains an array — every leaf must still be addressable as a single fully-qualified key.
- A project references a developer secret store that has never been created on this machine — that is "declared but empty", not a failure.
- Two projects in one repository share a settings file name (`appsettings.json` in three services) — tabs must stay distinguishable by more than the file name alone.
- An external source is slow or unreachable — its tab reports the timeout while every other tab stays usable; a single hanging source must never block the module from rendering.
- The user changes project while a reveal is in flight — the in-flight result must not be shown against the newly selected project.
- A config file changes on disk after the tabs were built — the user must be able to refresh without restarting the application.
- A source is detected but returns nothing — "reachable and empty" must be visibly different from "not linked" and from "failed".
- A revealed value is empty or whitespace — this must be distinguishable from the value being unavailable.
- A key vault or environment name is long enough to overflow its tab — names must remain identifiable.
- A project has no origin remote, no cloud links, and no config files — the module must still open on its existing Curated and System tabs.

## Requirements *(mandatory)*

### Functional Requirements

#### Naming and layout

- **FR-001**: The module MUST be presented as "Environment variables" everywhere it is named to the user.
- **FR-002**: The module MUST retain its existing Curated and System views, including the existing ability to stage and apply curated values. This feature MUST NOT alter that behaviour.
- **FR-003**: The module MUST present each discovered config file as its own tab, named after that file.
- **FR-004**: The module MUST present each detected external source as one or more tabs, distinct from the file tabs.
- **FR-005**: A tab MUST appear only when its underlying source is actually detected for the selected project. Sources that are absent MUST NOT occupy space.
- **FR-006**: Tabs MUST be rebuilt whenever the selected project changes, with no tab carried over from the previous project.
- **FR-007**: When the number of tabs exceeds what fits, the module MUST keep every tab reachable without truncating names to the point of ambiguity.

#### Names first

- **FR-008**: Loading any tab MUST retrieve names and descriptive metadata only. No value may be retrieved as part of loading a tab.
- **FR-009**: Descriptive metadata MUST include, where the source provides it, the deployment target or environment the entry belongs to, the entry's type or classification, and when it was last changed.
- **FR-010**: Every entry MUST be attributed to the source and container it came from, so identically named entries from different sources are never confused.

#### Reveal on demand

- **FR-011**: Every entry row MUST carry a reveal control, presented as an eye.
- **FR-012**: Activating the reveal control MUST retrieve exactly one value — that row's — and MUST NOT retrieve any other value.
- **FR-013**: Activating the control on a revealed row MUST re-mask it.
- **FR-014**: All revealed values MUST return to their masked state when the user changes tab or changes project.
- **FR-015**: Revealed values MUST NOT be written to disk, MUST NOT be written into any environment file, and MUST NOT persist beyond the current view.
- **FR-016**: Every reveal MUST be recorded in the audit trail, identifying the entry and its source. The audit record MUST NOT contain the value.

#### Retrievability as a first-class state

- **FR-017**: Each entry MUST declare whether its value is retrievable, and the reveal control MUST reflect that before the user activates it.
- **FR-018**: Entries whose values can never be retrieved MUST render a permanently disabled control with an explanation of why. This MUST NOT be presented as an error, a failure, or a retryable condition.
- **FR-019**: GitHub secrets MUST be classified as never retrievable. The platform returns names without values by design.
- **FR-020**: Vercel entries marked sensitive by the platform MUST be classified as never retrievable.
- **FR-021**: Entries whose retrievability depends on the user's permissions MUST be attempted on demand and, when refused, MUST report the refusal and name the access that would be required — leaving the rest of the list usable.
- **FR-022**: An application setting whose value is a reference to a secret store MUST be displayed as a reference and identified as such, never as a resolved secret.

#### Read-only integration

- **FR-023**: The feature MUST NOT create, update, or delete anything in Azure, Vercel, or GitHub under any circumstance.
- **FR-024**: The feature MUST NOT modify any config file it discovers in the project.
- **FR-025**: The only permitted write is recording the user's explicit Azure scope for a project, which is local to this workspace and never sent to any provider.

#### Discovering config files

- **FR-026**: The module MUST discover environment and configuration files within the selected project, including files excluded from version control — those are frequently the ones carrying real local configuration.
- **FR-027**: Discovery MUST NOT descend into dependency, build-output, or version-control internal directories.
- **FR-028**: Discovery MUST list the keys each file declares without displaying their values.
- **FR-029**: A file that cannot be read or parsed MUST surface that on its own tab without affecting other tabs.

#### Establishing the Azure link

- **FR-030**: The module MUST determine Azure linkage from four signals, applied in this order of precedence, with the first match winning:
  1. An Azure scope explicitly recorded for this project by the user.
  2. Azure Developer CLI conventions present in the project.
  3. Infrastructure-as-code definitions present in the project's infrastructure directory.
  4. The machine's default Azure sign-in.
- **FR-031**: The module MUST state which of the four signals established the link.
- **FR-032**: The machine's default sign-in MUST be presented as a machine default rather than a project link, and MUST be visibly distinguished from links established by the first three signals.
- **FR-033**: Users MUST be able to record an explicit Azure scope for a project, and to clear it so that automatic detection resumes.

#### Degrading without failing

- **FR-034**: A source whose supporting tooling is absent MUST report what is missing and MUST NOT prevent any other source from loading.
- **FR-035**: A source that is present but unauthenticated MUST report that sign-in is required and MUST NOT prevent any other source from loading.
- **FR-036**: A source that times out MUST report the timeout and MUST NOT prevent any other source from loading.
- **FR-037**: Every source MUST distinguish four outcomes from one another: not linked, reachable and empty, degraded with a stated reason, and loaded successfully.
- **FR-038**: Users MUST be able to refresh a source without restarting the application.
- **FR-039**: No external source may block the module from rendering.

#### Hierarchical and layered configuration

<!-- Added after the initial draft. Appended rather than renumbered into the discovery group
     above, so every FR reference written before the amendment still resolves. -->

- **FR-040**: Keys from hierarchical documents MUST be listed as fully-qualified paths down to each leaf, using the separator the owning framework itself uses, so a key can be searched for exactly as it is referenced in code.
- **FR-041**: A section or object that contains only other sections MUST NOT be listed as a key in its own right.
- **FR-042**: Where a project declares environment variables per launch or run profile, those MUST be discovered and attributed to the profile that injects them.
- **FR-043**: Where several discovered sources are layers of one framework's own configuration stack, and that framework defines a precedence between them, each entry MUST state which layer it came from and which layer takes effect. Entries MUST still occupy separate rows; the module MUST NOT compute a merged effective value.
- **FR-044**: Where a project declares a developer secret store that the platform deliberately keeps outside the repository, the module MUST resolve it from the project's own declaration and present it as its own source.
- **FR-045**: A secret store discovered under FR-044 MUST be attributed as living outside the repository, so no reader mistakes it for a file under version control.
- **FR-046**: A declared secret store that does not yet exist on this machine MUST be reported as reachable and empty, never as an error or a missing source.
- **FR-047**: Reading a store located outside the project directory MUST be confined to stores the selected project itself declares. The module MUST NOT enumerate or read stores belonging to any other project.

### Key Entities

- **Variable source**: One origin of configuration for the selected project — a discovered config file, a developer secret store the project declares but does not contain, or a detected external provider. Carries a kind, a display name, whether it lives inside or outside the repository, a link status, an outcome, and an explanatory hint when it is not fully loaded.
- **Variable container**: A grouping inside a source that becomes one tab — a single config file, a launch profile, a developer secret store, a key vault, an application environment, a deployment target, or a repository-level scope.
- **Variable entry**: One named key within a container. Carries its name, its descriptive metadata, its source and container attribution, and its retrievability classification. Never carries a value until revealed.
- **Retrievability classification**: Whether an entry's value is readable now, readable subject to permissions, or never readable — and the reason, in the last two cases.
- **Reveal result**: The outcome of one deliberate reveal — either a value held only for the current view, or a stated reason it could not be produced.
- **Azure project link**: The subscription and resource group associated with a project, together with which of the four signals established it and how much confidence that signal carries.
- **Configuration layer**: A source's position in a framework's own precedence order, where one exists. Lets an entry state which layer it came from and which layer wins, without the module computing a merged effective value.
- **Qualified key path**: An entry's name as the owning framework addresses it — every level of a hierarchical document joined by that framework's separator, down to a single leaf.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a project with local config files, a user can see every config file the project carries and the keys each declares within 3 seconds of opening the module, without any network access.
- **SC-002**: Opening the module, and opening any individual tab, reveals zero values. Values appear only after a deliberate reveal.
- **SC-003**: A user can locate a specific key across all sources and reveal its value in under 30 seconds.
- **SC-004**: When one source is unreachable, 100% of the remaining detected sources still load and remain usable.
- **SC-005**: Every entry whose value can never be retrieved is identifiable as such before the user attempts to reveal it, with a stated reason — measured as zero failed reveal attempts against permanently unavailable entries during usability testing.
- **SC-006**: Across a full session of browsing and revealing, zero create, update, or delete operations reach Azure, Vercel, or GitHub — verifiable from provider-side activity logs.
- **SC-007**: Every reveal appears in the audit trail, and no audit record contains a revealed value — verifiable by inspecting the audit trail after a session.
- **SC-008**: No revealed value survives a tab change, a project change, or an application restart.
- **SC-009**: For every Azure-linked project, a user can state which signal established the link without consulting documentation.
- **SC-010**: The module renders its first usable content within 3 seconds regardless of how many external sources are detected or how slow they are.
- **SC-011**: For a .NET project, a developer can find where a given setting's value actually comes from — which file, launch profile, or secret store, and which layer wins — without opening a terminal or a file explorer.
- **SC-012**: Every leaf of a hierarchical settings document is findable by searching for the exact key path used in application code.

## Assumptions

- **Config file discovery set**: Discovery targets `.env` and its common variants, `appsettings*.json`, `Properties/launchSettings.json`, and comparable per-project configuration files. Files excluded from version control are deliberately included, since those usually carry the real local configuration. The exact pattern list is treated as configuration rather than a fixed constant so it can grow without re-specification.
- **`appsettings.local.json` is a team convention, not a framework one**: .NET auto-loads only `appsettings.json` and `appsettings.{Environment}.json`; anything else loads only if the project registers it explicitly. The `appsettings*.json` pattern lists such files anyway — the module reports what is on disk and does not attempt to prove the application actually reads it.
- **Key separator follows the framework**: .NET addresses nested settings with a colon (`Logging:LogLevel:Default`) and accepts a double underscore in environment variables as a stand-in for it. FR-040 says "the separator the owning framework itself uses" rather than naming one, so other ecosystems are not forced into .NET's convention.
- **.NET precedence, for FR-043**: highest to lowest — command line, then environment variables, then developer secrets (Development only), then `appsettings.{Environment}.json`, then `appsettings.json`. The module shows this ordering; it never computes the merged result, because the effective value also depends on the environment the application runs under and on arguments the module cannot see.
- **Developer secret store, for FR-044**: .NET's Secret Manager stores secrets in the user profile, keyed by an id declared in the project file, expressly so they cannot be committed. Reading it therefore means stepping outside the project directory — bounded by FR-047 to stores the selected project declares. This is the .NET counterpart of `.env.local`; excluding it would leave the .NET half of this feature showing empty connection strings and nothing else.
- **Discovery depth**: Discovery is bounded to a depth sufficient for typical repositories and monorepo package directories, and always skips dependency, build-output, and version-control internal directories. An explicit cap prevents pathological scans.
- **Reveal is one at a time**: Each reveal is an individual act. There is no "reveal all" and no bulk export — that would defeat the names-first design and multiply the audit and exposure surface.
- **Auto-masking**: Revealed values auto-mask on tab change and project change. There is no idle timer in this feature.
- **"Application environments"** for Azure means the deployed application hosts associated with the project's scope and their configured settings, alongside the key vaults in that same scope.
- **Credentials are pre-existing**: The feature consumes whatever sign-ins the machine already has. It never prompts for, stores, or manages provider credentials, and it never initiates an interactive login.
- **Read-only means provider-side**: The read-only constraint governs the external providers. Recording the user's own Azure scope is local workspace state and is explicitly permitted by FR-025.
- **Existing behaviour is preserved**: The current Curated and System views and the existing curated-apply action are unchanged by this feature.
- **Source-of-truth reporting**: Each source reports its own state independently. The module never infers one source's health from another's.
- **Dependency on existing project selection**: The feature operates on whichever project the workspace currently has selected and has no project picker of its own.
- **Dependency on existing link detection**: Vercel and GitHub linkage reuse the project-link detection that already exists in the workspace. Azure link detection is new.
- **Dependency on existing audit and masking**: Reveal auditing and value masking reuse the workspace's existing audit trail and redaction behaviour rather than introducing new mechanisms.

## Out of Scope

- Editing, creating, or deleting variables in any external provider.
- Editing config files discovered in the project.
- Bulk reveal, bulk copy, or export of values in any form.
- Managing, refreshing, or storing provider credentials, or initiating interactive sign-in.
- Comparing or diffing values across sources or environments.
- Cloud providers other than Azure, Vercel, and GitHub.
- Any change to the existing curated-environment apply action.
