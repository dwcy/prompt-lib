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
