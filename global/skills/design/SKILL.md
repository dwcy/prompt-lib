---
name: design
description: Loads the Premium Digital Agency 2.0 design system into context. Use before building UI components, choosing colors, typography, or spacing, reviewing designs, or making any styling decision.
---

Apply the following design system for all UI work in this session. Every decision about color, typography, spacing, elevation, and component behavior must follow these rules.

The machine-readable token sheet (all CSS custom properties, including the light theme) is the single source of truth at [`references/tokens.css`](references/tokens.css) — read it when writing actual CSS; never restate token values elsewhere.

---

## Creative North Star: "The Neon Curator"

Deep, mysterious dark-mode foundation with high-energy acidic pops of color. Intentional asymmetry over rigid grids. Expansive whitespace ("Oxy-Grid"). Overlapping typography for motion and craft. This is a premium gallery for digital excellence — not a template.

---

## Colors & Surface Philosophy

| Token | Value | Role |
|---|---|---|
| `surface` | `#161120` | Base level — never use pure black |
| `surface-container-low` | `#1e1929` | Secondary content areas |
| `surface-container` | `#221d2d` | Interactive cards |
| `surface-bright` | `#3c3647` | High-priority overlays, card hover |
| `primary` | `#fbabff` | Electric Pink — primary CTAs |
| `primary-container` | `#eb6afb` | Signature gradient end |
| `on-primary` | `#580065` | Text on primary backgrounds |
| `secondary` | `#48e351` | Acid Green — success, high-energy callouts only |
| `on-surface` | `#e9def5` | Body text, lavender-grey |
| `outline-variant` | `#514251` | Ghost borders only, at 15% opacity |

### The No-Line Rule
Traditional 1px solid borders are **strictly prohibited**. Define structure through background color shifts only.
- Transitioning areas: shift from `surface` to `surface-container-low`
- Hero / primary CTA: linear gradient `primary` → `primary-container` at 135°

### The Glass & Gradient Rule
Floating elements (navbars, tooltips, FABs): `surface` at 60% opacity + `backdrop-blur: 20px`.

---

## Typography

| Role | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Display | Plus Jakarta Sans | 3.5rem | Bold | `letter-spacing: -0.04em` — hero headlines |
| Headline | Plus Jakarta Sans | 2rem | Bold | `padding-top: spacing-16` for editorial feel |
| Body | Manrope | 1rem | 300 (light) | Large descriptive blocks — weight 300 signals premium |
| Label | Manrope | small | any | All-caps, `letter-spacing: 0.1em` — metadata, eyebrows |

---

## Elevation & Depth

Use tonal layering — **no default drop shadows**.

- Place `surface-container-lowest` cards on `surface-container-low` sections for natural lift
- Floating elements (modals): `box-shadow: 0 40px 60px rgba(233,222,245,0.06)`
- Ghost Border fallback (accessibility only): `outline-variant` at 15% opacity — never 100%

---

## Components

### Buttons
- **Primary:** `primary` fill, `on-primary` text, `border-radius: 0.75rem`, hover glow `box-shadow: 0 0 0 6px rgba(251,171,255,0.2)`
- **Secondary:** `surface-container-highest` bg + Ghost Border
- **Tertiary:** text-only in `secondary`, animated underline expands from center on hover

### Cards
- No dividers — use `gap: 1.5rem` or `gap: 2rem` to separate items
- Hover: scale `1.02x` + background shifts to `surface-bright`

### Inputs
- Background: `surface-container-low`, no border
- Focus: Ghost Border becomes 40% opacity, label shifts to `secondary` color

### Chips
- High-pill shape (`border-radius: 9999px`)
- `tertiary-container` (`#a191ff`) background with `on-tertiary-container` text

---

## Spacing (Oxy-Grid)

When you think there is enough whitespace — add one more increment. Anchored to 0.25rem base:

`0.25` `0.5` `0.75` `1` `1.5` `2` `3` `4` `6` `8` `12` `16` `24` rem

---

## Do's and Don'ts

**Do:**
- Asymmetrical margins — if a headline is left-aligned, indent body text further right
- Use `secondary` (Acid Green) for success and high-energy callouts only
- Embrace Oxy-Grid spacing — more whitespace than feels comfortable

**Don't:**
- Never use `#000000` — always use `surface` (`#161120`)
- Never use default software drop shadows
- Never center-align long text blocks — anchor to a strong left or right axis

---

## Signature Element: The Lab Overlay

For `surface-container` elements: subtle dot-matrix pattern at 10% opacity in the background. Provides a tactile, blueprinted feel.

```css
background-image: radial-gradient(circle, var(--color-on-surface) 1px, transparent 1px);
background-size: 20px 20px;
opacity: 0.1;
```
