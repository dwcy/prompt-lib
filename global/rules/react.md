---
description: React architecture and code quality rules — loaded when editing React components, hooks, features, state, and API files
paths:
  - "**/*.tsx"
  - "**/components/**/*.ts"
  - "**/features/**/*.ts"
  - "**/hooks/**/*.ts"
  - "**/state/**/*.ts"
  - "**/api/**/*.ts"
  - "**/pages/**/*.ts"
  - "**/router/**/*.ts"
---

## File intent

Add a short one-line comment at the top of each new file describing its intent. Update it if the file's purpose changes.

## Separation of concerns (enforce always)

```
UI component → custom hook → query/mutation hook → API client
```

- Components = presentation only. No fetch calls, no business logic, no direct store reads beyond display.
- Business logic → hooks in `hooks/` or feature-level hooks in `features/<name>/hooks/`
- Data access → `api/` layer or feature query hooks. Never raw `fetch`/`axios` in component bodies.
- Avoid circular dependencies between layers.

## Numeric LoC budgets

| File kind | Soft cap | Hard cap |
|---|---:|---:|
| React component `.tsx` | 100 | 200 |
| Custom hook `.ts` (`use*`) | 80 | 150 |
| TanStack route / loader | 100 | 200 |
| Zustand store | 100 | 200 |
| Shared utility `.ts` | 150 | 300 |

- **Hard cap** = split, OR write a justification at line 1: `// > 200 LoC justified: <one-line structural reason>`.
- Non-substantive reasons ("needed", "for now") fail the verifier audit.
- The 5 concern-separation triggers live in `_size-discipline.md` — two or more firing = split before writing.

## Component rules

- Break large components into smaller focused ones — hard cap 200 LoC for `.tsx`.
- Lazy-load heavy components: `const HeavyComponent = lazy(() => import('./HeavyComponent'))`
- No inline `style={{}}` unless the value is computed at runtime.
- `user-select: none` on all non-editable interactive elements (buttons, nav, labels).
- DOMPurify before any `dangerouslySetInnerHTML`.
- No business logic in JSX — extract to a variable or hook before rendering.

## Data flow

- Normalize API response shapes at the API boundary — never pass raw response objects deep into the app.
- Make all data transformations explicit: use named intermediate variables, not chained map/filter/reduce.
- Comment WHY a transformation exists if it isn't obvious from the variable name.
- No magic values — define as constants or enums in `lib/constants.ts`.

## Async patterns

- `async/await` always — no raw `.then()` chains.
- Every `await` must have explicit error handling: `try/catch`, React Error Boundary, or TanStack Query's `onError`.
- Never silently swallow errors. Log or propagate with context (userId, endpoint, timestamp).
- For recoverable errors prefer a typed result (`{ data, error }`) over throwing.

## Constants and types

- No magic strings or numbers inline — define in `lib/constants.ts` or co-located `[feature].constants.ts`.
- Union types over string literals where the set of values is known.
- Branded types for domain IDs to prevent mixing: `type UserId = string & { __brand: 'UserId' }`.

## Imports order

```ts
// 1. External packages
import { useQuery } from "@tanstack/react-query"
// 2. Internal @/ paths
import { apiClient } from "@/api/client"
// 3. Relative
import { formatDate } from "./utils"
```

## Environment variables

- NEVER write to `.env`, `.env.develop`, or any env file. Provide copy-paste instructions instead.
- Only `.env.example` is committed. All others are gitignored.
- Use UTF-8 encoding (no BOM) when instructing manual file creation.
- All client-side env vars must use the `VITE_` prefix.

## DRY and YAGNI

- Extract shared logic when you see it duplicated a second time, not speculatively.
- Remove unused variables, imports, and dead code immediately — do not comment out.
- No TODO comments left in committed code — either do it now or create a task.
