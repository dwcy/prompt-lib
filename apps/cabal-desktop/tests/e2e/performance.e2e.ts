import { expect, type Page, test } from "@playwright/test";
import { type FixtureBackend, launchFixtureBackend } from "./fixture-backend.ts";

test.describe.configure({ mode: "serial" });

let backend: FixtureBackend;

test.beforeAll(async () => {
  backend = await launchFixtureBackend();
});

test.afterAll(async () => {
  await backend?.close();
});

test("warm start and 1,000-item interactions stay within their budgets", async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000);
  const sessions = Array.from({ length: 50 }, (_, index) => ({
    session_id: `session-${index}`,
    project: "prompt-lib",
    branch: "015-web-ui-overhaul",
    title: `Performance session ${index}`,
    started_at: "2026-07-19T10:00:00Z",
    duration_seconds: index,
    cost_usd: index / 100,
    tokens_in: 10,
    tokens_out: 5,
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    agent_count: index % 3,
    skill_count: 0,
    tool_count: 0,
    hook_count: 0,
    message_count: 1,
    tool_error_count: index % 10 === 0 ? 1 : 0,
    files_written: index % 4 === 0 ? 1 : 0,
    parent_id: null,
    child_ids: [],
    has_raw_log: true,
    file_size_bytes: 100,
  }));
  const nodes = Array.from({ length: 1_000 }, (_, index) => ({
    id: `node:${index}`,
    type: `type-${index % 10}`,
    label: `Performance node ${index}`,
    resource: `fixture/${index}.md`,
    doc: "",
    tags: [],
    metrics: { incoming: index % 4, outgoing: index % 5 },
  }));
  const counts = {
    nodes: 1_000,
    edges: 0,
    by_type: Object.fromEntries(Array.from({ length: 10 }, (_, index) => [`type-${index}`, 100])),
    by_relation: {},
    findings_by_severity: {},
  };
  await page.route("**/api/sessions?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          totals: {
            session_count: 1_000,
            tokens_in: 10_000,
            tokens_out: 5_000,
            cache_read_tokens: 0,
            cache_write_tokens: 0,
            cost_usd: 245,
            duration_seconds: 50_000,
            files_written: 250,
            agent_count: 999,
          },
          items: sessions,
          next_cursor: "50",
          page_size: 50,
          sort: "date_desc",
          project: null,
        }),
      ),
    }),
  );
  await page.route("**/api/sessions/session-*?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          session_id: "session-0",
          tab: "overview",
          payload: { models: [] },
          entry_count: 1,
        }),
      ),
    }),
  );
  await page.route("**/api/knowledge", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          available: true,
          repo_root: backend.projectDir,
          bundle_root: `${backend.projectDir}/docs/okf/prompt-lib`,
          index_path: `${backend.projectDir}/.cabal/okf/index.sqlite`,
          usage_path: `${backend.projectDir}/.cabal/okf/usage.jsonl`,
          generated_at: "2026-07-19T10:00:00Z",
          index_available: true,
          semantic_available: false,
          usage_count: 0,
          counts,
          digest: "sha256:performance",
        }),
      ),
    }),
  );
  await page.route("**/api/knowledge/graph?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        envelope({
          available: true,
          generated_at: "2026-07-19T10:00:00Z",
          nodes,
          edges: [],
          counts,
          next_cursor: null,
          total_nodes: 1_000,
          total_edges: 0,
        }),
      ),
    }),
  );

  await page.goto("/");
  expect(backend.startupMs).toBeLessThan(3_000);

  await page.getByRole("button", { name: "Sessions Dashboard", exact: true }).click();
  await expect(page.getByRole("button", { name: "all · 50" })).toBeVisible();
  const sessionInteractionMs = await twoFrameInteraction(page, "Filter sessions", "errors · 5");
  expect(sessionInteractionMs).toBeLessThan(200);

  await page.getByRole("button", { name: "Knowledge & Retrieval", exact: true }).click();
  await expect(page.getByText("1000 nodes · 0 edges")).toBeVisible();
  const graphInteractionMs = await page.getByLabel("Zoom").evaluate(async (input) => {
    const started = performance.now();
    const range = input as HTMLInputElement;
    range.value = "1.1";
    range.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    return performance.now() - started;
  });
  expect(graphInteractionMs).toBeLessThan(200);

  const measurements = {
    warm_start_ms: Math.round(backend.startupMs * 10) / 10,
    sessions_interaction_ms: Math.round(sessionInteractionMs * 10) / 10,
    graph_interaction_ms: Math.round(graphInteractionMs * 10) / 10,
  };
  console.log(`PERFORMANCE ${JSON.stringify(measurements)}`);
  await testInfo.attach("performance-measurements", {
    body: Buffer.from(JSON.stringify(measurements, null, 2)),
    contentType: "application/json",
  });
});

async function twoFrameInteraction(page: Page, fieldsetName: string, buttonName: string) {
  return page
    .getByRole("group", { name: fieldsetName })
    .evaluate(async (fieldset: HTMLElement, targetName: string) => {
      const button = [...fieldset.querySelectorAll("button")].find(
        (candidate) => candidate.textContent?.trim() === targetName,
      );
      if (!(button instanceof HTMLButtonElement)) throw new Error(`Missing ${targetName}`);
      const started = performance.now();
      button.click();
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      );
      return performance.now() - started;
    }, buttonName);
}

function envelope(data: unknown) {
  return {
    schema_version: "cabal-web.v2",
    captured_at: "2026-07-19T10:00:00Z",
    status: "ok",
    source: "performance-fixture",
    stale: false,
    precondition_digest: null,
    data,
    error: null,
  };
}
