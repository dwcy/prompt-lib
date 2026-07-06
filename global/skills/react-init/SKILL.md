---
name: react-init
description: Scaffold a new current-stable React project with Vite, TypeScript, Zustand, TanStack, Biome, Tailwind, Zod, and MUI Icons. Use when the user says "new React project", "scaffold a React app", "set up a Vite project", or starts a frontend project on this stack. Asks questions then generates all config files, folder structure, and .cursorrules. Hand architecture questions to @react-architect.
allowed-tools: Bash, Read, Write, Edit, Glob
---

Scaffold a complete current-stable React project. Ask all questions first, then execute everything in order without further interruptions.

Use only `pnpm` or `bun`. Never run `npm`, `npx`, or `yarn`. Use the latest stable versions at execution time; when a package or config format may have changed, verify current docs or registry metadata before writing version-specific setup.

---

## Step 1 — Ask these questions upfront

Ask all at once in a single message:

1. **Package manager** — pnpm or Bun?
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

Use the package manager chosen in Step 1.

**With pnpm:**
```bash
pnpm create vite@latest . -- --template react-ts
```

**With Bun:**
```bash
bun create vite@latest . --template react-ts
```

Do not use npm, npx, or yarn.

---

## Step 4 — Install core dependencies

**With pnpm:**
```bash
pnpm add zustand @tanstack/react-query @tanstack/react-router @tanstack/react-form
pnpm add zod dompurify
pnpm add @mui/icons-material @mui/material @emotion/react @emotion/styled
pnpm add tailwindcss @tailwindcss/vite
pnpm add -D @biomejs/biome @types/node
```

**With Bun:**
```bash
bun add zustand @tanstack/react-query @tanstack/react-router @tanstack/react-form
bun add zod dompurify
bun add @mui/icons-material @mui/material @emotion/react @emotion/styled
bun add tailwindcss @tailwindcss/vite
bun add -d @biomejs/biome @types/node
```

(`dompurify` ships its own types — do not add the deprecated `@types/dompurify` stub.)

---

## Step 5 — Install optional dependencies based on answers

**i18n:**
```bash
pnpm add react-i18next i18next i18next-http-backend i18next-browser-languagedetector
# or:
bun add react-i18next i18next i18next-http-backend i18next-browser-languagedetector
```

**Auth — Clerk:**
```bash
pnpm add @clerk/clerk-react
# or:
bun add @clerk/clerk-react
```

**Auth — Auth.js:**
```bash
pnpm add @auth/core
# or:
bun add @auth/core
```

**Testing:**
```bash
pnpm add -D vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
pnpm add -D @playwright/test
# or:
bun add -d vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
bun add -d @playwright/test
```

**Axios:**
```bash
pnpm add axios
# or:
bun add axios
```

**shadcn/ui:**
```bash
pnpm dlx shadcn@latest init
# or:
bunx shadcn@latest init
```

**Radix UI:**
```bash
pnpm add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tooltip
# or:
bun add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tooltip
```

**DaisyUI:**
```bash
pnpm add -D daisyui
# or:
bun add -d daisyui
```

**Mantine:**
```bash
pnpm add @mantine/core @mantine/hooks
# or:
bun add @mantine/core @mantine/hooks
```

**Storybook** — run after other deps are installed:
```bash
pnpm dlx storybook@latest init --builder vite
# or:
bunx storybook@latest init --builder vite
```

**Turborepo:**
```bash
pnpm add -D turbo
# or:
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

Copy `${CLAUDE_SKILL_DIR}/assets/biome.json` to the project root verbatim (Biome 2.x format: `files.includes` with `!` negations, import organizing under `assist.actions`). If you have verified the current stable Biome schema URL, add `$schema`; otherwise leave it out rather than pinning a stale version.

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

Write `.env.example` only. Do not write `.env`, `.env.develop`, `.env.local`, or any other real env file.

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

### Local env instructions

Tell the user to create `.env.develop` and `.env` manually in UTF-8 encoding (no BOM) if they need local/prod values:

```bash
# .env.develop
VITE_APP_NAME=my-app
VITE_API_BASE_URL=http://localhost:3000

# .env
VITE_APP_NAME=my-app
VITE_API_BASE_URL=https://api.yourdomain.com
```

Both `.env` and `.env.develop` are gitignored and must not be written by the agent.

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

Check if this file exists (CSS setup may already be done via `/css scaffold`). If not, copy `${CLAUDE_SKILL_DIR}/assets/globals.css` and replace `<chosen-font>` with the font the user selected in Step 1.

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

Copy `${CLAUDE_SKILL_DIR}/assets/cursorrules.tmpl` to `.cursorrules` in the project root, then resolve the placeholders: set `<selected-package-manager>`, and keep or drop each `[Add: …] [if … selected]` stack line based on the Step 1 answers.

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
pnpm install
# or:
bun install
```

---

## Step 12 — Report

Summarise everything created:

- Packages installed (core + optional)
- Config files written (vite.config.ts, biome.json, tsconfig.json, .gitignore, .env.example)
- Folders created
- Starter files written
- .cursorrules generated
- What to do next:
  - Run `pnpm dev` or `bun run dev` to start the dev server
  - Run `/css scaffold` to complete the CSS token setup if not already done
  - Run `/git init` to initialise the repo with the dwcy/repo-init hooks
