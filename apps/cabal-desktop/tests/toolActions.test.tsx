// Component test: the Tools install/update action flow end to end — ConfirmDialog blocks execute
// until the user confirms, and once the resulting job reaches a terminal state the tool's status
// query is invalidated and refetched (T043). This is the first real job-backed consumer of the
// useAction -> ConfirmDialog -> JobPane chain (Phase 3's project.select was synchronous), so this
// test exercises that full chain rather than mocking any of its pieces.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { useToolsStatus } from "@/api/tools";
import { ToolActionPanel } from "@/modules/tools/actions";
import {
  buildConfirmationTicket,
  buildEffectPreview,
  buildJobRecord,
  buildToolDetail,
  buildToolStatusEntry,
  wrapEnvelope,
} from "./msw/fixtures";
import { jobStreamHandler, toolsStatusHandler } from "./msw/handlers";
import { server } from "./msw/server";

// Mounts an active useToolsStatus() observer alongside the action panel, mirroring how ToolsModule's
// table stays mounted behind the drawer in the real app — this is what makes the post-job
// invalidateQueries() call actually trigger a refetch instead of just marking the cache stale.
function ToolsPageHarness() {
  useToolsStatus();
  return <ToolActionPanel tool={buildToolDetail({ key: "git", status: statusOf("missing") })} />;
}

function statusOf(state: "missing" | "installed") {
  return {
    state,
    current_version: state === "installed" ? "2.44.0" : null,
    latest_version: "2.45.0",
    checked_at: "2026-01-01T00:00:00Z",
  };
}

function renderHarness() {
  const queryClient = new QueryClient();
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ToolsPageHarness />
    </QueryClientProvider>,
  );
  return { user };
}

describe("ToolActionPanel", () => {
  it("does not execute the install action until the user confirms the ConfirmDialog", async () => {
    let executeCallCount = 0;
    server.use(
      toolsStatusHandler([buildToolStatusEntry("git", "missing")]),
      http.post("/api/actions/tools.install/prepare", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "tools.install",
              effect_preview: buildEffectPreview({ summary: "Install Git 2.45.0" }),
            }),
          ),
        ),
      ),
      http.post("/api/actions/tools.install/execute", () => {
        executeCallCount += 1;
        return HttpResponse.json(wrapEnvelope({ job_id: "job-git-install" }));
      }),
      http.get("/api/jobs/job-git-install", () =>
        HttpResponse.json(wrapEnvelope(buildJobRecord("queued", { job_id: "job-git-install" }))),
      ),
      jobStreamHandler("job-git-install", [], { keepOpen: true }),
    );
    const { user } = renderHarness();

    await user.click(screen.getByRole("button", { name: "Install" }));

    expect(await screen.findByText("Install Git 2.45.0")).toBeInTheDocument();
    expect(executeCallCount).toBe(0);

    await user.click(screen.getByRole("button", { name: "Install Git" }));

    expect(await screen.findByText("job-git-install")).toBeInTheDocument();
    expect(executeCallCount).toBe(1);
  });

  it("invalidates and refetches the tools status query once the job reaches a terminal state", async () => {
    let statusFetchCount = 0;
    server.use(
      http.get("/api/tools/status", () => {
        statusFetchCount += 1;
        return HttpResponse.json(wrapEnvelope({ items: [buildToolStatusEntry("git", "missing")] }));
      }),
      http.post("/api/actions/tools.install/prepare", () =>
        HttpResponse.json(wrapEnvelope(buildConfirmationTicket({ action_id: "tools.install" }))),
      ),
      http.post("/api/actions/tools.install/execute", () =>
        HttpResponse.json(wrapEnvelope({ job_id: "job-git-install" })),
      ),
      http.get("/api/jobs/job-git-install", () =>
        HttpResponse.json(wrapEnvelope(buildJobRecord("succeeded", { job_id: "job-git-install" }))),
      ),
      jobStreamHandler("job-git-install", [
        { event: "state", data: { state: "succeeded" }, id: 1 },
      ]),
    );
    const { user } = renderHarness();

    await waitFor(() => expect(statusFetchCount).toBeGreaterThan(0));
    const initialFetchCount = statusFetchCount;

    await user.click(screen.getByRole("button", { name: "Install" }));
    await screen.findByRole("alertdialog");
    await user.click(screen.getByRole("button", { name: "Install Git" }));

    await screen.findByText("succeeded");
    await waitFor(() => expect(statusFetchCount).toBeGreaterThan(initialFetchCount));
  });
});
