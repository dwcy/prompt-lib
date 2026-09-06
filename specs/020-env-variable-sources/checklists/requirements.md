# Specification Quality Checklist: Environment Variables — Multi-Source Browser

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-29
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Validation passed on the first iteration. Points worth recording:

- **Provider names are domain, not implementation.** Azure, Vercel, and GitHub are named throughout because they define the feature's scope — a stakeholder cannot evaluate it without knowing which providers are covered. No CLI command, endpoint, module path, language, or framework appears anywhere in the spec.
- **Zero clarification markers, deliberately.** Two questions were genuinely open — how widely to enumerate Azure resources, and what "application environments" means — and both were resolved as documented Assumptions rather than left as blockers. Both remain worth probing in `/speckit-clarify`; neither prevents planning.
- **FR-019 and FR-020 encode verified external constraints.** GitHub returns secret names without values by design (confirmed live against the repository origin: the secrets listing carries no value field), and Vercel never decrypts entries it marks sensitive. These are platform facts, not design choices, and drive the "never retrievable" classification in FR-017 and FR-018.
- **The read-only constraint has one deliberate carve-out.** FR-023 forbids all provider-side writes; FR-025 permits recording the user's own Azure scope as local workspace state. This was confirmed with the requester before the spec was written.
- **User Stories 1 and 2 form the MVP.** Together they deliver the whole promise with no external service, no authentication, and no network. Stories 3–7 each add one source or refinement and are independently shippable.

## Amendment — 2026-08-29, .NET configuration

Re-validated after adding User Story 7 and FR-040–FR-047. All 16 items still pass.

- **Why the amendment.** The original draft named `appsettings*.json` in the discovery set but treated every settings file as a flat, self-contained peer. Three things break under that assumption, all confirmed against current Microsoft documentation rather than recalled:
  1. Settings documents are hierarchical. A nested section has no "keys" until it is flattened to fully-qualified leaf paths, so FR-028 alone was ambiguous — hence FR-040 and FR-041.
  2. .NET defines a precedence across its own layers (command line → environment variables → developer secrets → `appsettings.{Environment}.json` → `appsettings.json`). The original edge case declared that the module "never declares one authoritative", which is correct across unrelated sources but actively misleading within one framework's own stack — hence FR-043 and the split edge case.
  3. `Properties/launchSettings.json` injects environment variables per launch profile and was matched by no discovery pattern — hence FR-042.
- **The scope change was the developer secret store.** .NET's Secret Manager keeps secrets in the user profile, keyed by an id declared in the project file, expressly so they cannot be committed. That is where .NET developers actually keep local secrets, and FR-026/FR-027 scan *within* the project, so it was structurally excluded. Including it means reading outside the project directory, which the requester approved explicitly. FR-047 bounds that: only stores the selected project itself declares, never enumeration of any other project's secrets.
- **Numbers are stable identifiers.** The new requirements are appended as FR-040–FR-047 rather than renumbered into the discovery group, so every FR reference written before this amendment still resolves. Their subsection sits last in the Requirements section to keep the numbering in reading order — grouping was traded for the ability to find a requirement by its number.
- **`appsettings.local.json` is recorded as a team convention, not a framework one.** .NET auto-loads only `appsettings.json` and `appsettings.{Environment}.json`. The pattern lists the file regardless — the module reports what is on disk and does not claim the application reads it.
