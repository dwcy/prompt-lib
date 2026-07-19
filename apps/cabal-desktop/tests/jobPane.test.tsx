// Component test: JobPane across queued/running/succeeded/failed/cancelled states, driven through
// the real network/SSE layer via MSW (GET /api/jobs/:id + a streamed GET /api/jobs/:id/stream body)
// rather than mocking src/lib/sse.ts, since JobPane wires useEventStream directly with no injection seam.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { JobState } from "@/api/schemas";
import { JobPane } from "@/components/JobPane";
import { buildJobRecord, wrapEnvelope } from "./msw/fixtures";
import { jobStreamHandler } from "./msw/handlers";
import { server } from "./msw/server";

function renderJobPane(jobId: string) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <JobPane jobId={jobId} />
    </QueryClientProvider>,
  );
}

function mockJob(jobId: string, state: JobState) {
  server.use(
    http.get(`/api/jobs/${jobId}`, () =>
      HttpResponse.json(wrapEnvelope(buildJobRecord(state, { job_id: jobId }))),
    ),
  );
}

describe("JobPane", () => {
  it("shows the queued state with a cancel button and no output yet", async () => {
    mockJob("job-queued", "queued");
    server.use(jobStreamHandler("job-queued", [], { keepOpen: true }));

    renderJobPane("job-queued");

    expect(await screen.findByText("queued")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel job" })).toBeInTheDocument();
  });

  it("renders streamed output lines and a gap indicator while running, with cancel available", async () => {
    mockJob("job-running", "running");
    server.use(
      jobStreamHandler(
        "job-running",
        [
          { event: "state", data: { state: "running" }, id: 1 },
          { event: "output", data: { line: "Installing dependencies…", seq: 1 }, id: 2 },
          { event: "output", data: { line: "Applying config…", seq: 2 }, id: 3 },
          { event: "gap", data: { dropped: 5 }, id: 4 },
        ],
        { keepOpen: true },
      ),
    );

    renderJobPane("job-running");

    expect(await screen.findByText("Installing dependencies…")).toBeInTheDocument();
    expect(screen.getByText("Applying config…")).toBeInTheDocument();
    expect(screen.getByText("5 lines dropped during reconnect")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel job" })).toBeInTheDocument();
  });

  it.each<JobState>([
    "succeeded",
    "failed",
    "cancelled",
  ])("shows the %s terminal state with no cancel button", async (state) => {
    const jobId = `job-${state}`;
    mockJob(jobId, state);
    server.use(jobStreamHandler(jobId, [{ event: "state", data: { state }, id: 1 }]));

    renderJobPane(jobId);

    expect(await screen.findByText(state)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel job" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yes, cancel" })).not.toBeInTheDocument();
  });
});
