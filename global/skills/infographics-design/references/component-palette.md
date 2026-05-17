# Body component palette

Eleven components for the card body zone. Pick the one whose data shape matches what you're showing — don't reach for a chart when pills will do.

## When to pick what

| Data shape | Component |
|---|---|
| Ranked breakdown by category | `bar` |
| Flat enumeration | `pills` |
| 4-beat lifecycle | `lifecycle-mini` |
| 3-step transformation | `flow` |
| 5-7 step pipeline | `orch-mini` |
| Structured definitions | `ladder` |
| Key/value reference | `kv` |
| Binary state comparison | `iso-mini` |
| Protocol/channel diagram | `wire-mini` |
| Gated checkpoints (4-8 items) | `gates-row` |
| Source/process/target flow | `deploy-mini` |

## bar — ranked breakdown

For: how a total decomposes (14 agents = 7 architects + 3 auditors + …).

```html
<div class="bar">
  <div class="row">
    <span class="lab">architect</span>
    <div class="track-line"><span style="width:50%"></span></div>
    <span class="num">7</span>
  </div>
  <!-- 3-5 rows total -->
</div>
```

Fixed label column (`6cqw`), tabular nums, axis line under bars. Don't show more than 5 rows or it gets noisy.

## pills — flat list

For: enumerable set of named items (MCP servers, templates, output styles).

```html
<div class="pills">
  <span class="pill">github</span>
  <span class="pill">figma</span>
  <!-- ... -->
</div>
```

Mono caps, **square corners** (`border-radius: 0`) to match the blueprint aesthetic — don't use pill / capsule rounding; it reads as a medicine tablet and clashes with the sharp borders of cells and bars. ~8 pills fits a `w-2` cell; 4-6 in tighter spaces.

## lifecycle-mini — 4-beat horizontal timeline

For: lifecycle scripts, sequential hooks, a small ordered process.

```html
<div class="lifecycle-mini">
  <div class="beat"><div class="dot"></div><div class="lab">Start</div></div>
  <div class="beat"><div class="dot"></div><div class="lab">Pre</div></div>
  <div class="beat"><div class="dot"></div><div class="lab">Post</div></div>
  <div class="beat"><div class="dot"></div><div class="lab">Stop</div></div>
</div>
```

Connector line is `::before` on the wrapper. Dots punch through with a `box-shadow` ring of the cell background.

## flow — 3-step arrow diagram

For: routing logic, decision flow, before-after transformation.

```html
<div class="flow">
  <div class="node">step 1</div>
  <div class="arr">›</div>
  <div class="node">step 2</div>
  <div class="arr">›</div>
  <div class="node">step 3</div>
</div>
```

3 nodes is the sweet spot. 4+ should use `orch-mini`.

## orch-mini — N-step pipeline

For: longer pipelines (5+ steps), build flows, deployments.

```html
<div class="orch-mini">
  <div class="step"><span class="ord">01</span>label</div>
  <!-- repeat 4-6 times -->
</div>
```

Each step is small mono caps with an `ord` badge. Best in `w-4` so steps don't get crushed.

## ladder — keyed list

For: structured definitions (memory tiers, conventions, rules).

```html
<ul class="ladder">
  <li><span class="k">commits</span>conventional types · author via -c flags</li>
  <li><span class="k">branches</span>refuse on main · feature branch first</li>
</ul>
```

`<span class="k">` is the mono caps key on its own line; the rest of the `<li>` is the body.

## kv — key/value spec sheet

For: 2-4 short lookups (run modes, env vars, distribution channels).

```html
<div class="kv">
  <span class="k">terminal</span><span class="v">python setup/configurator.py</span>
  <span class="k">standalone</span><span class="v">App.exe — 40 MiB · no Python required</span>
</div>
```

## iso-mini — two-state comparison

For: bad vs good, before vs after, broken vs working.

```html
<div class="iso-mini">
  <div class="col bad"><div class="h">shared</div>explanation</div>
  <div class="col good"><div class="h">isolated</div>explanation</div>
</div>
```

`::before` glyphs auto-inject ✗ / ✓ in the header.

## wire-mini — endpoint + lanes

For: protocols (request/response over wire), event channels, message buses.

```html
<div class="wire-mini">
  <div class="end">producer</div>
  <div class="end">consumer</div>
  <div class="lanes">
    <div><span class="dir">▶</span><span>request.send</span><span class="meta">POST</span></div>
    <div><span class="dir">◀</span><span>response.state</span><span class="meta">SSE</span></div>
  </div>
</div>
```

## gates-row — labelled tiles

For: 4-8 named gates, checkpoints, status indicators.

```html
<div class="gates-row">
  <div class="gx">G1<span class="lab">spec</span></div>
  <!-- ... -->
  <div class="gx new">G6<span class="lab">new</span></div>
</div>
```

`.new` modifier paints one tile in solid accent — for "this is the newest one" emphasis.

## deploy-mini — 3-stage horizontal pipeline

For: source → process → target flows. Reversible deployments. ETL stages.

```html
<div class="deploy-mini">
  <div class="b">global/</div>
  <div class="arr">›</div>
  <div class="b mid">apply wizard</div>
  <div class="arr">›</div>
  <div class="b">~/.claude/</div>
</div>
```

Middle pane uses `mid` modifier for accent fill — the action between the two states.

## Composition tips

- One component per card. Don't mix `pills` + `bar` in the same body.
- If you can't fit the data into any of these, the card scope is probably too broad — split it into two cards.
- Match component to span: bar/orch/gates want `w-4`+; pills/ladder/kv flex; iso/wire/flow want `w-3`.
