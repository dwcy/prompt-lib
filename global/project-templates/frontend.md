## Questions

1. Which framework?
   - React
   - Next.js (React + SSR)
   - Vue 3
   - Nuxt 3 (Vue + SSR)
   - Angular
   - Svelte / SvelteKit
   - Vanilla JS / no framework

2. Which styling approach?
   - Tailwind CSS
   - CSS Modules
   - styled-components / Emotion
   - SCSS / SASS
   - Plain CSS

3. Which state management (if any)?
   - Zustand
   - Redux Toolkit
   - Pinia (Vue)
   - Jotai / Recoil
   - React Query / TanStack Query only (server state)
   - None / component state only

4. TypeScript? (yes/no)

5. Which package manager?
   - pnpm (recommended)
   - Bun

6. Which test setup?
   - Vitest + Testing Library
   - Jest + Testing Library
   - Playwright (E2E only)
   - Vitest + Playwright (both)
   - No tests yet

7. Is there a component library?
   - shadcn/ui
   - Radix UI
   - MUI / Material
   - Chakra UI
   - None — custom components only

---

## CLAUDE.md Template

# [Project Name] — Frontend Developer Guide

## Stack

- **Framework:** [FRAMEWORK]
- **Language:** [TypeScript / JavaScript]
- **Styling:** [STYLING APPROACH]
- **State management:** [STATE MANAGEMENT]
- **Package manager:** [PACKAGE MANAGER]
- **Tests:** [TEST SETUP]
- **Component library:** [COMPONENT LIBRARY]

## Project Structure

```
src/
  components/      # Shared / reusable UI components
  features/        # Feature-scoped components and logic
  hooks/           # Custom React hooks
  lib/             # Utilities, helpers, API clients
  pages/ (or app/) # Route-level components
  store/           # Global state
  types/           # Shared TypeScript types
  styles/          # Global styles, theme tokens
```

## Code Conventions

- **One component per file** — filename matches component name (PascalCase)
- **No default exports** for utilities and hooks — named exports only
- Default exports only for page/route components (framework convention)
- Use `const` arrow functions for components: `export const Button = () => {}`
- Props interfaces named `[ComponentName]Props`
- Custom hooks must start with `use`

## Version Rules

- Use the latest stable version of the selected framework, libraries, and tooling.
- Verify current stable docs or registry metadata before adding version-specific APIs or packages.
- Do not pin stale year-based stack assumptions into project rules.

## Package Manager Rules

- Use only the selected package manager: [PACKAGE MANAGER].
- Do not run `npm`, `npx`, or `yarn`.
- Use `pnpm dlx` or `bunx` for one-off package executors.
- If the repo contains only `package-lock.json` or `yarn.lock`, ask before migrating to `pnpm` or `bun`.

## TypeScript Rules

- `strict: true` in tsconfig — no exceptions
- No `any` — use `unknown` and narrow, or define the type
- No non-null assertions (`!`) without a comment explaining why it's safe
- Prefer `type` over `interface` for simple shapes; `interface` for extensible contracts

## Component Rules

- Keep components **small and focused** — if it renders more than ~100 lines, split it
- Extract logic into custom hooks, not inline in JSX
- No business logic in components — components only display data and call handlers
- Avoid deeply nested JSX — extract sub-components

## State Rules

- Server state → TanStack Query (fetching, caching, mutations)
- UI state → local `useState` or context
- Global client state → [STATE MANAGEMENT LIBRARY]
- Do not store derived data in state — compute it

## Testing Rules

- Test behavior, not implementation — never test internal state
- Use `data-testid` only as a last resort; prefer accessible queries (`getByRole`, `getByLabelText`)
- Every feature component should have at least a smoke test

## What NOT to do

- Do not fetch data directly in components — use hooks or query functions
- Do not mutate props or external state directly
- Do not use `index.js` barrel files — they hurt tree-shaking
- Do not inline styles as `style={{}}` unless truly dynamic

## Build & Run

```bash
# pnpm
pnpm install
pnpm dev
pnpm build
pnpm test

# Bun
bun install
bun run dev
bun run build
bun test
```
