# Card anatomy

Every card on a designed infographic has exactly five zones. Anatomy uniformity is what makes 16 cards feel like one coherent sheet instead of a collage.

## The five zones

```
┌─ idx ─────────── title ───── [badge] ┐ ← 1. header
│ subtitle (one mono line, always)     │ ← 2. subtitle
│                                      │
│ body — chart / pills / diagram       │ ← 3. body (vertically centered)
│                                      │
│ ↳ source/path · meta info            │ ← 4. footer
└──────────────────────────────────────┘ ← 5. frame (optional accent)
```

### 1. Header strip (always)

| Element | Style |
|---|---|
| `.idx` | Mono caps, accent colour, top-left. Format `A·01`, `B·07` to support track grouping. |
| `.title` | Display font (Space Grotesk 700), `1.55cqh`, single line, no period. |
| `.badge` | Solid accent block, top-right. Numeric (`14`) for counted features OR small-caps tag (`2 MODES`, `JSON-RPC`, `GATE 6`, `AUTO`, `REVERSIBLE`) for qualitative cards. |

### 2. Subtitle (always)

One line of mono text, `~0.92cqh`. A single concrete statement — not a continuation of the title. Avoid filler ("an overview of"); state the contract ("routed by description match").

### 3. Body (variable)

Whatever data viz fits the data shape — see `component-palette.md`. Vertically centred in the remaining grid row. `align-self: center` on the body wrapper does this.

### 4. Footer (always)

Dotted top rule + ↳ glyph + mono path or meta. Examples:

- `global/agents/*.md · invoke with @`
- `services/orchestrator/ · spec 002`
- `.specify/memory/constitution.md · v1.1.0`

The footer turns the infographic into a lookup table — readers know where to find the thing.

### 5. Frame (optional accent)

Default: 1px solid border, paper background. Use variants sparingly (2-3 cards per sheet):

| Modifier | Use for |
|---|---|
| `.tinted` | Slightly darker paper or off-ink — for "key system" emphasis |
| `.accent-rail` | 3px left border in accent — for "enforcement" or "rule" cards |
| `.framed` | 2px solid ink border — for hero / framework cards |

### Corner ticks (optional, sheet-wide)

0.8cqw × 0.6cqh L-shapes at top-left and bottom-right in accent. Gives a blueprint feel without adding visual noise. Implemented via `::before` and `::after` on every cell.

## Markup template

```html
<div class="cell w-3">
  <div class="hdr">
    <span class="idx">A·01</span>
    <h3 class="title">Card title</h3>
    <span class="badge">14</span>
  </div>
  <p class="sub">one-line concrete statement</p>
  <div class="body">
    <!-- chart / pills / diagram -->
  </div>
  <div class="cell-foot">path/where/it/lives · how to invoke</div>
</div>
```

## Size spans (in a 6-column sub-grid)

| Class | Width | Sweet spot |
|---|---|---|
| `w-2` | 1/3 column (~28mm on A4 landscape) | Pills, short ladders, tight diagrams |
| `w-3` | 1/2 column (~42mm) | Most flow diagrams, comparisons |
| `w-4` | 2/3 column (~56mm) | Bar charts, wide pill rows, orch pipelines |
| `w-6` | full column (~85mm) | Hero row, kv with long paths |

Optional row spans:

| Class | Height | Use |
|---|---|---|
| `t-2` | 2 grid rows | A card whose body is genuinely taller (e.g. 8+ pills) |

## Track grouping

Each track (A · Visible / B · Behind) gets its own 6-column × 4-row sub-grid. Span widths sum to 6 per row:

```
A track sample plan:
  Row 1: w-4 (Agents bar)        + w-2 (Hooks)
  Row 2: w-4 (Slash cmds bar)    + w-2 (MCP pills)
  Row 3: w-6 (Setup wizard — tinted, hero)
  Row 4: w-2 (Templates) + w-2 (Styles) + w-2 (Rules)
```

8 cards per track × 2 tracks = 16 cards total — fits A4 landscape comfortably.

## Don'ts

- Don't drop the subtitle just because there's "nothing to add". The subtitle gives the card weight; an empty zone makes the title feel orphaned.
- Don't put the number anywhere except the badge. Inline numbers in the body compete with the badge.
- Don't use the badge for the card title. Title is the noun (`Agents`); badge is the count (`14`) or stamp (`AUTO`).
- Don't write the footer in prose. It's a path + a verb, mono, terse.
- Don't apply more than one frame modifier per card. Pick one of `tinted` / `accent-rail` / `framed`.
