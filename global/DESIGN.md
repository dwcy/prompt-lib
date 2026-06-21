# Design System: Premium Digital Agency 2.0

## 1. Overview & Creative North Star: "The Neon Curator"

This design system moves away from the static, boxed layouts of traditional corporate sites and into the realm of high-end digital editorialism. The Creative North Star, **"The Neon Curator,"** blends the deep, mysterious foundations of a dark-mode workspace with high-energy, acidic pops of color.

We break the "template" look by prioritizing **intentional asymmetry** and **tonal depth**. Rather than containing content in rigid grids, we let elements breathe through expansive whitespace (the "Oxy-Grid" approach) and use overlapping typography to create a sense of motion and craft. This is not just a UI; it is a premium gallery for digital excellence.

---

## 2. Colors & Surface Philosophy

The palette is rooted in a deep obsidian (`#161120`), punctuated by high-chroma accents of Electric Pink (`#EB6AFB`) and Acid Green (`#48E351`).

### The "No-Line" Rule

Traditional 1px solid borders are strictly prohibited for sectioning. Structural boundaries must be defined solely through background color shifts.

- **Transitioning Areas:** Use a shift from `surface` to `surface-container-low` to signal a new content block.
- **Signature Textures:** For Hero sections or primary CTAs, use a subtle linear gradient: `primary` (#fbabff) to `primary-container` (#eb6afb) at a 135-degree angle. This adds "visual soul" that flat hex codes cannot achieve.

### Surface Hierarchy & Nesting

Treat the UI as a series of physical layers. Each "inner" container should move up or down the tier to define importance without lines.

- **Base Level:** `surface` (#161120)
- **Secondary Content:** `surface-container-low` (#1e1929)
- **Interactive Cards:** `surface-container` (#221d2d)
- **High-Priority Overlays:** `surface-bright` (#3c3647)

### The "Glass & Gradient" Rule

To achieve the "Agency 2.0" feel, use **Glassmorphism** for floating elements (Navigation bars, Tooltips, Floating Action Buttons).

- **Formula:** `surface` color at 60% opacity + 20px `backdrop-blur`. This allows the vibrant accents to bleed through the UI, making the experience feel integrated.

---

## 3. Typography: The Editorial Voice

We use a high-contrast pairing of **Plus Jakarta Sans** for expressive moments and **Manrope** for functional clarity.

- **Display (Plus Jakarta Sans):** Large, bold, and unapologetic. Use `display-lg` (3.5rem) with `-0.04em` letter spacing for hero headlines. This conveys an authoritative, boutique agency voice.
- **Headlines (Plus Jakarta Sans):** Used for section titles. Ensure `headline-lg` (2rem) has ample top-padding (`spacing-16`) to maintain the "editorial" feel.
- **Body (Manrope):** Our workhorse. `body-lg` (1rem) is the standard for readability. Use `body-light` (weight 300) for large blocks of descriptive text to increase the "Premium" aesthetic.
- **Labels (Manrope):** All-caps with `0.1em` tracking. Used for small metadata or eyebrows above headlines to provide a technical, "lab-certified" look.

---

## 4. Elevation & Depth

In this system, depth is organic, not artificial. We use **Tonal Layering** instead of heavy shadows.

- **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section. The subtle contrast creates a soft, natural lift.
- **Ambient Shadows:** If an element must "float" (e.g., a modal), use an ultra-diffused shadow:
  - _Blur:_ 40px–60px.
  - _Opacity:_ 6%.
  - _Color:_ Use a tinted version of `on-surface` (the lavender-grey `#e9def5`) to mimic natural ambient light.
- **The "Ghost Border" Fallback:** If a border is required for accessibility, it must be a **Ghost Border**: Use `outline-variant` (#514251) at 15% opacity. Never use 100% opaque borders.

---

## 5. Components

### Buttons

- **Primary:** A vibrant `primary` (#fbabff) fill with `on-primary` (#580065) text. Radius: `md` (0.75rem). Use a subtle glow effect on hover (box-shadow using the primary color at 20% opacity).
- **Secondary:** `surface-container-highest` background with a `Ghost Border`.
- **Tertiary:** Text-only in `secondary` (#48e351) with an animated underline that expands from the center on hover.

### Cards & Lists

- **The Divider Ban:** Strictly forbid 1px horizontal lines. Use `spacing-6` or `spacing-8` of vertical white space to separate items.
- **Interaction:** Cards should subtly scale (1.02x) and shift background color to `surface-bright` on hover.

### Input Fields

- **Styling:** Use `surface-container-low` as the background. No borders.
- **Focus State:** A 2px "Ghost Border" becomes 40% opaque, and the `label-sm` shifts to the `secondary` color.

### Interactive Chips

- **Action Chips:** High-pill shape (`full` radius). Use `tertiary-container` (#a191ff) with `on-tertiary-container` text for a sophisticated, low-contrast tech look.

---

## 6. Do’s and Don’ts

### Do

- **Do** use asymmetrical margins. If a headline is left-aligned, try indenting the body text to its right to create a dynamic "path" for the eye.
- **Do** utilize the `secondary` (Acid Green) color for success states and "High-Energy" callouts only.
- **Do** embrace "Oxy-Grid" spacing. If you think there is enough whitespace, add one more increment from the spacing scale.

### Don’t

- **Don’t** use pure black (#000000). Always use the deep purple `surface` (#161120) to maintain tonal depth.
- **Don’t** use standard "Drop Shadows" from software defaults. They feel "cheap" and break the Premium Digital Agency 2.0 aesthetic.
- **Don’t** center-align long blocks of text. Editorial layouts are most effective when anchored to a strong left or right vertical axis.

---

## 7. Signature Element: The "Lab" Overlay

To honor the creative essence of the brand, designers are encouraged to use "Micro-Grids"—small, 10% opacity dot-matrix patterns—in the background of `surface-container` elements. This provides a tactile, "blueprinted" feel to the creative work being displayed.

---

## 8. Motion & Interaction: CSS-First

Motion is part of the "Premium Digital Agency 2.0" feel — but it belongs in CSS, not JavaScript. Animations, transitions, hover/scroll/reveal effects, and state toggles must be implemented in CSS by default. Modern CSS (2024–2025) expresses nearly all of this declaratively, and CSS-driven motion runs on the compositor, degrades gracefully, and stays in sync with the design tokens.

### Default to CSS

- **Transitions & animations:** `transition` and `@keyframes`. Animate `transform`/`opacity` for the smooth, premium feel; use `@property` to animate custom properties (e.g. gradient angles, color stops).
- **Scroll reveals & parallax:** scroll-driven animations (`animation-timeline: view()` / `scroll()`) — not scroll listeners or `IntersectionObserver`.
- **Parent / sibling state:** `:has()` (e.g. lift a card when its checkbox is checked) — not class toggling.
- **Disclosure / accordions:** native `<details>` styled with `::details-content` — not click handlers.
- **Tooltips / popovers / menus:** the `popover` attribute + CSS anchor positioning — not show/hide JS.
- **Component responsiveness:** container queries — not `ResizeObserver`.
- **View Transitions:** the CSS View Transitions API for cross-state morphs.

### Reserve JavaScript for genuine logic

Data fetching and async state, complex orchestration that branches on runtime data, gesture physics (momentum, drag inertia), focus management/ARIA wiring beyond what native elements provide, and persisting state across reloads. If the only reason to reach for JS is "toggle a class on an event," a CSS state selector almost certainly already covers it.

Always honor `@media (prefers-reduced-motion: reduce)` — provide a no-animation path that leaves content fully usable.

For the technique catalog, the effect → CSS-approach → when-JS-is-needed matrix, and copy-ready snippets, use the [`/css-guide`](skills/css-guide/SKILL.md) skill. For token scaffolding use [`/css`](skills/css.md).
