---
name: ui-component
description: Use when asked to "create a component", "build a UI component", "add a button", "make a card", "create an input", "build a form", "create a modal", "make a badge", "create a nav", or any other frontend UI element. Enforces design language compliance, ships a Preview component alongside every component, enforces correct HTML input semantics, and wires forms to Zustand + Zod validation. Never create a component unless explicitly asked.
allowed-tools: Read, Glob, Grep, Write, Edit
---

**Iron rule**: Do not write component code unless the user explicitly requests a specific component.

---

## Step 1 — Verify Design Language

Before writing any code, locate the active design system:

1. Check `C:\projects\global\DESIGN.md` (project-level design system — should be present).
2. Check `~/.claude/design.md` (global fallback — referenced from AGENTS.md).
3. Check for project-local files: `design-system.md`, `DESIGN.md`, `tokens.md`, `docs/design.md`.

If **no design language exists**, stop and guide the user:

> "No design language found. Before building components, define one. At minimum you need:
> - **Colors**: background layers, primary, secondary/accent, text, error, success
> - **Typography**: font families, size scale, weight scale
> - **Spacing**: base unit (4px or 8px) and scale
> - **Radius**: token set (sm/md/lg/full)
> - **Elevation**: shadow or surface-layer rules
>
> Describe your brand and I'll scaffold a starter design system."

Always state at the top of your response which file is active:
> **Design language**: Premium Digital Agency 2.0 (`global/DESIGN.md`)

---

## Step 2 — Map to Design Tokens

All visual properties must use CSS custom properties. Never use raw hex values in component code.

**Declare in `:root` (or `[data-theme="default"]`):**

```css
:root,
[data-theme="default"] {
  --color-surface:                #161120;
  --color-surface-container-low:  #1e1929;
  --color-surface-container:      #221d2d;
  --color-surface-container-high: #2b2538;
  --color-surface-bright:         #3c3647;
  --color-primary:                #fbabff;
  --color-primary-container:      #eb6afb;
  --color-on-primary:             #580065;
  --color-secondary:              #48e351;
  --color-tertiary-container:     #a191ff;
  --color-on-surface:             #e9def5;
  --color-on-surface-muted:       #a89ec0;
  --color-outline-variant:        #514251;
  --shadow-ambient:               0 0 50px 0 rgba(233,222,245,0.06);
  --shadow-glow-primary:          0 0 20px rgba(251,171,255,0.20);
  --glass-bg:                     rgba(22,17,32,0.60);
  --glass-blur:                   20px;
  --font-display:                 'Plus Jakarta Sans', sans-serif;
  --font-body:                    'Manrope', sans-serif;
  --radius-sm:   0.375rem;
  --radius-md:   0.75rem;
  --radius-lg:   1.25rem;
  --radius-full: 9999px;
  --space-1: 0.25rem; --space-2: 0.5rem;  --space-3: 0.75rem;
  --space-4: 1rem;    --space-6: 1.5rem;  --space-8: 2rem;
  --space-12: 3rem;   --space-16: 4rem;
}
```

Quick token reference:

| UI Element | Token |
|---|---|
| Page background | `var(--color-surface)` |
| Card | `var(--color-surface-container)` |
| Card hover | `var(--color-surface-bright)` + `scale(1.02)` |
| Input background | `var(--color-surface-container-low)` · no border |
| Input focus | Ghost Border at 40% opacity · label → `var(--color-secondary)` |
| Primary button | `var(--color-primary)` fill · `var(--color-on-primary)` text · `var(--radius-md)` |
| Borders | Forbidden — use surface color shifts |
| Ghost Border | `outline-variant` (#514251) at 15% opacity |
| Nav/floats | `var(--glass-bg)` + `backdrop-filter: blur(var(--glass-blur))` |
| Dividers | Forbidden — use `var(--space-6)` / `var(--space-8)` vertical gap |

---

## Step 3 — Theme Preparation

Every component must support theme switching without code changes.

- Use CSS variables for **every** color, background, shadow, and border value.
- Never inline raw hex in JSX `style` props or CSS-in-JS.
- Theme switching is a single attribute change at the root:

```ts
// themeStore.ts
export const useThemeStore = create<{ theme: string; setTheme: (t: string) => void }>()(
  subscribeWithSelector((set) => ({
    theme: 'default',
    setTheme: (theme) => {
      document.documentElement.setAttribute('data-theme', theme)
      set({ theme })
    },
  }))
)
```

Alternative themes override the same variable names under a `[data-theme="X"]` selector. Components require zero changes.

If the project uses Tailwind v4, wire tokens in `globals.css`:
```css
@theme {
  --color-surface: #161120;
  --color-primary: #fbabff;
  /* etc. */
}
```

---

## Step 4 — Build the Component

### Dual export (required for every component)

**1. The component** — production-ready, all values from CSS variables.
**2. `<ComponentNamePreview />`** — renders all meaningful states side by side.

```tsx
// PrimaryButton.tsx

export function PrimaryButton({ children, disabled, onClick }: PrimaryButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'var(--color-primary)',
        color: 'var(--color-on-primary)',
        borderRadius: 'var(--radius-md)',
        border: 'none',
        padding: `var(--space-2) var(--space-4)`,
        fontFamily: 'var(--font-body)',
        fontWeight: 600,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        transition: 'box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        if (!disabled) e.currentTarget.style.boxShadow = 'var(--shadow-glow-primary)'
      }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none' }}
    >
      {children}
    </button>
  )
}

export function PrimaryButtonPreview() {
  return (
    <div style={{ background: 'var(--color-surface)', padding: 'var(--space-8)', display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
      <PrimaryButton onClick={() => {}}>Default</PrimaryButton>
      <PrimaryButton disabled onClick={() => {}}>Disabled</PrimaryButton>
    </div>
  )
}
```

Preview must include: default, hover (note in comment), disabled, error, loading, all variants/sizes.

### Input type semantics (required)

| Purpose | `type=` |
|---|---|
| Email | `"email"` |
| Password | `"password"` |
| Number | `"number"` |
| Phone | `"tel"` |
| URL | `"url"` |
| Date | `"date"` |
| Date + time | `"datetime-local"` |
| Time | `"time"` |
| Search | `"search"` |
| Checkbox | `"checkbox"` |
| Radio | `"radio"` |
| File | `"file"` |
| Color | `"color"` |
| Slider | `"range"` |
| Hidden | `"hidden"` |
| Free text only | `"text"` |

Never use `type="text"` for emails, phones, URLs, or numbers.

---

## Step 5 — Forms: Zustand + Zod

All forms use a Zustand store with `subscribeWithSelector` and a Zod schema.

```ts
// src/frontend/src/store/exampleForm.store.ts
import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { z } from 'zod'

const Schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'At least 8 characters'),
})

type Fields = z.infer<typeof Schema>
type Errors = Partial<Record<keyof Fields, string>>

interface State { fields: Fields; errors: Errors; isSubmitting: boolean }
interface Actions {
  setField: <K extends keyof Fields>(k: K, v: Fields[K]) => void
  validateField: (k: keyof Fields) => void
  submit: () => Promise<void>
  reset: () => void
}

const initial: Fields = { email: '', password: '' }

export const useExampleFormStore = create<State & Actions>()(
  subscribeWithSelector((set, get) => ({
    fields: initial,
    errors: {},
    isSubmitting: false,

    setField: (k, v) => set((s) => ({ fields: { ...s.fields, [k]: v } })),

    validateField: (k) => {
      const r = Schema.shape[k].safeParse(get().fields[k])
      set((s) => ({
        errors: { ...s.errors, [k]: r.success ? undefined : r.error.errors[0].message },
      }))
    },

    submit: async () => {
      const r = Schema.safeParse(get().fields)
      if (!r.success) {
        const errs: Errors = {}
        r.error.errors.forEach((e) => { const k = e.path[0] as keyof Fields; if (!errs[k]) errs[k] = e.message })
        set({ errors: errs })
        return
      }
      set({ isSubmitting: true })
      // await apiCall(r.data)
      set({ isSubmitting: false, fields: initial, errors: {} })
    },

    reset: () => set({ fields: initial, errors: {} }),
  }))
)

export const selectFields = (s: State & Actions) => s.fields
export const selectErrors = (s: State & Actions) => s.errors
export const selectIsSubmitting = (s: State & Actions) => s.isSubmitting
```

Rules:
- Validate on `blur` per field, full schema on submit — not on every keystroke
- Show errors inline below the input, use `aria-invalid` + `aria-describedby`
- Store files live in `src/frontend/src/store/` — one file per form

---

## Step 6 — Deliver

After writing the component, state:
1. **Design tokens applied** — which variable was used for each visual property
2. **Preview usage** — how to render `<ComponentNamePreview />`
3. **Form stores** (if applicable) — which Zod schema fields map to which inputs
