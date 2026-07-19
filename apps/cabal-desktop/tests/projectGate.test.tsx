// Component test: the project gate blocks the workspace until a project has been explicitly
// selected, and selecting one (recents) drives project.select prepare→confirm→execute through to
// the normal shell — exercising T032's gate flow and T036's cache-invalidation wiring end-to-end.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import App from "@/App";
import { useProjectContextStore } from "@/stores/projectContext";
import { useUiPrefsStore } from "@/stores/uiPrefs";
import {
  buildConfirmationTicket,
  buildEffectPreview,
  buildProjectContext,
  buildRecentProject,
  wrapEnvelope,
} from "./msw/fixtures";
import { server } from "./msw/server";

function renderApp() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
  return { user };
}

describe("Project gate", () => {
  afterEach(() => {
    useProjectContextStore.setState({ selected: null, recents: [] });
    useUiPrefsStore.setState({ lastModule: null, sidebarCollapsed: false });
  });

  it("blocks the workspace and shows recents + a path input when no project has ever been selected", async () => {
    server.use(
      http.get("/api/project", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildProjectContext({
              selected_at: null,
              recents: [buildRecentProject({ path: "/repos/alpha", name: "alpha" })],
            }),
          ),
        ),
      ),
    );

    renderApp();

    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("Project folder path")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
  });

  it("selecting a recent project through prepare→confirm→execute closes the gate and reveals the shell", async () => {
    let projectSelected = false;
    server.use(
      http.get("/api/project", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildProjectContext({
              selected_at: projectSelected ? "2026-01-01T00:00:00Z" : null,
              path: projectSelected ? "/repos/alpha" : "/repos/example",
              name: projectSelected ? "alpha" : "example",
              recents: [buildRecentProject({ path: "/repos/alpha", name: "alpha" })],
            }),
          ),
        ),
      ),
      http.post("/api/actions/project.select/prepare", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "project.select",
              effect_preview: buildEffectPreview({ summary: "Switch to alpha" }),
            }),
          ),
        ),
      ),
      http.post("/api/actions/project.select/execute", () => {
        projectSelected = true;
        return HttpResponse.json(wrapEnvelope({ job_id: null }));
      }),
    );

    const { user } = renderApp();

    await user.click(await screen.findByText("alpha"));
    await screen.findByText("Switch to alpha");
    await user.click(screen.getByRole("button", { name: "Switch project" }));

    expect(await screen.findByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(useProjectContextStore.getState().selected?.name).toBe("alpha");
  });
});
