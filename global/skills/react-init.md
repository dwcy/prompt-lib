---
name: react-init
description: Scaffold a new React 2025 project — Vite + TypeScript + Zustand + TanStack + Biome + Tailwind v4 + Zod + MUI Icons. Asks questions then generates all config files, folder structure, and .cursorrules.
allowed-tools: Bash, Read, Write, Edit, Glob
---

Scaffold a complete React 2025 project. Ask all questions first, then execute everything in order without further interruptions.

---

## Step 1 — Ask these questions upfront

Ask all at once in a single message:

1. **Runtime** — Bun or Node.js (npm)?
2. **i18n** — Does this project need multi-language support? (react-i18next)
3. **Auth** — Authentication needed? If yes: Clerk or Auth.js?
4. **Testing** — Add testing setup? (Vitest + React Testing Library + Playwright)
5. **Storybook** — Add Storybook for component documentation?
6. **API client** — Axios or native fetch?
7. **Tailwind enhancer** — Add a component library on top of Tailwind?
   - Options: shadcn/ui, Radix UI, DaisyUI, Mantine, Chakra UI
   - Or "none"
8. **Monorepo** — Will this be part of a Turborepo monorepo?
9. **Project name** — What is the project name (used in package.json and README)?
10. **Font** — Primary font family? (Inter, Manrope, Plus Jakarta Sans, Satoshi, Space Grotesk, Sora, Roboto, or custom)

Wait for answers before proceeding.

---

## Step 2 — Verify clean directory

```bash
ls -la
```

If the directory is not empty, warn the user and ask to confirm before continuing.

---

## Step 3 — Create the Vite project

**With Bun:**
```bash
bun create vite . --template react-ts
```

**With Node/npm:**
```bash
npm create vite@latest . -- --template react-ts
```

---

## Step 4 — Install core dependencies

**With Bun:**
```bash
bun add zustand @tanstack/react-query @tanstack/react-router @tanstack/react-form
bun add zod dompurify
bun add @mui/icons-material @mui/material @emotion/react @emotion/styled
bun add tailwindcss @tailwindcss/vite
bun add -d @biomejs/biome @types/node @types/dompurify
```

**With npm:**
```bash
npm install zustand @tanstack/react-query @tanstack/react-router @tanstack/react-form
npm install zod dompurify
npm install @mui/icons-material @mui/material @emotion/react @emotion/styled
npm install tailwindcss @tailwindcss/vite
npm install -D @biomejs/biome @types/node @types/dompurify
```

---

## Step 5 — Install optional dependencies based on answers

**i18n:**
```bash
bun add react-i18next i18next i18next-http-backend i18next-browser-languagedetector
# or: npm install react-i18next i18next ...
```

**Auth — Clerk:**
```bash
bun add @clerk/clerk-react
```

**Auth — Auth.js:**
```bash
bun add @auth/core
```

**Testing:**
```bash
bun add -d vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
bun add -d @playwright/test
```

**Axios:**
```bash
bun add axios
```

**shadcn/ui:**
```bash
bunx shadcn@latest init
```

**Radix UI:**
```bash
bun add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tooltip
```

**DaisyUI:**
```bash
bun add -d daisyui
```

**Mantine:**
```bash
bun add @mantine/core @mantine/hooks
```

**Storybook** — run after other deps are installed:
```bash
bunx storybook@latest init --builder vite
# or: npx storybook@latest init --builder vite
```

**Turborepo:**
```bash
bun add -d turbo
```

---

## Step 6 — Write config files

### `vite.config.ts`

Read the existing `vite.config.ts` first, then replace entirely:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  esbuild: {
    drop: mode === "production" ? ["console", "debugger"] : [],
  },
}));
```

### `biome.json`

Write fresh:

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "vcs": {
    "enabled": true,
    "clientKind": "git",
    "useIgnoreFile": true
  },
  "files": {
    "ignoreUnknown": false,
    "ignore": ["dist", "node_modules", ".storybook", "storybook-static"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true
    }
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "always",
      "trailingCommas": "all",
      "arrowParentheses": "always"
    }
  }
}
```

### `tsconfig.json`

Read the existing file, then add path aliases inside `compilerOptions`:

```json
"baseUrl": ".",
"paths": {
  "@/*": ["./src/*"]
}
```

Also ensure `"strict": true` is present.

### `tsconfig.app.json` (if it exists)

Add the same `baseUrl` and `paths` inside `compilerOptions`.

### `package.json` scripts

Read the existing `package.json`, then update the `scripts` block:

```json
"scripts": {
  "dev": "vite --mode develop",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "lint": "biome lint ./src",
  "format": "biome format ./src --write",
  "check": "biome check ./src --write"
}
```

### `.gitignore`

Read if it exists. Ensure these lines are present (add if missing, do not duplicate):

```
# Environment
.env
.env.develop
.env.local
.env.*.local

# Build
dist/
dist-ssr/

# Dependencies
node_modules/

# Logs
*.log
npm-debug.log*

# Editor
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

`.env.example` must NOT be gitignored.

### `.env.example`

```bash
# Copy to .env.develop for local development
# Copy to .env for production

VITE_APP_NAME=my-app
VITE_API_BASE_URL=http://localhost:3000
```

Add Clerk key if Clerk was selected:
```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_key_here
```

### `.env.develop`

```bash
VITE_APP_NAME=my-app
VITE_API_BASE_URL=http://localhost:3000
```

### `.env`

```bash
VITE_APP_NAME=my-app
VITE_API_BASE_URL=https://api.yourdomain.com
```

Both `.env` and `.env.develop` are gitignored.

---

## Step 7 — Create folder structure

```bash
mkdir -p src/{api,components/ui,features,forms,hooks,layouts,lib,pages,router,state,types}
```

If i18n was selected:
```bash
mkdir -p public/locales/en
```

If Storybook was selected, it creates `.storybook/` automatically — skip.

---

## Step 8 — Write starter files

### `src/styles/globals.css`

Check if this file exists (CSS setup may already be done via `/css scaffold`). If not, write:

```css
/* ─── Reset ─────────────────────────────────────────────────────── */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  -webkit-text-size-adjust: 100%;
  color-scheme: dark;
}

body {
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

img, video, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
}

/* Prevent cursor selection on non-editable elements */
button, a, nav, label, [role="button"] {
  user-select: none;
  -webkit-user-select: none;
}

@import "tailwindcss";

@theme {
  --font-body: '<chosen-font>', sans-serif;
  --font-display: '<chosen-font>', sans-serif;
}
```

Replace `<chosen-font>` with the font the user selected in Step 1.

### `src/api/client.ts`

If **Axios** was selected:
```ts
import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});
```

If **native fetch** was selected:
```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json() as Promise<T>;
}
```

### `src/main.tsx`

Read the existing file, then update to wire up TanStack Query and Router:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/styles/globals.css";
import App from "./App";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
```

If Clerk was selected, wrap with `ClerkProvider` outside `QueryClientProvider`.

### `src/router/index.tsx`

```ts
import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";

const rootRoute = createRootRoute();

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <div>Home</div>,
});

const routeTree = rootRoute.addChildren([indexRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register { router: typeof router }
}
```

### i18n setup (if selected)

`public/locales/en/common.json`:
```json
{
  "appName": "My App"
}
```

`src/lib/i18n.ts`:
```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    ns: ["common"],
    defaultNS: "common",
    backend: { loadPath: "/locales/{{lng}}/{{ns}}.json" },
  });

export default i18n;
```

Import in `main.tsx`: `import "@/lib/i18n";`

### Vitest config (if testing selected)

Add to `vite.config.ts` inside the config object:
```ts
test: {
  globals: true,
  environment: "jsdom",
  setupFiles: "./src/test/setup.ts",
},
```

Create `src/test/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

---

## Step 9 — Generate `.cursorrules`

Write `.cursorrules` in the project root:

```
# React 2025 Stack — Project Rules

## Stack
React 19, TypeScript strict, Vite, Zustand, TanStack Query/Router/Forms, Biome, Tailwind v4, Zod, DOMPurify, MUI Icons
[Add: react-i18next] [if i18n selected]
[Add: Clerk / Auth.js] [if auth selected]
[Add: Vitest + React Testing Library + Playwright] [if testing selected]

## Folder structure
src/api/         — TanStack Query client and query/mutation hooks
src/components/  — Pure reusable UI, no app logic
src/components/ui/ — Design system atoms
src/features/    — Self-contained feature modules
src/forms/       — Shared Zod schemas and TanStack Form config
src/hooks/       — Shared custom React hooks
src/layouts/     — Page layout wrappers
src/lib/         — Pure utility functions (no React)
src/pages/       — Route-level page components
src/router/      — TanStack Router config
src/state/       — Zustand stores
src/types/       — Shared TypeScript types
src/styles/      — globals.css and Tailwind entry

## State rules
- Server data (API responses) → TanStack Query
- Cross-feature UI state → Zustand (src/state/)
- Local UI state → useState / useReducer
- Form state → TanStack Forms
- Never put server data in Zustand

## Naming
- Components: PascalCase (UserCard.tsx)
- Hooks: camelCase, use prefix (useUserProfile.ts)
- Zustand stores: camelCase, Store suffix (useCartStore.ts)
- Zod schemas: camelCase, Schema suffix (loginSchema)
- Types/interfaces: PascalCase, Props suffix for component props

## Component rules
- One component per file
- No business logic in components — hooks only
- Props interface named [ComponentName]Props
- DOMPurify before any dangerouslySetInnerHTML
- user-select: none on all non-editable interactive elements

## Import style
- Use @/ alias for all src-relative imports
- Group: external libs → @/ paths → relative paths

## TypeScript
- strict: true always
- No any — use unknown and narrow with Zod or type guards
- All API response shapes typed

## Biome
- Double quotes, 2-space indent, 100-char line width
- Run: bun run check (or npm run check)

## Forms
- TanStack Forms for form state management
- Zod schema for all validation
- DOMPurify for any user-generated HTML content

## Environment
- VITE_ prefix required for client-side env vars
- .env.develop → loaded in dev (vite --mode develop)
- .env → loaded in production
- Never commit .env or .env.develop
```

---

## Step 10 — Install font

If the selected font is a Google Font, add the import to `src/styles/globals.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=<FontName>:wght@300;400;500;600;700&display=swap');
```

Replace `<FontName>` with the URL-encoded font name (e.g. `Plus+Jakarta+Sans`, `Manrope`, `Inter`).

---

## Step 11 — Final install

Run the package manager install to ensure everything is resolved:

```bash
bun install
# or: npm install
```

---

## Step 12 — Report

Summarise everything created:

- Packages installed (core + optional)
- Config files written (vite.config.ts, biome.json, tsconfig.json, .gitignore, .env.*)
- Folders created
- Starter files written
- .cursorrules generated
- What to do next:
  - Run `bun dev` (or `npm run dev`) to start the dev server
  - Run `/css scaffold` to complete the CSS token setup if not already done
  - Run `/git init` to initialise the repo with the dwcy/repo-init hooks
