import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { LogStream } from "@/components/LogStream";
import { McpModule } from "@/modules/mcp/McpModule";
import { ServicesModule } from "@/modules/services/ServicesModule";
import { buildConfirmationTicket, buildEffectPreview, wrapEnvelope } from "./msw/fixtures";
import { server } from "./msw/server";

function renderModule(module: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(<QueryClientProvider client={queryClient}>{module}</QueryClientProvider>);
  return { user };
}

const MULTI_SCOPE_SERVER = {
  name: "workspace-files",
  scopes: ["global", "project"],
  status: "connected",
  active: true,
  pending: false,
  command: "mcp-files C:/projects/prompt-lib",
  env_required: [],
  env_status: [],
  env_present: true,
  is_plugin: false,
  plugin_id: null,
  plugin_enabled: null,
  plugin_scope: null,
  removable_scopes: ["global", "project"],
  actions_available: ["disable"],
  global_action_label: "Activate globally",
};

describe("MCP and service workflows", () => {
  it("renders service output and an explicit replay gap", () => {
    render(
      <LogStream
        connectionState="open"
        events={[
          { event: "output", id: 4, data: { line: "service ready", seq: 4 } },
          { event: "gap", id: null, data: { dropped: 3 } },
          { event: "output", id: 8, data: { line: "request handled", seq: 8 } },
        ]}
      />,
    );

    expect(screen.getByText("service ready")).toBeInTheDocument();
    expect(screen.getByText("request handled")).toBeInTheDocument();
    expect(screen.getByText("3 lines dropped during reconnect")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("maps a multi-scope connector to one prepared ownership-layer removal", async () => {
    let preparedScope: unknown = null;
    server.use(
      http.get("/api/mcp", () =>
        HttpResponse.json(
          wrapEnvelope({
            servers: [MULTI_SCOPE_SERVER],
            counts: { total: 1, connected: 1, pending: 0, inactive: 0, error: 0 },
            project_dir: "C:/projects/prompt-lib",
          }),
        ),
      ),
      http.get("/api/mcp/:name/status", () =>
        HttpResponse.json(
          wrapEnvelope({
            server: MULTI_SCOPE_SERVER,
            project_dir: "C:/projects/prompt-lib",
          }),
        ),
      ),
      http.post("/api/actions/mcp.disable/prepare", async ({ request }) => {
        const body = (await request.json()) as { scope?: unknown };
        preparedScope = body.scope;
        return HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "mcp.disable",
              effect_preview: buildEffectPreview({
                summary: `Remove ${String(body.scope)} ownership for workspace-files`,
                files_changed: ["~/.claude.json"],
                scopes: [String(body.scope)],
                removals: [],
              }),
            }),
          ),
        );
      }),
    );
    const { user } = renderModule(<McpModule />);

    const allFilter = await screen.findByRole("button", { name: "all" });
    expect(allFilter).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /workspace-files/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Disable" }));

    expect(
      await screen.findByRole("dialog", { name: "Remove one workspace-files scope" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Remove this scope" })).toHaveLength(2);

    await user.click(screen.getAllByRole("button", { name: "Remove this scope" })[0]);

    expect(
      await screen.findByText("Remove global ownership for workspace-files"),
    ).toBeInTheDocument();
    expect(preparedScope).toBe("global");
  });

  it("keeps service startup unavailable until prerequisites are ready", async () => {
    server.use(
      http.get("/api/services", () =>
        HttpResponse.json(
          wrapEnvelope({
            services: [
              buildService({
                key: "indexer",
                label: "Knowledge indexer",
                state: "blocked",
                prereqs: [{ key: "python", ok: false, message: "Python runtime is missing" }],
              }),
              buildService({ key: "event-bus", label: "Event bus", state: "stopped" }),
            ],
            counts: { total: 2, running: 0, stopped: 1, not_set_up: 0, blocked: 1 },
          }),
        ),
      ),
    );
    const { user } = renderModule(<ServicesModule />);

    expect(await screen.findByText("Python runtime is missing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start service" })).not.toBeInTheDocument();

    const readyService = screen.getByRole("button", { name: /Event bus/ });
    await user.click(readyService);

    expect(readyService).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Start service" })).toBeEnabled();
  });
});

function buildService(overrides: Record<string, unknown>) {
  return {
    key: "service",
    label: "Service",
    description: "Local agent infrastructure",
    state: "stopped",
    detail: "ready",
    run_command: "service run",
    source_url: "https://example.test/service",
    runnable: true,
    depends_on: [],
    install_path: "C:/tools/service",
    console_name: "service",
    pid: null,
    started_by_app: false,
    prereqs: [],
    log_stream_available: false,
    log_path: "C:/logs/service.log",
    log_present: false,
    dashboard_handoff: false,
    dashboard_command: null,
    default_port: null,
    ...overrides,
  };
}
