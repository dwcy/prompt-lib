---
description: C# file conventions — loaded automatically when editing .cs files
paths:
  - "**/*.cs"
---

When editing C# files:

- Use **file-scoped namespaces** — `namespace Foo;` not `namespace Foo { }`
- Use **primary constructors** for simple dependency injection (C# 12+)
- Use `record` for immutable DTOs and value objects
- Use `sealed` on classes not designed for inheritance
- Do not use `var` when the type is not clear from the right-hand side
- Prefer **pattern matching** over type casting and null checks
- Use `is null` / `is not null` — not `== null`
- Nullable reference types are enabled — do not suppress warnings without a comment
- `async` methods must be awaited — no fire-and-forget without explicit intent
- **Formatting** is applied automatically by the `format_on_write` PostToolUse hook via `dotnet format` when a `.csproj`/`.sln` and `.editorconfig` are present. Match the project's `.editorconfig`; the hook will silently fix style violations after each Write/Edit.

## File size and single responsibility

| File kind | Soft cap | Hard cap |
|---|---:|---:|
| Plain class `.cs` | 200 | 350 |
| Partial class (counted as one) | 200 | 350 |
| Record / DTO | 100 | 200 |
| Test class | 300 | 500 |

- One class per file. Partials counted as one.
- **Hard cap** = split, OR write a justification at line 1: `// > 350 LoC justified: <one-line structural reason>`.
- Non-substantive reasons ("needed", "complex") fail the verifier audit.
- The 5 concern-separation triggers live in `_size-discipline.md` — two or more firing = split before writing.
- Domain layer must have zero external dependencies; if a file mixes domain types with EF / HTTP / DI plumbing, split.
- Commands mutate state; Queries return data — never mix in the same handler file.
