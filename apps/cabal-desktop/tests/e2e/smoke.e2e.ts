// Placeholder for the T097 e2e smoke flow — skipped until the fixture
// backend launcher (tests/e2e/fixture-backend.ts) is implemented.
import { test } from "@playwright/test";

test.skip("desktop workspace smoke: nav walk, prepare/execute, reconnect", async () => {
  // T097 will:
  // 1. Launch a fixture backend via launchFixtureBackend() and point the app at it.
  // 2. Walk all 22 nav entries and assert each module renders without error.
  // 3. Run one full action prepare -> confirm -> execute flow end to end.
  // 4. Kill the fixture backend and assert the reconnect banner appears.
});
