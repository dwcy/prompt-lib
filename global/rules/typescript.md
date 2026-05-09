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
