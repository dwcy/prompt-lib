---
name: react-safe
description: Audit a React file or feature for async correctness, error handling completeness, and security issues — unhandled promises, swallowed errors, missing sanitisation, logged secrets, and input validation gaps.
allowed-tools: Read, Glob, Bash
---

If no target is given, ask: "Which file, hook, or feature should I audit for safety?"

Read all target files before reporting. If a feature directory is given, Glob and read everything inside it.

---

## Async audit

Scan every `async` function and `useEffect` with async logic.

**Check for:**

- `await` calls without `try/catch` and outside of TanStack Query's managed scope
- `.then()` / `.catch()` chains mixed with `async/await` in the same function
- Unhandled promise rejections (bare `promise.then(...)` with no `.catch()`)
- `useEffect` that calls an async function but doesn't handle the cleanup or rejection
- Race conditions: multiple concurrent fetches without `AbortController` or query deduplication

**Pattern to enforce:**

```ts
// Good — explicit error boundary
try {
  const data = await apiFetch("/endpoint");
  // handle data
} catch (error) {
  logger.error("Failed to fetch endpoint", { error, userId });
  // propagate or set error state
}

// Good — TanStack Query handles it
const { data, error } = useQuery({ queryKey: [...], queryFn: fetchFn });
```

**Flag these patterns:**

```ts
// ❌ Fire and forget
useEffect(() => { fetchData(); }, []);

// ❌ Swallowed error
try { ... } catch (_) {}
catch (e) { console.log(e) }  // not enough — no context

// ❌ .then without .catch
apiCall().then(setData);
```

---

## Error handling audit

**Check for:**

- Errors caught and silently discarded (empty catch blocks or `catch(_)`)
- `console.log(error)` — should be structured logging with context
- No error boundary around async-heavy component subtrees
- Missing loading/error state handling in components that use queries or mutations
- `throw` used for expected/recoverable errors (e.g., 404) — should return typed result instead
- Retry/fallback logic absent for critical data fetches

**Logging standard:**

```ts
// Include contextual metadata — never just the error alone
logger.error("Failed to submit order", {
  error,
  userId: user.id,
  orderId,
  endpoint: "/orders",
  timestamp: new Date().toISOString(),
});
```

---

## Security audit

### Input sanitisation

- Any user-provided string rendered via `dangerouslySetInnerHTML` without DOMPurify
- Form inputs passed to API calls without Zod schema validation first
- URL parameters (`useParams`, `useSearchParams`) used in queries without sanitisation

**Pattern to enforce:**

```ts
// Every dangerouslySetInnerHTML must go through DOMPurify
const clean = DOMPurify.sanitize(userGeneratedHtml);
<div dangerouslySetInnerHTML={{ __html: clean }} />

// Every form value must pass a Zod schema before hitting the API
const result = schema.safeParse(formValues);
if (!result.success) return handleValidationError(result.error);
await submitOrder(result.data);
```

### Secrets and PII

- `console.log`, `console.error`, or any logger call that includes:
  - Tokens, API keys, passwords (`token`, `password`, `secret`, `key`, `auth`)
  - PII (`email`, `phone`, `address`, `ssn`, `dob`, `nationalId`)
- Any secret passed as a prop or stored in component state unnecessarily
- `VITE_` env vars that contain secrets (should be server-side only)

### Least privilege

- Components receiving more data than they need (over-fetching then ignoring fields)
- Zustand stores holding data that should be scoped locally
- Auth tokens stored in `localStorage` without awareness of XSS risk (flag as warning)

---

## Output format

```
## Safety Audit: [filename or feature]

### Critical
- [Issue] — [exact location: file:line] → [Fix]

### Warning
- [Issue] — [exact location] → [Recommendation]

### Suggestion
- [Issue] → [Improvement]

### Clean
- [Areas with no issues — be specific]
```

- **Critical** — unhandled async errors, missing DOMPurify, PII in logs, secret in client-side code
- **Warning** — swallowed catch, missing loading/error UI, validation gap, over-scoped data
- **Suggestion** — structured logging improvement, typed result over throw, AbortController opportunity

After the report, ask: "Want me to fix the Critical items now?"
