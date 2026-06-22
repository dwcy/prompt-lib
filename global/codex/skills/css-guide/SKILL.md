---
name: css-guide
description: CSS-first techniques & animations (prefer CSS over JS). Use when building animations, transitions, hover/scroll/reveal effects, layout, state toggles, or asking how to do X in CSS instead of JavaScript; references css-tricks.com guides. Complements /css (scaffolder) and @frontend-css.
allowed-tools: Read, Write, Edit, Glob, WebFetch
---

This skill is a technique guide, not a scaffolder. It exists to push you toward solving motion, interaction, layout, and state-toggle problems in **CSS first**, reaching for JavaScript only when CSS genuinely cannot express the behavior. Modern CSS (2024–2025) has absorbed a large share of what used to require JS: keyframes, transitions, scroll-driven animation, the `:has()` parent selector, container queries, the `popover` attribute, and View Transitions.

For project-specific scaffolding (globals.css, design tokens, CSS modules) use [`/css`](../css.md). For deeper CSS architecture work, hand off to `@frontend-css`. This skill is the "which technique, and why CSS over JS" layer that sits on top of both.

## The CSS-first decision rule

Before writing a single line of JavaScript for a visual or interactive effect, ask: **can CSS do this?** For the following, the answer is almost always yes — reach for CSS:

- **Animation / transition** — entrance/exit, hover, focus, color/size/transform changes → `transition`, `@keyframes`, `@property` (for animating custom properties).
- **Scroll-triggered reveal / parallax / progress bar** → scroll-driven animations (`animation-timeline: view()` / `scroll()`). No `IntersectionObserver`, no scroll listener.
- **Accordion / disclosure** → native `<details>`/`<summary>`, styled with `::details-content` and `:has()`. No click handler.
- **Tabs, tooltips, popovers, menus** → the `popover` attribute + `popovertarget`, plus `:has()` for state. No show/hide JS.
- **Parent / sibling state styling** (e.g. "style the card when its checkbox is checked", "style the form when an input is invalid") → `:has()`. No class toggling.
- **Component-level responsiveness** (a card that restyles based on its own width, not the viewport) → container queries. No `ResizeObserver`.
- **Layout** — centering, equal columns, responsive grids without breakpoints → Flexbox / Grid with `auto-fit` + `minmax()`.

### When JavaScript is genuinely required

Reserve JS for actual logic, not for moving pixels:

- **Data fetching / async state** — loading data, mutations, optimistic UI.
- **Complex orchestration / sequencing** that branches on runtime values CSS can't read (e.g. animation steps driven by computed data).
- **Gesture physics** — momentum scrolling, drag inertia, spring physics beyond what `linear()` easing covers.
- **Focus management & ARIA wiring** for custom widgets (roving tabindex, focus trapping) — though native `popover`/`<details>` handle much of this for you.
- **Persisting state** across reloads, or syncing UI state to a store.

If the only reason you'd reach for JS is "to add/remove a class on an event," check whether `:has()`, `:checked`, `:target`, `popover`, or `<details>` already expresses that state declaratively.

## Technique index

Grounded in the css-tricks.com guides. The full distilled catalog with URLs lives in [`references/css-tricks-index.md`](references/css-tricks-index.md). The effect → CSS-approach → when-JS-is-needed matrix is in [`references/css-over-js.md`](references/css-over-js.md).

| Need | Modern CSS | css-tricks guide |
|---|---|---|
| 1-D layout (rows/toolbars) | Flexbox (`gap`, `justify-content`, `align-items`) | [Flexbox guide](https://css-tricks.com/snippets/css/a-guide-to-flexbox/) |
| 2-D layout (page/grid) | Grid (`repeat(auto-fit, minmax())`, `fr`, areas) | [Grid guide](https://css-tricks.com/complete-guide-css-grid-layout/) |
| Component responsiveness | Container queries (`container-type`, `@container`) | [Container queries](https://css-tricks.com/css-container-queries/) |
| Parent/sibling state | `:has()`, `:is()`, `:where()` | [CSS selectors](https://css-tricks.com/css-selectors/) |
| Animatable variables | `@property` typed custom props | [Custom properties](https://css-tricks.com/a-complete-guide-to-custom-properties/) |
| Derived colors (hover tints) | `color-mix()`, relative color syntax | [Color functions](https://css-tricks.com/css-color-functions/) |

Topics not yet in the css-tricks guide index (scroll-driven animations, View Transitions, `popover`) are documented inline in the references with current MDN-aligned syntax. If you need to confirm browser support or syntax for any of these, `WebFetch` the relevant css-tricks.com guide URL above before advising.

## Ready-to-use snippets

The `assets/` folder holds valid, current, token-referencing CSS you can copy and adapt:

- [`assets/scroll-reveal.css`](assets/scroll-reveal.css) — fade-and-rise on scroll using `animation-timeline: view()`. Replaces `IntersectionObserver`.
- [`assets/hover-underline.css`](assets/hover-underline.css) — center-out underline on hover, matching the design system's tertiary-button motion.
- [`assets/disclosure.css`](assets/disclosure.css) — accordion/FAQ styling for native `<details>` + a `:has()`-driven open state. Replaces click-toggle JS.

Every value in these snippets references a design token (`var(--color-…)`, `var(--size-…)`, `var(--radius-…)`) per this repo's convention — never hardcode hex, rem, or font names. The tokens are defined by [`/css scaffold`](../css.md); if a token you need is missing, add it to `globals.css` first.

## How to use this skill

1. Identify the effect the user wants (animation, reveal, toggle, layout, responsive component).
2. Consult the decision rule above — default to CSS; only fall through to JS for the listed genuine cases.
3. Point to the matching technique in the index and, if a snippet fits, copy from `assets/` and swap in the project's tokens.
4. If the user is starting from scratch, suggest running [`/css scaffold`](../css.md) first so the tokens these techniques rely on exist.
