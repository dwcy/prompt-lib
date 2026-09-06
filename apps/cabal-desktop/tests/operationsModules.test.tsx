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

    // Both the table row and the detail panel now expose a Disable action (T3 redesign); either
    // triggers the same prepare/confirm flow, so the row's action (listed first in the DOM) is
    // the one this test drives.
    await user.click(screen.getAllByRole("button", { name: "Disable" })[0]);

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
      http.get("/api/services/running-apps", () =>
        HttpResponse.json(wrapEnvelope({ apps: [], count: 0 })),
      ),
      http.get("/api/services/docker-apps", () =>
        HttpResponse.json(wrapEnvelope(emptyDockerPayload())),
      ),
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
    renderModule(<ServicesModule />);

    // Action buttons are per-row and gated on that row's own prereqs (not on selection): the
    // blocked service exposes no Start action, while the ready service's is present and enabled.
    expect(await screen.findByText("Python runtime is missing")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Start" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
  });

  it("shows listening web apps and prepares a confirmed shutdown", async () => {
    let preparedParams: unknown = null;
    server.use(
      http.get("/api/services", () =>
        HttpResponse.json(
          wrapEnvelope({
            services: [],
            counts: { total: 0, running: 0, stopped: 0, not_set_up: 0, blocked: 0 },
          }),
        ),
      ),
      http.get("/api/services/running-apps", () =>
        HttpResponse.json(
          wrapEnvelope({
            apps: [
              {
                port: 5173,
                pid: 4242,
                app_name: "fixture-web",
                location: "C:/projects/fixture-web",
                address: "127.0.0.1",
                started_at: 1725000000.25,
              },
            ],
            count: 1,
          }),
        ),
      ),
      http.get("/api/services/docker-apps", () =>
        HttpResponse.json(wrapEnvelope(emptyDockerPayload())),
      ),
      http.post("/api/actions/services.running_app.stop/prepare", async ({ request }) => {
        preparedParams = await request.json();
        return HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "services.running_app.stop",
              effect_preview: buildEffectPreview({
                summary: "Shut down fixture-web on port 5173",
                scopes: ["services", "running-apps", "4242"],
                removals: ["fixture-web (PID 4242, port 5173)"],
                backup: "Restart the app from its location or original command",
              }),
            }),
          ),
        );
      }),
    );
    const { user } = renderModule(<ServicesModule />);

    expect(await screen.findByText("fixture-web")).toBeInTheDocument();
    expect(screen.getByText("C:/projects/fixture-web")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Shut down fixture-web on port 5173" }));

    expect(
      await screen.findByRole("alertdialog", { name: "Shut Down Web App" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Shut down fixture-web on port 5173")).toBeInTheDocument();
    expect(preparedParams).toEqual({ pid: 4242, port: 5173, started_at: 1725000000.25 });
  });

  it("hides OS processes by default and reveals them when the filter is turned off", async () => {
    server.use(
      http.get("/api/services", () =>
        HttpResponse.json(
          wrapEnvelope({
            services: [],
            counts: { total: 0, running: 0, stopped: 0, not_set_up: 0, blocked: 0 },
          }),
        ),
      ),
      http.get("/api/services/running-apps", () =>
        HttpResponse.json(
          wrapEnvelope({
            apps: [
              {
                port: 5173,
                pid: 4242,
                app_name: "fixture-web",
                location: "C:/projects/fixture-web",
                address: "127.0.0.1",
                started_at: 1725000000.25,
              },
              {
                port: 135,
                pid: 900,
                app_name: "svchost",
                location: "C:\\Windows\\System32",
                address: "127.0.0.1",
                started_at: 1725000000.25,
              },
            ],
            count: 2,
          }),
        ),
      ),
      http.get("/api/services/docker-apps", () =>
        HttpResponse.json(wrapEnvelope(emptyDockerPayload())),
      ),
    );
    const { user } = renderModule(<ServicesModule />);

    expect(await screen.findByText("fixture-web")).toBeInTheDocument();
    expect(screen.queryByText("svchost")).not.toBeInTheDocument();
    expect(screen.getByText("Hide OS processes (1 hidden)")).toBeInTheDocument();

    await user.click(screen.getByRole("switch", { name: "Hide OS processes" }));

    expect(await screen.findByText("svchost")).toBeInTheDocument();
    expect(screen.getByText("fixture-web")).toBeInTheDocument();
  });

  it("shows Docker containers in every state and prepares the matching lifecycle action", async () => {
    let preparedParams: unknown = null;
    server.use(
      http.get("/api/services", () =>
        HttpResponse.json(
          wrapEnvelope({
            services: [],
            counts: { total: 0, running: 0, stopped: 0, not_set_up: 0, blocked: 0 },
          }),
        ),
      ),
      http.get("/api/services/running-apps", () =>
        HttpResponse.json(wrapEnvelope({ apps: [], count: 0 })),
      ),
      http.get("/api/services/docker-apps", () =>
        HttpResponse.json(
          wrapEnvelope({
            available: true,
            daemon_running: true,
            message: null,
            containers: [
              buildDockerApp({ name: "fixture-web", state: "running", can_stop: true }),
              buildDockerApp({
                container_id: "b".repeat(64),
                name: "fixture-worker",
                state: "exited",
                status: "Exited (0)",
                ports: "",
                can_start: true,
              }),
            ],
            counts: { total: 2, running: 1, stopped: 1, other: 0 },
          }),
        ),
      ),
      http.post("/api/actions/services.docker.stop/prepare", async ({ request }) => {
        preparedParams = await request.json();
        return HttpResponse.json(
          wrapEnvelope(
            buildConfirmationTicket({
              action_id: "services.docker.stop",
              effect_preview: buildEffectPreview({
                summary: "Stop Docker container fixture-web",
                scopes: ["services", "docker", "a".repeat(64)],
                removals: [`Running container fixture-web (${"a".repeat(12)})`],
                backup: "Start the same Docker container again to recover",
              }),
            }),
          ),
        );
      }),
    );
    const { user } = renderModule(<ServicesModule />);

    expect(await screen.findByText("fixture-web")).toBeInTheDocument();
    expect(screen.getByText("fixture-worker")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start Docker container fixture-worker" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Stop Docker container fixture-web" }));

    expect(await screen.findByRole("alertdialog", { name: "Stop Docker App" })).toBeInTheDocument();
    expect(preparedParams).toEqual({ container_id: "a".repeat(64), expected_state: "running" });
  });
});

function emptyDockerPayload() {
  return {
    available: true,
    daemon_running: true,
    message: null,
    containers: [],
    counts: { total: 0, running: 0, stopped: 0, other: 0 },
  };
}

function buildDockerApp(overrides: Record<string, unknown>) {
  return {
    container_id: "a".repeat(64),
    name: "fixture",
    image: "fixture/app:latest",
    state: "running",
    status: "Up 2 minutes",
    health: "healthy",
    ports: "0.0.0.0:5173->5173/tcp",
    project: "fixture",
    service: "web",
    location: "C:/projects/fixture",
    can_start: false,
    can_stop: false,
    ...overrides,
  };
}

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
