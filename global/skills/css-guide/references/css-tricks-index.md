# css-tricks.com guide catalog

Distilled index of the css-tricks.com guides relevant to CSS-first technique work. Each entry: what it does + the canonical URL. Grouped by concern. Source index: https://css-tricks.com/guides/

Use these URLs as the authoritative reference when advising on a technique. `WebFetch` a URL to confirm current syntax or browser support before recommending an unfamiliar property.

## Layout

- **Flexbox — complete guide** — one-dimensional layout: distribute and align items along a single axis (`display:flex`, `flex-direction`, `justify-content`, `align-items`, `flex-wrap`, `gap`, `flex-grow/shrink/basis`, `align-self`). https://css-tricks.com/snippets/css/a-guide-to-flexbox/
- **Grid — complete guide** — two-dimensional layout: rows and columns together (`grid-template-columns/rows`, `gap`, `grid-template-areas`, `repeat()`, `minmax()`, `fr`, `place-items`; `auto-fit`/`auto-fill` for responsive grids with no media queries). https://css-tricks.com/complete-guide-css-grid-layout/
- **Centering in CSS** — the definitive lookup for vertical/horizontal centering across contexts. https://css-tricks.com/centering-css-complete-guide/
- **Calc()** — runtime math mixing units (`calc(100% - var(--size-8))`) for fluid sizing without JS measurement. https://css-tricks.com/a-complete-guide-to-calc-in-css/
- **Length units** — when to use `rem`, `ch`, `vw`/`vh`/`dvh`, `fr`, and container query units (`cqw`/`cqi`). https://css-tricks.com/css-length-units/

## Modern selectors & queries

- **CSS selectors** — `:is()` / `:where()` to collapse selector lists (differ on specificity), the `:has()` relational/parent selector for styling an element based on its descendants or siblings, and CSS nesting with `&`. https://css-tricks.com/css-selectors/
- **Container queries** — register an element as a query container (`container-type: inline-size`, `container-name`, shorthand `container:`) and style its children by the container's size with `@container`. Solves component portability that viewport media queries can't. https://css-tricks.com/css-container-queries/
- **Media queries** — viewport-level responsiveness, `prefers-reduced-motion`, `prefers-color-scheme`. https://css-tricks.com/a-complete-guide-to-css-media-queries/
- **Cascade layers** — `@layer` to order specificity deliberately rather than fighting it. https://css-tricks.com/css-cascade-layers/
- **Anchor positioning** — tether one element to another (tooltips, popovers) purely in CSS. https://css-tricks.com/css-anchor-positioning-guide/

## Animation & motion

- **Custom properties** — `--var` reusable values through the cascade; crucially, `@property` registers a *typed* custom property (`syntax`, `inherits`, `initial-value`) so it can be **animated** in `@keyframes` (untyped custom properties cannot animate between values). https://css-tricks.com/a-complete-guide-to-custom-properties/
- **Color functions** — `color-mix(in srgb, …)` to derive hover/active tints from a base token, relative color syntax (`from`) to shift channels, and the modern `oklch()`/`lab()` spaces. https://css-tricks.com/css-color-functions/
- **Gradients** — animatable and `@property`-driven gradients for signature surfaces. https://css-tricks.com/a-complete-guide-to-css-gradients/

> Scroll-driven animations (`animation-timeline: scroll()` / `view()`) and View Transitions are current (2024–2025) CSS but not yet a standalone entry in the css-tricks guide index. Their decision-level usage is documented in [`css-over-js.md`](css-over-js.md).

## Interaction without JS

- **Links and buttons** — semantics of when to use `<a>` vs `<button>`, the foundation for accessible CSS-driven interaction. https://css-tricks.com/a-complete-guide-to-links-and-buttons/
- **Data attributes** — `[data-state="open"]` style hooks that CSS reads directly, avoiding class-toggling JS. https://css-tricks.com/a-complete-guide-to-data-attributes/
- **Dark mode** — `prefers-color-scheme` + `color-scheme` and token overrides for theming with no JS toggle required. https://css-tricks.com/a-complete-guide-to-dark-mode-on-the-web/
