---
name: react-perf
description: Performance audit for a React component or feature — unnecessary re-renders, missing memoisation, heavy imports, bundle size issues, large dataset handling, and lazy-load opportunities.
allowed-tools: Read, Glob, Bash
---

If no target is given, ask: "Which component, hook, or feature should I audit for performance?"

Read all target files first. If a feature is given, Glob and read everything inside it.

---

## Re-render audit

### Find unnecessary re-renders

Check every component that:
- Receives objects or arrays as props without memoisation of the source
- Creates inline objects/arrays/functions inside JSX: `style={{ ... }}`, `onClick={() => ...}`, `options={[...]}`
- Calls a context that holds large state when it only needs a slice of it
- Uses a Zustand selector that returns a new object on every call

**Patterns to flag:**

```tsx
// ❌ New function reference on every render → child always re-renders
<Button onClick={() => handleClick(id)} />

// ✅ Stable reference
const handleClick = useCallback(() => onAction(id), [id, onAction])
<Button onClick={handleClick} />

// ❌ Inline object → new reference every render
<Chart config={{ color: "red", size: 12 }} />

// ✅ Stable config
const chartConfig = useMemo(() => ({ color: "red", size: 12 }), [])
<Chart config={chartConfig} />

// ❌ Zustand selector returns new object
const { name, email } = useUserStore()  // fine if destructured
const user = useUserStore(s => ({ name: s.name, email: s.email }))  // ❌ new object every call

// ✅ Select primitives or use shallow
import { useShallow } from "zustand/react/shallow"
const { name, email } = useUserStore(useShallow(s => ({ name: s.name, email: s.email })))
```

### Memoisation rule

Only add `useMemo` / `useCallback` / `memo` when:
- A profiler or DevTools flame graph shows the re-render is causing visible lag, OR
- The computation is measurably expensive (>1ms), OR
- The reference is passed to a memoised child and stability matters

Flag premature memoisation (adding `useMemo` to trivial string concatenation or a simple lookup).

---

## Lazy-load audit

Scan all imports and identify:
- Heavy components (rich text editors, charts, PDF viewers, maps, calendars) imported at the top of a page/layout
- Routes that import large feature bundles unconditionally
- Any import from a package that is not needed on initial render

**Pattern to enforce:**

```tsx
// ❌ Heavy chart imported eagerly at the top of the page
import { AnalyticsChart } from "@/features/analytics/AnalyticsChart"

// ✅ Lazy-loaded — only fetched when rendered
const AnalyticsChart = lazy(() => import("@/features/analytics/AnalyticsChart"))

// In JSX:
<Suspense fallback={<ChartSkeleton />}>
  <AnalyticsChart />
</Suspense>
```

---

## Large dataset audit

Scan for:
- Arrays mapped to JSX without a key, or with `index` as key when order can change
- Lists rendered without virtualisation when the dataset could exceed ~50 items
- `filter` + `map` chains run inside the render body without memoisation

**Flag:**

```tsx
// ❌ Renders 1000 rows directly — destroys scroll performance
{items.map(item => <Row key={item.id} {...item} />)}

// ✅ Virtualise with TanStack Virtual
import { useVirtualizer } from "@tanstack/react-virtual"
```

Recommend `@tanstack/react-virtual` for any list the user expects to grow large.

---

## Bundle size audit

```bash
# Check what's in the bundle
pnpm dlx vite-bundle-visualizer
# or:
bunx vite-bundle-visualizer
```

Flag:
- Moment.js (replace with `date-fns` or `dayjs`)
- Lodash full import (`import _ from "lodash"`) — use individual imports or native equivalents
- Full MUI component library when only icons are needed
- Any library over 50kb gzipped that could be replaced with a smaller alternative or native API

---

## TanStack Query config audit

Check the `QueryClient` configuration:
- Is `staleTime` set? Default `0` causes refetch on every focus — often too aggressive.
- Is `gcTime` (formerly `cacheTime`) appropriate?
- Are queries that run on every keystroke debounced?
- Is `refetchOnWindowFocus` disabled where it causes flicker?

```ts
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,   // 5 min — tune per query
      refetchOnWindowFocus: false, // disable if causing UX issues
    },
  },
})
```

---

## Output format

```
## Performance Audit: [filename or feature]

### High impact
- [Issue] — [location: file:line] → [Fix with code example]

### Medium impact
- [Issue] → [Recommendation]

### Low impact / opportunity
- [Issue] → [Suggestion]

### No issues
- [Areas that are optimised well]
```

- **High** — re-render on every parent render due to unstable refs, missing lazy-load on heavy component, >500 items without virtualisation
- **Medium** — unnecessary `useMemo` on trivial value, missing `staleTime`, full library import
- **Low** — minor key stability issue, small debounce opportunity

After the report, ask: "Want me to apply the high-impact fixes now?"
