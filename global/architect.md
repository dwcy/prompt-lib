# Design Philosophy

Personal design principles that apply across all projects and languages.

## Software design

- Favour **simplicity over cleverness** — the best solution is the one the next developer can understand without asking questions
- **Explicit over implicit** — if behaviour isn't obvious from reading the code, it needs a comment or a rename, not a convention
- Design for **deletability** — code that is easy to remove or replace is well-designed code
- Prefer **boring technology** for core infrastructure and **interesting technology** at the edges where it earns its complexity
- Small, focused units — a function does one thing, a class owns one concept, a module has one reason to change

## Architecture

- Dependencies point inward — domain logic never depends on infrastructure
- Define boundaries early and enforce them — it is much harder to untangle coupling later
- Ports and adapters over direct integration — abstract external dependencies behind interfaces you own
- Start with a monolith, extract services only when a team or scaling boundary demands it
- Every architectural decision has a cost — name the tradeoff when making the choice

## API and interface design

- Design the interface before the implementation — write the calling code first
- Fail fast and loudly — surface errors at the boundary, not deep in the call stack
- Return types should be honest — avoid returning null when you mean "not found", use Result or Option patterns
- Immutable by default — mutability is a feature that requires justification
- Make invalid state unrepresentable in the type system where possible

## UI and UX (when applicable)

- Functionality before aesthetics — a beautiful interface that does the wrong thing is worse than an ugly one that works
- Respect the user's mental model — don't surprise them
- Empty states, loading states, and error states are part of the design — not afterthoughts
- Accessibility is not optional — keyboard navigation and screen reader support from the start

## What to avoid

- Premature abstraction — wait until you see the pattern three times before extracting it
- Premature optimisation — profile first, optimise second
- Accidental complexity — complexity that exists because of the implementation, not the problem
- Resume-driven development — choosing technology to learn it rather than because it fits
