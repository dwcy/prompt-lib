// Component test: Overview renders each section's signal + the deployment alignment from GET
// /api/overview, and a ledger row deep-links into the corresponding module (T033).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { OverviewModule } from "@/modules/overview/OverviewModule";
import { useUiPrefsStore } from "@/stores/uiPrefs";
import {
  buildErrorEnvelope,
  buildHealthPayload,
  buildOverviewPayload,
  buildProviderState,
  buildSystemOverview,
  buildToolCatalogItem,
  buildToolCatalogPayload,
  buildToolStatusEntry,
  wrapEnvelope,
} from "./msw/fixtures";
import { server } from "./msw/server";

function renderOverview() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <OverviewModule />
    </QueryClientProvider>,
  );
  return { user };
}

describe("OverviewModule", () => {
  afterEach(() => {
    useUiPrefsStore.setState({ lastModule: null, sidebarCollapsed: false });
  });

  it("renders each section's summary and the claude/codex drift badges", async () => {
    server.use(
      http.get("/api/overview", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildOverviewPayload({
              dashboard_summary: { summary: "3 services linked", state: "ok" },
              recent_sessions: [{ summary: "session-abc" }, { summary: "session-def" }],
              account: { summary: "you@example.com" },
              doctor: { summary: "No issues found" },
              knowledge_availability: { summary: "Graph available" },
              security_summary: { summary: "No vulnerabilities" },
              drift_flags: { claude: true, codex: false },
            }),
          ),
        ),
      ),
    );

    renderOverview();

    expect(await screen.findByText("3 services linked")).toBeInTheDocument();
    expect(screen.getAllByText("session-abc").length).toBeGreaterThan(0);
    expect(screen.getByText("you@example.com")).toBeInTheDocument();
    expect(screen.getByText("No issues found")).toBeInTheDocument();
    expect(screen.getByText("Graph available")).toBeInTheDocument();
    expect(screen.getByText("No vulnerabilities")).toBeInTheDocument();
    expect(screen.getByText("drift")).toBeInTheDocument();
    expect(screen.getByText("in sync")).toBeInTheDocument();
  });

  it("deep-links to the corresponding module when a ledger row is clicked", async () => {
    server.use(
      http.get("/api/overview", () => HttpResponse.json(wrapEnvelope(buildOverviewPayload()))),
    );
    const { user } = renderOverview();

    await user.click(await screen.findByRole("button", { name: "View Config Doctor" }));

    expect(useUiPrefsStore.getState().lastModule).toBe("doctor");
  });

  it("shows the active GitHub user and secondary swap target with health states", async () => {
    server.use(
      http.get("/api/provider", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildProviderState({
              accounts: [
                {
                  user: "primary-user",
                  host: "github.com",
                  active: true,
                  valid: true,
                  storage: "keyring",
                },
                {
                  user: "secondary-user",
                  host: "github.com",
                  active: false,
                  valid: true,
                  storage: "keyring",
                },
              ],
              active_account: "primary-user",
            }),
          ),
        ),
      ),
    );

    renderOverview();

    const githubPanel = await screen.findByRole("region", {
      name: "GitHub accounts on this computer",
    });
    expect(within(githubPanel).getByText("GitHub")).toBeInTheDocument();
    expect(screen.getByLabelText("primary-user is logged in, valid, and active")).toHaveAttribute(
      "data-health",
      "healthy",
    );
    expect(screen.getByLabelText("secondary-user is inactive")).toHaveAttribute(
      "data-health",
      "unhealthy",
    );
    expect(screen.getByRole("button", { name: "Swap to secondary-user" })).toBeEnabled();
  });

  it("shows Cabal revision and the computer toolchain", async () => {
    renderOverview();

    expect(await screen.findByRole("region", { name: "Machine snapshot" })).toBeInTheDocument();
    expect(screen.getByText("Windows 11")).toBeInTheDocument();
    expect(screen.getByText(/Package manager: winget/)).toBeInTheDocument();
    expect(screen.getByText("abc12345")).toBeInTheDocument();
    expect(screen.getByText("2026-08-11")).toBeInTheDocument();
    expect(screen.getByText("2.51.0")).toBeInTheDocument();
    expect(screen.getByText("3.14.0")).toBeInTheDocument();
    expect(screen.getByText("v24.0.0")).toBeInTheDocument();
    expect(screen.getByText("10.0.100")).toBeInTheDocument();
    expect(screen.getByText("Latest version")).toBeInTheDocument();
    const cabalRow = screen.getByLabelText("Cabal version");
    expect(Array.from(cabalRow.children, (child) => child.textContent)).toEqual([
      "Cabal 0.1.0",
      "abc12345",
      "2026-08-11",
      "Latest version",
    ]);
    expect(screen.queryByRole("button", { name: "Up to date" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Terminal settings" })).toBeInTheDocument();
    expect(screen.getByText(/Default terminal: Windows Terminal/)).toBeInTheDocument();
    expect(screen.getByText("PowerShell")).toBeInTheDocument();
    expect(screen.getByText("Command Prompt")).toBeInTheDocument();
    expect(screen.getByText("Windows Terminal")).toBeInTheDocument();
    expect(screen.getByText("Oh My Posh")).toBeInTheDocument();
    expect(screen.getByText("CaskaydiaCove Nerd Font")).toBeInTheDocument();
  });

  it("replaces the latest-version label with a yellow update link only when behind", async () => {
    const overview = buildSystemOverview();
    server.use(
      http.get("/api/system/overview", () =>
        HttpResponse.json(
          wrapEnvelope({
            ...overview,
            cabal: {
              ...overview.cabal,
              status: "behind",
              latest_hash: "def67890",
              behind_count: 2,
            },
          }),
        ),
      ),
    );

    renderOverview();

    const update = await screen.findByRole("button", { name: "Update (2)" });
    expect(update).toHaveClass("overview-system-panel__update-link");
    expect(screen.queryByText("Latest version")).not.toBeInTheDocument();
    expect(screen.queryByText("Up to date")).not.toBeInTheDocument();
  });

  it("falls back to existing endpoints when the running backend needs a restart", async () => {
    server.use(
      http.get("/api/system/overview", () =>
        HttpResponse.json(buildErrorEnvelope({ code: "not_found", message: "Not Found" }), {
          status: 404,
        }),
      ),
      http.get("/api/health", () =>
        HttpResponse.json(wrapEnvelope(buildHealthPayload(0, { version: "0.1.0" }))),
      ),
      http.get("/api/env", () =>
        HttpResponse.json(
          wrapEnvelope({
            scope: "curated",
            entries: [],
            count: 0,
            editable_count: 0,
            platform: "Windows",
          }),
        ),
      ),
      http.get("/api/tools", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildToolCatalogPayload([
              buildToolCatalogItem({ key: "git", label: "Git" }),
              buildToolCatalogItem({ key: "python", label: "Python" }),
            ]),
          ),
        ),
      ),
      http.get("/api/tools/status", () =>
        HttpResponse.json(
          wrapEnvelope({
            items: [
              buildToolStatusEntry("git", "installed", { current_version: "2.51.0" }),
              buildToolStatusEntry("python", "installed", { current_version: "3.14.0" }),
            ],
          }),
        ),
      ),
    );

    renderOverview();

    expect(await screen.findByText("Restart to refresh")).toBeInTheDocument();
    expect(screen.getByText("Windows")).toBeInTheDocument();
    expect(screen.getByText("2.51.0")).toBeInTheDocument();
    expect(screen.getByText("3.14.0")).toBeInTheDocument();
    expect(screen.queryByText(/Computer information is unavailable/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Restart required" })).not.toBeInTheDocument();
    expect(screen.getByText("No shells detected")).toBeInTheDocument();
  });

  it("derives the tool catalog, agent assets, knowledge graph, and services-ready KPIs from real data, plus the git/github/supabase/vercel status row", async () => {
    server.use(
      http.get("/api/tools", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildToolCatalogPayload([
              buildToolCatalogItem({ key: "git" }),
              buildToolCatalogItem({ key: "node" }),
              buildToolCatalogItem({ key: "bun" }),
              buildToolCatalogItem({ key: "docker" }),
              buildToolCatalogItem({ key: "zed" }),
            ]),
          ),
        ),
      ),
      http.get("/api/tools/status", () =>
        HttpResponse.json(
          wrapEnvelope({
            items: [
              buildToolStatusEntry("git", "installed"),
              buildToolStatusEntry("node", "update_available"),
              buildToolStatusEntry("bun", "missing"),
              buildToolStatusEntry("docker", "manual_required"),
              buildToolStatusEntry("zed", "unsupported"),
            ],
          }),
        ),
      ),
      http.get("/api/knowledge", () =>
        HttpResponse.json(
          wrapEnvelope({
            available: true,
            repo_root: "C:/projects/prompt-lib",
            bundle_root: "docs/okf/prompt-lib",
            index_path: "docs/okf/prompt-lib/index.sqlite",
            usage_path: "docs/okf/prompt-lib/usage.jsonl",
            generated_at: "2026-08-11T00:00:00Z",
            index_available: true,
            semantic_available: true,
            usage_count: 12,
            counts: {
              nodes: 143,
              edges: 212,
              by_type: { agent: 29, skill: 26, hook: 9, rule: 4 },
              by_relation: {},
              findings_by_severity: {},
            },
            digest: "abc123",
          }),
        ),
      ),
      http.get("/api/dashboard", ({ request }) => {
        const section = new URL(request.url).searchParams.get("section");
        const bySection: Record<string, Record<string, unknown>> = {
          git: { state: "ok", current_branch: "main", local_branches: ["main"], remotes: [] },
          github: {
            state: "ok",
            connected: true,
            owner_repo: "dwcy/prompt-lib",
            runs: [],
            pull_requests: [],
          },
          supabase: {
            state: "token_missing",
            hint: "Set SUPABASE_ACCESS_TOKEN to enrich this section.",
          },
          vercel: { state: "not_linked", hint: "Run `vercel link` to connect a project." },
        };
        return HttpResponse.json(wrapEnvelope(bySection[section ?? ""] ?? {}));
      }),
    );

    renderOverview();

    expect(await screen.findByText("Tool catalog")).toBeInTheDocument();
    expect(screen.getByText("40% installed")).toBeInTheDocument();
    expect(screen.getByText("2 installed · 1 missing · 1 manual · 1 n/a")).toBeInTheDocument();

    expect(screen.getByText("Agent assets")).toBeInTheDocument();
    expect(screen.getByText("29 agents · 26 skills · 9 hooks · 4 rules")).toBeInTheDocument();

    expect(screen.getByText("Knowledge graph")).toBeInTheDocument();
    expect(screen.getByText("exported")).toBeInTheDocument();
    expect(screen.getByText("212 edges")).toBeInTheDocument();

    expect(screen.getByText("Services ready")).toBeInTheDocument();
    expect(screen.getByText("2 need attention")).toBeInTheDocument();
    expect(screen.getByText("Supabase no token · Vercel not linked")).toBeInTheDocument();

    const servicesRow = screen.getByRole("region", { name: "Project service status" });
    expect(within(servicesRow).getByText("Supabase")).toBeInTheDocument();
    expect(within(servicesRow).getByText("token_missing")).toBeInTheDocument();
    expect(within(servicesRow).getByText("Vercel")).toBeInTheDocument();
    expect(within(servicesRow).getByText("not_linked")).toBeInTheDocument();
    expect(
      within(servicesRow).getByText("Run `vercel link` to connect a project."),
    ).toBeInTheDocument();
  });
});
