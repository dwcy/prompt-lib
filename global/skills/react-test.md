---
name: react-test
description: Scaffold or review tests for a React component, hook, or feature using Vitest and React Testing Library. Follows dependency-injection patterns, covers happy paths and failure modes, never tests implementation details.
allowed-tools: Read, Write, Glob, Bash
---

If no argument is given, ask: "Which component, hook, or feature should I write tests for?"

Read the target file before writing any tests.

---

## Test placement

```
src/components/ui/Button/
├── Button.tsx
└── __tests__/
    └── Button.test.tsx

src/features/auth/
├── components/LoginForm.tsx
├── hooks/useLogin.ts
└── __tests__/
    ├── LoginForm.test.tsx
    └── useLogin.test.ts
```

Tests live in a `__tests__/` folder inside the component or feature directory. Mirror the source filename with `.test.tsx` / `.test.ts`.

---

## What to test

### Components
- Renders without crashing (smoke test)
- Renders correct output for each meaningful prop combination
- User interactions: click, type, submit — test the outcome, not the internal state
- Conditional rendering: when a prop changes, does the right branch show?
- Error states: what does it render when data is missing or loading fails?
- Accessibility: interactive elements are keyboard reachable, labels are correct

### Custom hooks
- Test via `renderHook` from React Testing Library
- Initial state is correct
- Each action produces the expected state transition
- Async actions resolve and reject correctly
- Side effects run at the right time

### Feature integration (when requested)
- User journey from entry to completion
- Happy path end-to-end within the feature boundary
- At least one failure mode (network error, validation failure)

---

## Rules to follow

- **Test behaviour, not implementation** — never assert on internal state, private methods, or component internals
- **Dependency injection** — mock external dependencies (API calls, stores, auth) at the module boundary using `vi.mock()`
- **Explicit setup** — use `beforeEach` to reset mocks; never share mutable state between tests
- **Named arrange/act/assert** — structure each test clearly; use descriptive `it()` strings
- **Cover failure modes** — at least one test per component/hook for an error or empty state
- **No `getByTestId`** unless there is no accessible query — prefer `getByRole`, `getByLabelText`, `getByText`
- **No snapshot tests** — they break on any UI change and test nothing meaningful

---

## Test file template

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Wrap with providers if needed
function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("[ComponentName]", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders correctly with default props", () => {
    render(<ComponentName />, { wrapper });
    expect(screen.getByRole("button", { name: /submit/i })).toBeInTheDocument();
  });

  it("calls onSubmit when the form is valid", async () => {
    const onSubmit = vi.fn();
    render(<ComponentName onSubmit={onSubmit} />, { wrapper });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  it("shows an error when the API call fails", async () => {
    vi.mocked(apiCall).mockRejectedValue(new Error("Network error"));
    render(<ComponentName />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i)
    );
  });
});
```

---

## Mocking patterns

**API / fetch:**
```ts
vi.mock("@/api/client", () => ({
  apiFetch: vi.fn(),
}))
```

**TanStack Query mutation:**
```ts
vi.mock("@/features/auth/hooks/useLogin", () => ({
  useLogin: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  }),
}))
```

**Zustand store:**
```ts
vi.mock("@/state/cartStore", () => ({
  useCartStore: vi.fn(() => ({
    items: [],
    addItem: vi.fn(),
  })),
}))
```

---

## Vitest config check

Before writing tests, verify `vite.config.ts` has the test block:

```ts
test: {
  globals: true,
  environment: "jsdom",
  setupFiles: "./src/test/setup.ts",
}
```

And `src/test/setup.ts` imports `@testing-library/jest-dom`. Create these if missing.

---

## After writing tests

```bash
bun run test        # or: npx vitest
bun run test --coverage
```

Report: tests written, coverage of the happy path and how many failure modes are covered.
