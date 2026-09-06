import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { SessionsModule } from "@/modules/sessions/SessionsModule";
import { buildConfirmationTicket, buildEffectPreview, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

const SESSION_ITEMS = [
  buildSession({
    session_id: "session-alpha",
    title: "Alpha session",
    cost_usd: 1.25,
    tool_error_count: 2,
  }),
  buildSession({
    session_id: "session-beta",
    title: "Beta session",
    cost_usd: 4.5,
    files_written: 3,
  }),
];

function renderModule() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <SessionsModule />
    </QueryClientProvider>,
  );
  return { user };
}

function installSessionHandlers(onSort?: (sort: string) => void) {
  server.use(
    http.get("/api/sessions", ({ request }) => {
      const sort = new URL(request.url).searchParams.get("sort") ?? "";
      onSort?.(sort);
      return HttpResponse.json(
        wrapEnvelope({
          totals: {
            session_count: 2,
            tokens_in: 2_000,
            tokens_out: 800,
            cache_read_tokens: 400,
            cache_write_tokens: 100,
            cost_usd: 5.75,
            duration_seconds: 180,
            files_written: 3,
            agent_count: 1,
          },
          items: SESSION_ITEMS,
          next_cursor: null,
          page_size: 50,
          sort,
          project: "prompt-lib",
        }),
      );
    }),
    http.get("/api/sessions/:sessionId", ({ params, request }) => {
      const tab = new URL(request.url).searchParams.get("tab") ?? "overview";
      return HttpResponse.json(
        wrapEnvelope({
          session_id: String(params.sessionId),
          tab,
          payload: tab === "overview" ? { models: [] } : {},
          entry_count: 0,
        }),
      );
    }),
  );
}

describe("SessionsModule", () => {
  it("keeps a thousand-session dataset bounded to one server page", async () => {
    const requestedCursors: Array<string | null> = [];
    server.use(
      http.get("/api/sessions", ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        requestedCursors.push(cursor);
        const offset = cursor === null ? 0 : Number(cursor);
        const items = Array.from({ length: 50 }, (_, index) =>
          buildSession({
            session_id: `session-${offset + index}`,
            title: `bounded-session-${offset + index}`,
          }),
        );
        return HttpResponse.json(
          wrapEnvelope({
            totals: {
              session_count: 1_000,
              tokens_in: 10_000,
              tokens_out: 5_000,
              cache_read_tokens: 0,
              cache_write_tokens: 0,
              cost_usd: 0,
              duration_seconds: 0,
              files_written: 0,
              agent_count: 0,
            },
            items,
            next_cursor: offset < 950 ? String(offset + 50) : null,
            page_size: 50,
            sort: "date_desc",
            project: null,
          }),
        );
      }),
      http.get("/api/sessions/:sessionId", ({ params }) =>
        HttpResponse.json(
          wrapEnvelope({
            session_id: String(params.sessionId),
            tab: "overview",
            payload: { models: [] },
            entry_count: 0,
          }),
        ),
      ),
    );
    const { user } = renderModule();

    expect(await screen.findByTitle("bounded-session-0")).toBeInTheDocument();
    // The row list is virtualized (only the visible window + overscan mounts, not all 50 at
    // once), so this checks the page is bounded rather than asserting an exact DOM node count.
    const renderedRows = screen.getAllByTitle(/^bounded-session-\d+$/);
    expect(renderedRows.length).toBeGreaterThan(0);
    expect(renderedRows.length).toBeLessThanOrEqual(50);
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByTitle("bounded-session-50")).toBeInTheDocument();
    expect(requestedCursors).toEqual([null, "50"]);
    expect(screen.queryByTitle("bounded-session-0")).not.toBeInTheDocument();
  });

  it("exposes active lenses and requests the selected comparison sort", async () => {
    const requestedSorts: string[] = [];
    installSessionHandlers((sort) => requestedSorts.push(sort));
    const { user } = renderModule();

    expect(await screen.findByRole("button", { name: "all · 2" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "errors · 1" }));
    expect(screen.getByRole("button", { name: "errors · 1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Cost" }));
    await waitFor(() => expect(requestedSorts).toContain("cost_desc"));
    expect(screen.getByRole("button", { name: "Cost" })).toHaveAttribute("aria-pressed", "true");
  });

  it("requires the prepared destructive preview before deleting a transcript", async () => {
    let executeCalls = 0;
    installSessionHandlers();
    server.use(
      http.post("/api/actions/sessions.delete/prepare", () =>
        HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "sessions.delete",
              effect_preview: buildEffectPreview({
                summary: "Delete transcript session-alpha",
                files_changed: [],
                scopes: ["session history"],
                backup: null,
                removals: ["session-alpha.jsonl"],
              }),
            }),
          ),
        ),
      ),
      http.post("/api/actions/sessions.delete/execute", () => {
        executeCalls += 1;
        return HttpResponse.json(wrapEnvelope({ job_id: "job-delete-session" }));
      }),
    );
    const { user } = renderModule();

    await screen.findByRole("heading", { name: "Alpha session" });
    await user.click(screen.getByRole("button", { name: "Delete session" }));

    expect(await screen.findByText("Delete transcript session-alpha")).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toHaveClass("confirm-dialog--destructive");
    expect(executeCalls).toBe(0);

    await user.click(screen.getByRole("button", { name: "Delete Session Transcript" }));
    await waitFor(() => expect(executeCalls).toBe(1));
  });
});

function buildSession(overrides: Record<string, unknown>) {
  return {
    session_id: "session",
    project: "prompt-lib",
    branch: "015-web-ui-overhaul",
    title: "Session",
    started_at: "2026-07-13T12:00:00Z",
    duration_seconds: 90,
    cost_usd: 0,
    tokens_in: 1_000,
    tokens_out: 400,
    cache_read_tokens: 200,
    cache_write_tokens: 50,
    agent_count: 1,
    skill_count: 2,
    tool_count: 3,
    hook_count: 1,
    message_count: 12,
    tool_error_count: 0,
    files_written: 0,
    parent_id: null,
    child_ids: [],
    has_raw_log: true,
    file_size_bytes: 1_024,
    ...overrides,
  };
}
