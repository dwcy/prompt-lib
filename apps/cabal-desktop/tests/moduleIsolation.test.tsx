// Component + shell test: one Project Dashboard section failing (a section-scoped GET /api/dashboard
// error) degrades only that section via its own TanStack Query error state — it never throws during
// render, so ModuleErrorBoundary (components/shell/ModuleErrorBoundary.tsx) never engages here; sibling
// sections keep rendering their real data and the rest of the shell (nav, other modules) stays usable.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import App from "@/App";
import { ProjectDashboardModule } from "@/modules/project-dashboard/ProjectDashboardModule";
import { useUiPrefsStore } from "@/stores/uiPrefs";
import { buildErrorEnvelope, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function sectionOf(request: Request): string | null {
  return new URL(request.url).searchParams.get("section");
}

function githubFailingDashboardHandler() {
  return http.get("/api/dashboard", ({ request }) => {
    const section = sectionOf(request);
    if (section === "github") {
      return HttpResponse.json(
        buildErrorEnvelope({ code: "github_unreachable", message: "GitHub API timed out" }),
        { status: 500 },
      );
    }
    if (section === "git") {
      return HttpResponse.json(wrapEnvelope({ state: "ok", current_branch: "main" }));
    }
    if (section === "supabase") {
      return HttpResponse.json(wrapEnvelope({ state: "ok", project_ref: "abcd1234" }));
    }
    return HttpResponse.json(
      wrapEnvelope({ state: "ok", project_name: "my-app", latest_deployment_status: "READY" }),
    );
  });
}

// useDashboardSection sets no per-query retry (unlike useHealth's retry: 2), so a bare
// `new QueryClient()` would retry the failing section 3x with exponential backoff before
// isError flips true — retry: false makes the failure assert promptly, matching how a real
// section error appears to the user (TanStack's error state, not an artificial delay).
function newTestQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

describe("Module isolation: one dashboard section failing", () => {
  it("keeps rendering sibling sections' data and shows the failing section's own error state", async () => {
    server.use(githubFailingDashboardHandler());
    const queryClient = newTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectDashboardModule />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("On main")).toBeInTheDocument();
    expect(screen.getByText("abcd1234")).toBeInTheDocument();
    expect(screen.getByText("my-app · READY")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("GitHub API timed out");
  });

  describe("full shell", () => {
    afterEach(() => {
      useUiPrefsStore.setState({ lastModule: null, sidebarCollapsed: false });
    });

    it("keeps the workspace navigable and other modules unaffected while one section is failing", async () => {
      server.use(githubFailingDashboardHandler());
      const queryClient = newTestQueryClient();
      const user = userEvent.setup();
      render(
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>,
      );

      await user.click(await screen.findByRole("button", { name: "Project Dashboard" }));

      expect(await screen.findByText("On main")).toBeInTheDocument();
      expect(await screen.findByRole("alert")).toHaveTextContent("GitHub API timed out");

      await user.click(screen.getByRole("button", { name: "Home Overview" }));

      expect(await screen.findByRole("navigation", { name: "Primary" })).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });
});
