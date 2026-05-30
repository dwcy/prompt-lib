---
description: TypeScript file conventions — loaded automatically when editing .ts or .tsx files
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

When editing TypeScript files:

- `strict: true` is enforced — no `any`, use `unknown` and narrow it
- No non-null assertions (`!`) without a comment explaining why it is safe
- Prefer `type` for simple shapes, `interface` for extensible contracts
- Named exports for everything except page/route components (framework convention)
- Props interfaces named `[ComponentName]Props`
- Custom hooks must start with `use`
- No inline `style={{}}` unless the value is truly dynamic
- Do not use `React.FC` — type props directly on the function signature
- **Formatting** is applied automatically by the `format_on_write` PostToolUse hook via `biome format --write` when a `biome.json`/`biome.jsonc` is present. The hook silently reformats `.ts`/`.tsx`/`.js`/`.jsx`/`.json` after each Write/Edit.

## File size and single responsibility

For React component files (`.tsx`) and React-adjacent `.ts` under `components/`, `hooks/`, `features/`, etc., see `react.md` for the per-kind budgets. For plain TS utilities outside that surface:

| File kind | Soft cap | Hard cap |
|---|---:|---:|
| Pure TS utility `.ts` | 150 | 300 |
| Type-only `.ts` (interfaces, schemas) | 200 | 400 |
| Test module | 300 | 500 |

- One domain per file. A `formatCurrency` helper does not share a file with a `parseAddress` helper.
- **Hard cap** = split, OR write a justification at line 1: `// > 300 LoC justified: <one-line structural reason>`.
- The 5 concern-separation triggers live in `_size-discipline.md` — two or more firing = split before writing.
