# Feature Specification: Installable Distribution with Installation Wizard

**Feature Branch**: `016-install-wizard`
**Created**: 2026-07-11
**Status**: Draft
**Input**: User description: "I need you to make a plan on how to have this as a proper installable with a installation wizard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh-Machine Install (Priority: P1)

A person setting up a new machine obtains the prompt-lib installable through a single standard install command, runs it, and is guided by an installation wizard through every step needed to reach a fully working Claude Code configuration — prerequisite checks, component selection, deployment to the global configuration location, and final verification. They never need to clone the repository, know its internal layout, or run repository-internal scripts.

**Why this priority**: This is the core value of the feature. Today a new machine requires cloning the repo, knowing about the apply script or TUI, and performing several one-time manual steps (git hooks path, identity filter, checkout refresh). A self-contained installable with a wizard removes every one of those manual steps and makes setup reproducible.

**Independent Test**: Can be fully tested on a machine (or clean user profile) that has never had prompt-lib: run the install command, complete the wizard with default answers, then confirm Claude Code sessions see the deployed agents, skills, hooks, rules, and settings.

**Acceptance Scenarios**:

1. **Given** a machine with no prompt-lib present, **When** the user runs the single install command and accepts the wizard defaults, **Then** all default components (settings, global instructions, agents, skills, hooks, rules, output styles) are deployed to the global configuration location and the wizard reports a verified, working installation.
2. **Given** a machine missing a required prerequisite, **When** the wizard runs its prerequisite check, **Then** it names the missing prerequisite, explains how to obtain it, and does not proceed with a partial deployment.
3. **Given** the wizard is at the component-selection step, **When** the user deselects an optional component group, **Then** that group is not deployed and everything else installs normally.
4. **Given** a completed installation, **When** the user starts a new Claude Code session, **Then** the deployed configuration is active without any further manual steps.

---

### User Story 2 - Safe Upgrade of an Existing Installation (Priority: P2)

A person with prompt-lib already installed runs the installer again (same or newer version). The wizard detects the existing installation, shows what would change before touching anything, backs up every file it will overwrite, applies the update, and preserves machine-local customizations it does not own.

**Why this priority**: The configuration evolves continuously; an installable that can only do first-time setup would be abandoned after a week. Safe, previewable upgrades are what make the installable the permanent distribution channel instead of a one-off convenience.

**Independent Test**: Install once, modify one managed file and one machine-local file, run the installer again with a newer version, and verify the managed file is updated (with a backup taken) while the machine-local file is untouched.

**Acceptance Scenarios**:

1. **Given** an existing installation, **When** the user runs the installer again, **Then** the wizard identifies the installed version and presents a preview of additions, updates, and removals before writing anything.
2. **Given** the preview is shown, **When** the user declines, **Then** no files are modified.
3. **Given** the user accepts an upgrade, **When** files are overwritten, **Then** every overwritten file is backed up first and the backup location is reported.
4. **Given** machine-local settings or user-created files exist alongside managed files, **When** an upgrade runs, **Then** those files are never modified or deleted.
5. **Given** an installation already at the latest version, **When** the installer runs, **Then** it reports "up to date" and makes zero changes.

---

### User Story 3 - Health Check and Repair (Priority: P3)

A person who suspects their setup is broken (a hook not firing, a skill missing) runs the installer's health check. It verifies the installed components against what the installed version should contain, reports anything missing, modified, or stale, and offers to repair the differences.

**Why this priority**: Deployed configuration drifts — files get hand-edited, partially deleted, or clobbered by other tools. A doctor mode turns "reclone and redeploy everything" into a targeted, low-risk repair.

**Independent Test**: Install, then delete one deployed file and hand-edit another; run the health check and verify both are detected and can be repaired individually.

**Acceptance Scenarios**:

1. **Given** a healthy installation, **When** the health check runs, **Then** it reports all components present and matching the installed version.
2. **Given** a deployed file was deleted or modified, **When** the health check runs, **Then** the specific file and the nature of the difference are reported.
3. **Given** reported differences, **When** the user chooses repair, **Then** only the differing files are restored and machine-local files are untouched.

---

### User Story 4 - Clean Uninstall (Priority: P4)

A person removes prompt-lib from a machine. The uninstaller removes everything the installer deployed, offers to restore any pre-installation backups, and leaves all user-created and machine-local files in place.

**Why this priority**: Lowest frequency of use, but a proper installable is defined as much by clean removal as by installation — and it is the safety net that makes people willing to install in the first place.

**Independent Test**: Install on a profile that already had some pre-existing global configuration, then uninstall and verify managed files are gone and the pre-existing configuration is back.

**Acceptance Scenarios**:

1. **Given** a completed installation, **When** the user uninstalls, **Then** every file the installer deployed is removed and files it never deployed remain.
2. **Given** the installer had backed up pre-existing files during installation, **When** the user uninstalls, **Then** they are offered restoration of those backups.
3. **Given** the user confirms uninstall, **When** it completes, **Then** a summary lists exactly what was removed and what was restored.

---

### Edge Cases

- **Interrupted installation** (power loss, closed terminal mid-wizard): a re-run must detect the incomplete state and either resume or roll back cleanly — never leave a half-deployed configuration presented as complete.
- **Pre-existing unmanaged content** in the global configuration location (the user's own agents, skills, or settings created outside prompt-lib): the installer must treat these as foreign, never overwrite them silently, and ask before touching any name collision.
- **Missing prerequisites discovered mid-flow** (a tool present at check time but failing at use time): fail the affected step with an actionable message rather than aborting the whole installation silently.
- **Downgrade attempt** (installing an older version over a newer one): must be detected and require explicit confirmation.
- **Secrets and environment files**: the installer must never create or modify environment/secret files; where configuration needs them, it provides copy-paste instructions instead.
- **Non-interactive environments** (provisioning scripts, no TTY): installation must be possible without the wizard by supplying answers up front; the wizard is the default, not the only path.
- **Machine-specific values** (paths, identity, locally-enabled integrations): the wizard must collect or detect these per machine rather than baking one machine's values into the distributed package.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be distributable as a versioned, self-contained installable that can be installed on a machine with a single standard command, without cloning the source repository.
- **FR-002**: The system MUST support Windows, macOS, and Linux with the same user-facing installation flow.
- **FR-003**: The installer MUST provide a guided installation wizard that walks the user through, at minimum: prerequisite verification, component selection, machine-specific configuration, a pre-write preview, deployment, and post-install verification.
- **FR-004**: The wizard MUST check all prerequisites before deploying anything and report each missing prerequisite with an actionable instruction for obtaining it.
- **FR-005**: The wizard MUST let the user select or deselect optional component groups (at minimum: agents, skills, hooks, rules, output styles, integration/server configuration) while always installing the required core.
- **FR-006**: The installer MUST show a preview of every file it will add, update, or remove and obtain confirmation before writing.
- **FR-007**: The installer MUST back up every pre-existing file it overwrites and record where backups live; backups MUST be restorable.
- **FR-008**: The installer MUST maintain a record of what it deployed (components, files, version) so that upgrade, health check, and uninstall can distinguish managed files from user-created files.
- **FR-009**: Re-running the installer MUST be safe and idempotent: an up-to-date installation results in zero changes, and an outdated one is upgraded through the same preview-and-confirm flow.
- **FR-010**: The installer MUST never modify or delete files it did not deploy, and MUST ask before resolving any name collision with unmanaged files.
- **FR-011**: The installer MUST never create or edit environment/secret files; when such files are needed it MUST output copy-paste instructions and required content instead.
- **FR-012**: The system MUST provide a health-check mode that compares the deployed state against the installed version's expected state and reports missing, modified, or extra managed files, with an optional targeted repair.
- **FR-013**: The system MUST provide an uninstall mode that removes all managed files, offers restoration of pre-installation backups, and reports a summary of actions taken.
- **FR-014**: The system MUST support a non-interactive installation mode in which all wizard answers are supplied up front, producing the same result as the equivalent interactive run.
- **FR-015**: Each release of the installable MUST carry a version, and the installed version MUST be discoverable on the machine after installation.
- **FR-016**: The installer MUST complete all one-time setup steps that today require manual action after cloning (repository hook enablement, identity-injection configuration, initial deployment) without the user performing them by hand.
- **FR-017**: An interrupted installation MUST be detectable on the next run and MUST be resumable or cleanly rolled back; the system MUST never report a partial deployment as successful.
- **FR-018**: Personal identity values (name, email, machine paths) MUST NOT be embedded in the distributed package; they MUST be collected or detected per machine at install time.

### Key Entities

- **Distribution Package**: The versioned, self-contained artifact a user obtains and installs; carries the full deployable payload and the wizard.
- **Component Group**: A selectable unit of the configuration (agents, skills, hooks, rules, output styles, integration configuration); has a required/optional flag.
- **Installation Manifest**: The on-machine record of the installed version, selected components, every deployed file, and backup locations; the source of truth for upgrade, health check, and uninstall.
- **Backup Snapshot**: A preserved copy of any pre-existing file the installer overwrote, linked from the manifest and restorable individually or together.
- **Machine-Local Configuration**: Values and files owned by the machine/user rather than the package (identity, local paths, locally-enabled integrations, user-created agents/skills); never overwritten by install or upgrade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user on a fresh machine reaches a verified working configuration in under 10 minutes using one install command plus the wizard, with zero manual file edits.
- **SC-002**: 100% of the one-time manual setup steps documented today (deploy script, repository hook enablement, identity filter configuration) are eliminated from the fresh-install path.
- **SC-003**: Running the installer twice in a row results in zero file changes on the second run.
- **SC-004**: 100% of files overwritten during install or upgrade are recoverable from backups.
- **SC-005**: After uninstall, zero managed files remain and 100% of user-created files present before installation are intact.
- **SC-006**: The health check detects 100% of deliberately introduced defects (one deleted managed file, one modified managed file) in a verification test.
- **SC-007**: A non-interactive install produces a configuration identical to an interactive install given the same answers.

## Assumptions

- The primary audience is the repository owner installing on their own machines; making the installable shareable with teammates is a secondary benefit, supported by the existing practice of keeping personal identity out of the distributed content (FR-018) but not adding multi-user management features.
- The existing interactive setup TUI (the `run` configurator wizard) is the conceptual foundation: this feature packages and extends that experience into a clone-free installable, rather than introducing a second, parallel setup system.
- "Installable" means a standard package/artifact installed by a common tooling command, not an OS-native graphical installer (MSI/pkg/deb); the wizard is a guided terminal experience consistent with the project's existing tooling.
- The global configuration location (`~/.claude/`) remains the deployment target; this feature changes how content gets there, not where it lives.
- Producing releases of the package happens from this repository; the release/publishing workflow itself is in scope only insofar as a versioned artifact must exist for users to install (the CI mechanics are a planning-stage decision).
- Environment/secret file policy is inherited unchanged: such files are never written by tooling, only documented for manual creation.
