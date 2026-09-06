import { defineConfig, devices } from "@playwright/test";
import { fixtureHandshakePath } from "./tests/e2e/fixture-backend.ts";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:4173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "pnpm exec vite --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: false,
    env: {
      PROMPTLIB_CABAL_HANDSHAKE_PATH: fixtureHandshakePath(),
    },
  },
});
