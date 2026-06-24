---
name: css
description: Scaffold CSS for a frontend project. /css scaffold — sets up globals.css with reset and design tokens. /css Button — generates Button.module.css alongside the component file.
allowed-tools: Read, Write, Edit, Glob
---

When `/css` is invoked:

- **No argument** → ask: "Scaffold full globals.css, or generate a CSS module? (scaffold / component name)"
- **`/css scaffold`** → set up the full CSS architecture for this project
- **`/css <ComponentName>`** → generate `[ComponentName].module.css` in the component's directory

---

## /css scaffold

1. Glob the file tree to detect the framework:
   - `app/layout.tsx` → Next.js App Router
   - `pages/_app.tsx` → Next.js Pages Router
   - `src/main.tsx` or `src/index.tsx` → Vite / CRA
2. Check if `styles/globals.css` exists — read it first if it does
3. Create (or replace) `styles/globals.css` with the full template below
4. Open the entry point file and verify `import '../styles/globals.css'` (or equivalent path) exists — add it if missing
5. Report what was created and the CSS module convention to follow

### globals.css to write

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

p, h1, h2, h3, h4, h5, h6 {
  overflow-wrap: break-word;
}

/* ─── Design tokens ──────────────────────────────────────────────── */
:root {
  /* Colors */
  --color-surface:                #161120;
  --color-surface-container-low:  #1e1929;
  --color-surface-container:      #221d2d;
  --color-surface-bright:         #3c3647;
  --color-primary:                #fbabff;
  --color-primary-container:      #eb6afb;
  --color-on-primary:             #580065;
  --color-secondary:              #48e351;
  --color-on-surface:             #e9def5;
  --color-outline-variant:        #514251;

  /* Typography */
  --font-display: 'Plus Jakarta Sans', sans-serif;
  --font-body:    'Manrope', sans-serif;

  /* Spacing (0.25rem increments) */
  --size-1:  0.25rem;
  --size-2:  0.5rem;
  --size-3:  0.75rem;
  --size-4:  1rem;
  --size-6:  1.5rem;
  --size-8:  2rem;
  --size-12: 3rem;
  --size-16: 4rem;
  --size-24: 6rem;

  /* Border radius */
  --radius-sm:   0.25rem;
  --radius-md:   0.75rem;
  --radius-lg:   1.5rem;
  --radius-full: 9999px;

  /* Shadows — diffused, tinted with on-surface lavender */
  --shadow-sm: 0 2px  12px 0 rgba(233, 222, 245, 0.04);
  --shadow-md: 0 4px  32px 0 rgba(233, 222, 245, 0.06);
  --shadow-lg: 0 8px  60px 0 rgba(233, 222, 245, 0.08);

  /* Z-index scale */
  --z-base:     0;
  --z-raised:   10;
  --z-dropdown: 100;
  --z-sticky:   200;
  --z-modal:    300;
  --z-toast:    400;
}

/* ─── Light theme override ───────────────────────────────────────── */
[data-theme="light"] {
  color-scheme: light;

  --color-surface:                #faf8ff;
  --color-surface-container-low:  #f3f0fa;
  --color-surface-container:      #ece8f4;
  --color-surface-bright:         #ffffff;
  --color-on-surface:             #1c1a27;
  --color-outline-variant:        #c9c3d0;
}

/* ─── Base element styles ────────────────────────────────────────── */
body {
  background-color: var(--color-surface);
  color: var(--color-on-surface);
  font-family: var(--font-body);
  font-size: 1rem;
  font-weight: 400;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-display);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

a {
  color: var(--color-primary);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}
```

---

## /css \<ComponentName\>

1. Glob for the component file (`**/<ComponentName>.*`) to locate its directory
2. If the component doesn't exist yet, ask where to place it before proceeding
3. Read the component file briefly to understand its props and intended variants
4. Create `[ComponentName].module.css` in the same directory as the component
5. All values must reference CSS variables — never hardcode hex, rem, or font names

### Module structure to follow

```css
/* Root — always the outermost wrapper */
.root { }

/* Variants — applied alongside .root via cx(styles.root, styles.primary) */
.primary { }
.secondary { }

/* States — applied alongside .root */
.root.disabled { }
.root.loading { }
```

### Button.module.css reference

```css
.root {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--size-2);
  padding: var(--size-2) var(--size-4);
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.875rem;
  font-weight: 600;
  transition: background-color 150ms ease, box-shadow 150ms ease;
}

.primary {
  background-color: var(--color-primary);
  color: var(--color-on-primary);
}

.primary:hover {
  box-shadow: 0 0 0 6px color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.secondary {
  background-color: var(--color-surface-container);
  color: var(--color-on-surface);
  outline: 1px solid color-mix(in srgb, var(--color-outline-variant) 15%, transparent);
  outline-offset: -1px;
}

.secondary:hover {
  background-color: var(--color-surface-bright);
}

.tertiary {
  background-color: transparent;
  color: var(--color-secondary);
  position: relative;
  padding-bottom: calc(var(--size-2) + 1px);
}

.tertiary::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  right: 50%;
  height: 1px;
  background-color: var(--color-secondary);
  transition: left 200ms ease, right 200ms ease;
}

.tertiary:hover::after {
  left: 0;
  right: 0;
}

.root.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}
```
