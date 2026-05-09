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
---

When editing test files:

- Test names follow the pattern: `MethodName_Scenario_ExpectedResult`
- Each test must be fully independent — no shared mutable state between tests
- Do not mock `DbContext` or database layers — use real databases in integration tests
- Test behaviour and outcomes, not implementation details
- Do not assert that a method was called unless the call itself is the behaviour under test
- Arrange / Act / Assert sections — separated by a blank line, no comments needed
- One logical assertion per test — if you need multiple, use `SoftAssertions` or equivalent
- Test edge cases and error paths, not just the happy path
