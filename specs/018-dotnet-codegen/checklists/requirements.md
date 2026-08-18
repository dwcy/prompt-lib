# Specification Quality Checklist: dotnet-codegen

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-14
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

**Iteration 1 findings:**

- *Content Quality — implementation details*: PASS with one deliberate exception. The spec names ".NET/C#" and "the .NET SDK" throughout. This is the feature's problem domain, not an implementation choice — the feature is defined as C# backend generation. Delivery mechanism (prompt assets vs. analysis service vs. standalone agent) is correctly left unresolved and deferred to `/speckit-plan`.

- *Success criteria — technology-agnostic*: PASS. SC-001..SC-010 are stated as developer-observable outcomes (wall-clock, proportion of tokens, first-attempt success rate) with no vendor, framework, or product named. Token and cache metrics are retained deliberately: the developer specified that success must be measured in the four cost centres rather than in subjective code quality.

**Iteration 2 — open decisions resolved by the developer and folded into the spec:**

1. **Architecture lock** → *small closed set, locked per project*. Template chosen once at project creation from a short maintained list, recorded in the project, never re-decided. Folded into FR-001, FR-001a/b/c, US1 (story text + scenarios 1, 3, 4), SC-001, SC-012. Chosen over a single global template because it fits `@dotnet-architect`'s existing behaviour of reading each project's CLAUDE.md, and over per-run inference because inference would forfeit the largest cost lever in the design.

2. **Autonomy model** → *gate after reasoning*. Each run pauses once, presents its intent in prose, and proceeds unattended only after approval. Folded into FR-010a..FR-010e, US1 story text, SC-001, SC-011. This places the only human checkpoint at the cheapest possible point to catch a wrong intent — before any code has been written.

3. **Relationship to existing assets** → *coexist, decide later*. No existing agent, command, or rules file is modified. Folded into FR-032, FR-032a, FR-032b and the Assumptions section. Consolidation is deferred to a follow-up feature driven by real usage data.

**Status: all checklist items pass.** The spec is ready for `/speckit-plan`.

Two items are deliberately left for the planning phase rather than the spec, and are recorded as assumptions rather than gaps:

- **Which templates constitute the closed set**, and how many. The spec fixes the *shape* of the decision (small, closed, per-project-locked); naming the members is a design choice.
- **The delivery form** — prompt assets, a semantic-analysis service plus a driving skill, a standalone agent, or a hybrid. This is the primary question `/speckit-plan` exists to answer here, and must be costed against SC-001..SC-012.
