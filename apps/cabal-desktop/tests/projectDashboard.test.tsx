// Component test: Project Dashboard shows linked sections with their summary, hides sections
// reporting they aren't linked yet, and each section's refresh button refetches only that section
// (T034).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { ProjectDashboardModule } from "@/modules/project-dashboard/ProjectDashboardModule";
import { wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function sectionOf(request: Request): string | null {
  return new URL(request.url).searchParams.get("section");
}

function renderDashboard() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ProjectDashboardModule />
    </QueryClientProvider>,
  );
  return { user };
}

describe("ProjectDashboardModule", () => {
  it("shows linked sections with their summary and hides sections reporting linked: false", async () => {
    let githubCallCount = 0;
    server.use(
      http.get("/api/dashboard", ({ request }) => {
        const section = sectionOf(request);
        if (section === "git") {
          return HttpResponse.json(
            wrapEnvelope({ state: "ok", current_branch: "main", detached: false }),
          );
        }
        if (section === "github") {
          githubCallCount += 1;
          return HttpResponse.json(wrapEnvelope({ state: "ok", connected: false }));
        }
        if (section === "supabase") {
          return HttpResponse.json(wrapEnvelope({ state: "not_set_up" }));
        }
        return HttpResponse.json(
          wrapEnvelope({
            state: "ok",
            project_name: "my-app",
            latest_deployment_status: "READY",
          }),
        );
      }),
    );

    renderDashboard();

    expect(await screen.findByText("On main")).toBeInTheDocument();
    expect(screen.getByText("my-app · READY")).toBeInTheDocument();
    expect(screen.queryByText("GitHub")).not.toBeInTheDocument();
    expect(screen.queryByText("Supabase")).not.toBeInTheDocument();
    expect(githubCallCount).toBe(1);
  });

  it("refetches a section when its refresh button is clicked", async () => {
    let gitCallCount = 0;
    server.use(
      http.get("/api/dashboard", ({ request }) => {
        const section = sectionOf(request);
        if (section === "git") {
          gitCallCount += 1;
          return HttpResponse.json(
            wrapEnvelope({ state: "ok", current_branch: `call-${gitCallCount}` }),
          );
        }
        return HttpResponse.json(wrapEnvelope({ state: "ok", connected: true }));
      }),
    );
    const { user } = renderDashboard();

    await screen.findByText("On call-1");
    await user.click(screen.getByRole("button", { name: "Refresh Git" }));

    await waitFor(() => expect(gitCallCount).toBe(2));
    expect(await screen.findByText("On call-2")).toBeInTheDocument();
  });
});
