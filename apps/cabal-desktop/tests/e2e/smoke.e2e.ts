import { expect, test } from "@playwright/test";
import { type FixtureBackend, launchFixtureBackend } from "./fixture-backend.ts";

const MODULE_TITLES = [
  "Project Gate & Switcher",
  "Home Overview",
  "Project Dashboard",
  "Tools Catalog",
  "Global Config Deployment",
  "Cleanup & Restore",
  "Settings Configurator",
  "MCP Connectors",
  "Local Project Config",
  "Knowledge & Retrieval",
  "Agent Services",
  "Package Security",
  "Sessions Dashboard",
  "Account & Assistant Info",
  "Config Doctor",
  "Model Assignments",
  "Environment Variables",
  "Git Identity & Commit Policy",
  "Provider Repos & Clone",
  "New Project Wizard",
  "Codex Parity",
  "Diagnostics & Backend Health",
] as const;

test.describe.configure({ mode: "serial" });

let backend: FixtureBackend;

test.beforeAll(async () => {
  backend = await launchFixtureBackend();
});

test.afterAll(async () => {
  await backend?.close();
});

test("desktop workspace smoke: nav walk, prepare/execute, responsive frame, reconnect", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  await page.goto("/");

  // Branding moved into the sidebar (not a header heading) in the console redesign.
  await expect(page.locator(".sidebar-nav__brand")).toContainText("Cabal");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator(".health-strip--ok")).toBeVisible();

  for (const title of MODULE_TITLES) {
    await page.getByRole("button", { name: title, exact: true }).click();
    await expect(page.locator(".app-shell__view-title")).toHaveText(title);
    await expect(page.locator(".module-error-boundary")).toHaveCount(0);
    await expect(page.locator("#workspace-content")).toBeVisible();
  }

  await page.getByRole("button", { name: "Knowledge & Retrieval", exact: true }).click();
  await page.getByRole("button", { name: "Validate bundle", exact: true }).click();
  await expect(page.getByRole("alertdialog", { name: "Validate OKF Bundle" })).toBeVisible();
  await page.getByRole("button", { name: "Validate OKF Bundle", exact: true }).click();
  await expect(page.getByRole("alertdialog", { name: "Validate OKF Bundle" })).toBeHidden();

  await page.getByRole("button", { name: "Home Overview", exact: true }).click();
  await expect(page.locator(".overview-console")).toBeVisible();
  await testInfo.attach("desktop-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Collapse navigation" }).click();
  await expect
    .poll(() =>
      page
        .locator("#workspace-navigation")
        .evaluate((navigation) => Math.round(navigation.getBoundingClientRect().right)),
    )
    .toBeLessThanOrEqual(0);
  const frame = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(frame.scrollWidth).toBeLessThanOrEqual(frame.clientWidth + 1);
  await expect(page.locator("#workspace-content")).toBeVisible();
  await testInfo.attach("mobile-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  await backend.stop();
  await expect(page.getByRole("alert")).toContainText("Backend unavailable", { timeout: 30_000 });
});
