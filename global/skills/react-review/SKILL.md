---
name: react-review
description: Structured code quality review of a React file or feature — checks separation of concerns, naming, component design, data flow, types, documentation, and code hygiene. Use when the user says "review this component", "review this React code", or wants a quality pass before merging. Reports Critical / Warning / Suggestion. Hand redesign follow-ups to @react-architect.
allowed-tools: Read, Glob, Bash
---

Review the target file or feature for code quality. If no target is given, ask: "Which file or feature should I review?"

Read the target file(s) first. If a feature directory is given, Glob and read all files inside it.

---

## Review checklist

Work through each category. Report every finding — not just the worst ones.

### Separation of concerns

- Does the component contain business logic? (fetch calls, data transformation, conditional flow beyond rendering)
- Does any component read directly from `api/` instead of going through a hook?
- Is there any shared state that should be in a Zustand store instead of prop-drilled?
- Is there circular dependency risk between imports?

### Component design

- Is the component doing too many things? (>150 lines of JSX is a signal)
- Are there repeated JSX blocks that should be extracted into a child component?
- Are heavy components lazy-loaded?
- Is `user-select: none` applied to non-editable interactive elements?
- Is any `dangerouslySetInnerHTML` present without DOMPurify?

### Naming and style

- Are names intent-driven? (no `data`, `item`, `val`, `temp`, `x`)
- Are constants extracted, or are magic strings/numbers inline?
- Is the import order: external → `@/` internal → relative?
- Are there unused imports or variables?
- Are all exports named (not default)?

### Functions and logic

- Are functions single-purpose and small?
- Is complex logic broken into named intermediate variables?
- Is there any clever one-liner that a junior dev would need to decode?
- Are all WHY comments present where the reasoning is non-obvious?

### Data flow

- Are API response shapes normalized at the boundary?
- Are data transformations explicit and named (not chained opaque pipelines)?
- Does the data flow direction hold: UI → hook → query/mutation → api?

### Type safety

- Are all props typed with a `[ComponentName]Props` interface?
- Are any API responses typed as `any` or left untyped?
- Are union types used where a string literal set is known?
- Are domain IDs typed (not raw `string`)?

### Async and error handling

- Is `async/await` used consistently (no `.then()` chains)?
- Are all `await` calls inside `try/catch` or handled via TanStack Query?
- Are errors silently swallowed anywhere?
- Does error logging include contextual metadata?

### Documentation

- Does the file have a top-of-file intent comment?
- Do non-obvious functions have a WHY comment?
- Are exported types and functions understandable without reading their implementation?

### Code hygiene

- Commented-out code blocks present?
- TODO or FIXME comments left behind?
- Dead code paths (unreachable branches, unused state)?

---

## Output format

```
## Code Review: [filename or feature]

### Critical
- [Finding] → [Specific fix or example]

### Warning
- [Finding] → [Suggestion]

### Suggestion
- [Finding] → [Improvement]

### Positive
- [What is done well — be specific]
```

- **Critical** — violates separation of concerns, security risk, unhandled async error, raw API leak into UI
- **Warning** — naming, magic values, missing types, lazy-load opportunity missed
- **Suggestion** — clarity improvement, extract opportunity, better naming
- **Positive** — genuinely good patterns worth noting

Always include at least one Positive finding. If there are zero Critical findings, say so explicitly.

After the report, ask: "Want me to fix the Critical and Warning items now?"
