---
name: lovable-cleanup
description: Remove all Lovable/GPTEngineer scaffolding from a project — strips lovable-tagger from package.json and vite.config.ts, cleans index.html metadata, removes injected data-lovable-id and data-gptengineer-id attributes from all source files, rewrites README, and regenerates the lockfile.
allowed-tools: Read, Edit, Glob, Bash
---

Remove all Lovable/GPTEngineer scaffolding from this project. Work through each step in order. Read every file before editing it.

---

## Step 1 — Confirm scope

Run in parallel:

```bash
grep -r "lovable\|gptengineer\|lov-" --include="*.json" --include="*.ts" --include="*.html" -l
grep -r "data-lovable-id\|data-gptengineer-id" --include="*.tsx" --include="*.jsx" --include="*.html" -l
```

Report: which files contain Lovable references, and how many attribute injections exist. Proceed without waiting for confirmation.

---

## Step 2 — package.json

Read `package.json`. Remove any entry whose key or value contains `lovable-tagger` or `gptengineer` from `devDependencies` and `dependencies`. Do not touch any other dependency.

---

## Step 3 — vite.config.ts

Read `vite.config.ts`. Make these targeted removals — nothing else:

- Remove the import line: `import { componentTagger } from "lovable-tagger";`
- Remove any line in the `plugins` array that calls `componentTagger(...)` — including any surrounding conditional (e.g. `mode === 'development' && componentTagger()`)
- If the conditional wrapper is an `&&` expression and removing it leaves the array entry empty or malformed, remove the whole entry cleanly

Do not reformat the rest of the file.

---

## Step 4 — index.html

Read `index.html`. Remove or replace the following — nothing else:

**Remove these meta tags entirely:**
```html
<meta name="author" content="Lovable" />
<meta property="og:description" content="..." />   <!-- only if Lovable-generated -->
<meta property="og:image" content="..." />          <!-- only if pointing to lovable/gptengineer CDN -->
<meta name="twitter:site" content="@lovable_dev" />
<meta name="twitter:image" content="..." />         <!-- only if pointing to lovable/gptengineer CDN -->
```

**Remove the gptengineer script tag:**
```html
<script src="https://cdn.gpteng.co/gptengineer.js" ...></script>
```

**Update title and description:**
- Ask the user: "What should the app title and description be in index.html?" 
- Wait for the answer, then update `<title>` and the `<meta name="description">` tag

Leave all other tags untouched.

---

## Step 5 — Strip injected attributes from source files

Lovable-tagger injects `data-lovable-id` and `data-gptengineer-id` attributes into JSX/TSX/HTML during build. Find and remove them from all source files.

```bash
# Find all affected files
grep -rl "data-lovable-id\|data-gptengineer-id\|lovable-id=" --include="*.tsx" --include="*.jsx" --include="*.html" .
```

For each matched file, read it and remove:
- `data-lovable-id="..."` attributes (any value)
- `data-gptengineer-id="..."` attributes (any value)
- Standalone `lovable-id="..."` attributes

Remove only the attribute — preserve the element, its other attributes, and surrounding whitespace.

Also search for any element IDs or class names that look like generated Lovable slugs:
```bash
grep -rn 'id="[^"]*lov[^"]*"' --include="*.tsx" --include="*.jsx" --include="*.html" .
```

Report what is found. If the IDs look like content IDs (e.g. `id="lov-button-1"`, `id="lovable-hero"`) and are not referenced anywhere else in the codebase via `getElementById` or CSS selectors, remove them. If they are referenced, flag them to the user instead of removing.

---

## Step 6 — README.md

Ask the user:

> What should the new README say? Give me: project name, one-line description, and any setup/run instructions I should include.

Wait for their answer. Then rewrite `README.md` completely — no Lovable references, no "built with Lovable" badges, no gptengineer links. Use the information provided.

---

## Step 7 — Regenerate lockfile

Detect the package manager:

```bash
ls package-lock.json yarn.lock pnpm-lock.yaml bun.lockb bun.lock 2>/dev/null
```

Run the matching install command to regenerate the lockfile with the removed dependency. Do not use npm or yarn. If the project only has `package-lock.json` or `yarn.lock`, stop and ask whether to migrate to `pnpm` or `bun`.

| Lockfile | Command |
|---|---|
| `package-lock.json` | Stop and ask to migrate to `pnpm` or `bun` |
| `yarn.lock` | Stop and ask to migrate to `pnpm` or `bun` |
| `pnpm-lock.yaml` | `pnpm install` |
| `bun.lockb` | `bun install` |
| `bun.lock` | `bun install` |

---

## Step 8 — Verify

Run in parallel:

```bash
grep -r "lovable\|gptengineer" --include="*.ts" --include="*.tsx" --include="*.jsx" --include="*.html" --include="*.json" -l
grep -r "data-lovable-id\|data-gptengineer-id" --include="*.tsx" --include="*.jsx" --include="*.html" .
```

If any matches remain, report exactly what they are and where. Do not silently ignore them.

Report a final summary: files changed, attributes removed, lockfile regenerated.
