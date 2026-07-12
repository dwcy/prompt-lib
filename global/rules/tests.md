---
description: Test file conventions — loaded automatically when editing test files
paths:
  - "**/*Tests*/**/*.cs"
  - "**/*Test.cs"
  - "**/*.test.ts"
  - "**/*.test.tsx"
  - "**/*.spec.ts"
  - "**/*.spec.tsx"
  - "**/tests/**/*.py"
  - "**/test_*.py"
  - "**/*_test.py"
---

When editing test files:

- Test names describe business behaviour: `<Context>_<action>_<expected outcome>` (e.g. `Updating_price_returns_200_and_persists_change`) — never implementation names like `ProductUpdateService_UpdateAsync_Returns200`
- Each test must be fully independent — no shared mutable state between tests
- Do not mock `DbContext` or database layers — use real databases in integration tests
- Test behaviour and outcomes, not implementation details
- Do not assert that a method was called unless the call itself is the behaviour under test
- Arrange / Act / Assert sections — separated by a blank line; structural `// Arrange` / `// Act` / `// Assert` labels are fine, explanatory comments are not
- One logical assertion per test — if you need multiple, use `SoftAssertions` or equivalent
- Test edge cases and error paths, not just the happy path
