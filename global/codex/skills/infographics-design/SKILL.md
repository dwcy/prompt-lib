---
name: infographics-design
description: Use when designing an HTML infographic, single-page feature reference, or printable A4 visual overview. Produces a single self-contained file with embedded CSS-only data viz (bar charts, lifecycle timelines, flow diagrams, pill rows), uniform card anatomy, blueprint corner ticks, and a single-accent palette. Not for general web pages or app UIs.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Infographics Design

Single-file HTML infographics that read like a printed reference sheet, not a webpage. Optimised for one A4 page (landscape, no scrolling) or a longer scrollable variant.

## When to invoke

- "Make me an infographic of all our features"
- "Single-page overview I can print or screenshot"
- "Visual reference for the team / stakeholder"
- "One-page feature map of this repo"

Not for:
- General marketing landing pages → use a frontend framework
- App UIs → use `@react-architect` / `@frontend-architect`
- Static documentation → use Markdown

## The six rules that drive the output

### 1. Audit before you design

Count every feature from its **actual source files** — not what the README claims, not from memory. Use `scripts/audit_features.py` or run `Glob`/`Bash` equivalents. Cite the path in the cell footer so the infographic doubles as a lookup table (e.g. "17 agents · `global/agents/*.md`").

This is non-negotiable. Stale numbers undermine the whole sheet.

### 2. Two tracks, not one

Every system has a **visible surface** (what users invoke) AND a **behind-the-scenes** layer (how it works). A good infographic shows both — the second track is where depth lives and the audience learns something.

Default split: **A · Visible** (left column) | **B · Behind the scenes** (right column). The body grid must mirror the header columns.

### 3. Uniform card anatomy

Every card on the sheet has exactly five zones, no exceptions:

```
┌─ idx ─────────── title ───── [badge] ┐
│ subtitle (one mono line, always)     │
│                                      │
│ body — chart / pills / diagram       │
│                                      │
│ ↳ source/path · meta info            │
└──────────────────────────────────────┘
```

Full spec in `references/card-anatomy.md`. Anatomy uniformity is what makes 16 cards feel like one coherent sheet instead of a collage.

### 4. Solid colours over gradients

Budget: **≤3 gradients in the whole document**. Single accent — no rainbow. Variation comes from cell treatments (`tinted`, `accent-rail`, `framed`), not new colours.

Default palette: cream paper / ink black / one deep accent. Light + dark cell alternation between the two tracks. See `references/design-tokens.css`.

### 5. Sharp corners over rounded

The default aesthetic is **square / blueprint**, not soft / web-UI. Concretely:

| Element | Radius |
|---|---|
| Cells | `0` (1px solid border) |
| Pills, gates, orch steps, deploy panes | `0` |
| Bar segments + tracks | `1px` (very subtle) |
| Badge block | `2px` max |
| Lifecycle dots | `50%` (circles are fine; that's their shape) |

Pill / capsule rounding (`border-radius: 999px`) reads as a medicine tablet — it clashes with the sharp 1px borders of cells, bars, and gates. Save heavy rounding for app UIs, not reference sheets.

### 6. Size variation comes from content, not aesthetics

Don't force a uniform grid. Bar charts want width; pill rows can be narrow. Lay each track on a 6-column sub-grid and span cards 2 / 3 / 4 / 6 columns based on what they show. See `references/card-anatomy.md` for span guidance.

## Process

1. **Classify scope**
   - One-page (A4) — fixed dimensions, no scroll → use `references/a4-fit-pattern.css`.
   - Scrollable longform — vertical sections → use design tokens but no `aspect-ratio`.

2. **Audit content**
   - Run `python scripts/audit_features.py "<glob1>" "<glob2>" ...` to count each feature group.
   - Separate visible-surface items from behind-the-scenes items.
   - Aim for ~16 cells total (8 per track) for a balanced A4 sheet. Cut cells if you can't reach 16 — uneven counts work fine.

3. **Plan the layout matrix**
   - For each cell, decide: width span + body component (from `references/component-palette.md`).
   - Mark 2-3 cells for `tinted` or `accent-rail` emphasis.
   - Sketch on paper or in a markdown table before writing HTML.

4. **Scaffold**
   - Copy `assets/template.html` to the target path.
   - Swap the design tokens if the project has its own brand colour.
   - Replace placeholder cells with planned content.

5. **Validate**
   - `python scripts/validate_html.py <file>` — checks tag balance, CSS brace balance, gradient count.
   - Confirm cell count, badge count, and footer count are all equal.
   - Open in browser at the target size; confirm no scroll on A4 variant.
   - State explicitly what you cannot visually verify — gradient text, hover states, fit on the user's actual monitor.

## Bundled resources

| Path | What it is |
|---|---|
| `assets/template.html` | Complete A4 landscape skeleton with header, two-track grid, footer, three sample cells covering different body components. Copy as starting point. |
| `references/card-anatomy.md` | Five-zone spec with markup template and span guidance. |
| `references/component-palette.md` | Eleven body components (bar, pills, lifecycle, flow, orch, ladder, kv, iso, wire, gates, deploy) — when to pick which. |
| `references/design-tokens.css` | `:root` custom properties, reset, fonts. Drop-in for the `<style>` block. |
| `references/a4-fit-pattern.css` | Sheet container with `aspect-ratio`, `container-type: size`, `cqw`/`cqh` units, print stylesheet. |
| `scripts/audit_features.py` | Counts files matching one or more glob patterns. Use it to compute the numbers BEFORE writing the page. |
| `scripts/validate_html.py` | HTML tag-stack validation + CSS brace balance + gradient budget check. |

## Anti-patterns

- **Multi-colour rainbow palette.** Looks like a tech ad, not a reference. Pick one accent.
- **Rounded pills / capsules** (`border-radius: 999px`). Reads as a medicine tablet, clashes with the sharp borders of cells, bars, and gates. Use `border-radius: 0` for pills, tiles, panes.
- **Inconsistent card anatomy.** Some cells with numbers, some without; some with footers, some without — feels like a collage. Use all five zones every time.
- **Bar charts without an axis line or aligned labels.** Labels must share a fixed column width; numbers must use `tabular-nums`.
- **Web-feeling hover, animation, parallax.** This is a printed sheet. Cut motion except for `prefers-reduced-motion: no-preference` entrance fades on scrollable longform.
- **Pretending an A4 sheet is a webpage.** Use `aspect-ratio` and `overflow: hidden` on the sheet. Use `cqw`/`cqh` units inside, not `vw`/`vh`.
- **Container queries without `container-type: size`** on the sheet — `cqh` won't work otherwise.
- **Numbers that don't match the actual file count.** Audit first; cite the path; never round up to a nicer number.
- **More than three gradients.** If you need a fourth, replace one with a solid `tinted` or `accent-rail` treatment.

## Iteration loop

1. Get content density + structure right (audit, layout, anatomy).
2. Polish typography + spacing.
3. Add purposeful variation (size spans, accent treatments).
4. Validate structurally + visually.
5. Ask the user what cannot be confirmed from your side.

Don't skip step 1. A polished card with the wrong number is worse than an ugly card with the right number.
