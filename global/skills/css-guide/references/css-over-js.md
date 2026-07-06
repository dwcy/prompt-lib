# CSS-over-JS decision matrix

For each common interaction, the modern CSS approach (and the property that makes it work) versus the narrow case where JavaScript is actually required. Default to the CSS column. Reach for JS only when the "JS genuinely required" condition holds.

All examples assume the design tokens from [`/css scaffold`](../../css/SKILL.md) exist (`--color-*`, `--size-*`, `--radius-*`). Honor `@media (prefers-reduced-motion: reduce)` whenever you add motion.

| Effect | CSS approach (modern property) | JS genuinely required when… |
|---|---|---|
| **Hover / focus state change** | `transition` on the changing properties; pseudo-classes `:hover`, `:focus-visible` | never — this is pure CSS |
| **Entrance / exit animation** | `@keyframes` + `animation`; animate transforms/opacity. For animating a custom property, register it with `@property` | the sequence branches on fetched data |
| **Scroll-triggered reveal / fade-in** | `animation-timeline: view()` with `animation-range` — element animates as it enters the viewport | you need a one-shot callback to run non-visual logic (analytics, lazy data load) |
| **Scroll progress bar / parallax** | `animation-timeline: scroll()` bound to a scroll container | physics-based momentum or velocity-dependent behavior |
| **Accordion / disclosure / FAQ** | native `<details>`/`<summary>`; animate open/close via `::details-content` and `interpolate-size: allow-keywords`; style open state with `details:has(> summary:hover)` or `details[open]` | you must enforce "only one open at a time" with persistence, or sync open state to a store |
| **Tabs** | radio inputs + `:checked` + sibling selectors, or `:target`; style panels via `:has()` | tab content is lazy-loaded or order is dynamic |
| **Tooltip / popover / dropdown menu** | the `popover` attribute + `popovertarget` button; position with CSS anchor positioning; no show/hide script | content is fetched on open, or complex keyboard nav beyond what `popover` provides |
| **Style a parent from child state** (card with checked checkbox, form with invalid input) | `:has()` — e.g. `.card:has(:checked)`, `form:has(:invalid)` | the state must also drive non-visual logic (submit gating, network calls) |
| **Style based on sibling/preceding element** | `:has()` with sibling combinators — e.g. `label:has(+ input:focus)` | n/a for styling; JS only for the logic the state feeds |
| **Responsive component** (restyle by own width, not viewport) | container queries: `container-type: inline-size` on the wrapper, `@container (min-width: …)` on children | layout depends on measured content that CSS units (`cqi`, `ch`) can't express |
| **Theme / dark mode** | `prefers-color-scheme` + token overrides; optional `[data-theme]` attribute hook | user-chosen theme must persist across reloads (then JS only writes the attribute; CSS still styles) |
| **Centering / equal columns / responsive grid** | Flexbox or Grid `repeat(auto-fit, minmax(…, 1fr))` — no breakpoints | never — pure CSS |
| **Derived hover/active colors** | `color-mix(in srgb, var(--color-primary) 85%, black)` or relative color syntax | never — pure CSS |
| **Counting / numbering** | CSS counters (`counter-reset`, `counter-increment`, `::marker`) | the count comes from runtime data, not document order |

## Anti-patterns to flag

- Adding a `scroll` event listener to fade elements in → use `animation-timeline: view()`.
- `IntersectionObserver` whose only job is toggling a `.visible` class → use scroll-driven animation or `:has()`.
- `onClick` that toggles `aria-expanded` and a class on an accordion → use `<details>`.
- `ResizeObserver` that swaps a class to change a card's layout → use container queries.
- JS that reads a checkbox and adds a class to its parent → use `parent:has(:checked)`.
- Hand-computed lighter/darker color variants as separate hex tokens → derive with `color-mix()`.

## Browser-support note

The properties above are current (2024–2025) and broadly shipped in evergreen browsers. `:has()`, container queries, `color-mix()`, and `popover` are baseline-available; scroll-driven animations and `interpolate-size`/`::details-content` are the newest — confirm support and provide a graceful no-animation fallback (the content stays visible/usable without the enhancement). When unsure, `WebFetch` the relevant guide in [`css-tricks-index.md`](css-tricks-index.md).
