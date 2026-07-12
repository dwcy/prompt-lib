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
            wrapEnvelope({ linked: true, state: "ok", summary: "Clean working tree" }),
          );
        }
        if (section === "github") {
          githubCallCount += 1;
          return HttpResponse.json(wrapEnvelope({ linked: false }));
        }
        if (section === "supabase") {
          return HttpResponse.json(wrapEnvelope({ state: "not_set_up" }));
        }
        return HttpResponse.json(wrapEnvelope({ linked: true, summary: "Deployed" }));
      }),
    );

    renderDashboard();

    expect(await screen.findByText("Clean working tree")).toBeInTheDocument();
    expect(screen.getByText("Deployed")).toBeInTheDocument();
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
            wrapEnvelope({ linked: true, summary: `Git call ${gitCallCount}` }),
          );
        }
        return HttpResponse.json(wrapEnvelope({ linked: true, summary: "ok" }));
      }),
    );
    const { user } = renderDashboard();

    await screen.findByText("Git call 1");
    const refreshButtons = screen.getAllByRole("button", { name: "Refresh" });
    await user.click(refreshButtons[0]);

    await waitFor(() => expect(gitCallCount).toBe(2));
    expect(await screen.findByText("Git call 2")).toBeInTheDocument();
  });
});
