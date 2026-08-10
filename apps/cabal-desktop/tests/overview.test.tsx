// Component test: Overview renders each section's signal + the deployment alignment from GET
// /api/overview, and a ledger row deep-links into the corresponding module (T033).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { OverviewModule } from "@/modules/overview/OverviewModule";
import { useUiPrefsStore } from "@/stores/uiPrefs";
import { buildOverviewPayload, wrapEnvelope } from "./msw/fixtures";
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
});
