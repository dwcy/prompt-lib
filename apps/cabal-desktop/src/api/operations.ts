import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export const mcpEnvStatusSchema = z.object({
  name: z.string(),
  present: z.boolean(),
});

export const mcpServerSchema = z.object({
  name: z.string(),
  scopes: z.array(z.string()),
  status: z.enum(["connected", "error", "pending", "inactive"]),
  active: z.boolean(),
  pending: z.boolean(),
  command: z.string(),
  env_required: z.array(z.string()),
  env_status: z.array(mcpEnvStatusSchema),
  env_present: z.boolean(),
  is_plugin: z.boolean(),
  plugin_id: z.string().nullable(),
  plugin_enabled: z.boolean().nullable(),
  plugin_scope: z.string().nullable(),
  removable_scopes: z.array(z.string()),
  actions_available: z.array(z.string()),
  global_action_label: z.string(),
});

export const mcpPayloadSchema = z.object({
  servers: z.array(mcpServerSchema),
  counts: z.object({
    total: z.number(),
    connected: z.number(),
    pending: z.number(),
    inactive: z.number(),
    error: z.number(),
  }),
  project_dir: z.string().nullable(),
});

export const mcpStatusPayloadSchema = z.object({
  server: mcpServerSchema.nullable(),
  project_dir: z.string().nullable(),
});

export const servicePrereqSchema = z.object({
  key: z.string(),
  ok: z.boolean(),
  message: z.string(),
});

export const serviceStateSchema = z.enum([
  "running",
  "stopped",
  "not_set_up",
  "blocked",
  "info_only",
]);

export const serviceRowSchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  state: serviceStateSchema,
  detail: z.string(),
  run_command: z.string(),
  source_url: z.string(),
  runnable: z.boolean(),
  depends_on: z.array(z.string()),
  install_path: z.string(),
  console_name: z.string(),
  pid: z.number().nullable(),
  started_by_app: z.boolean(),
  prereqs: z.array(servicePrereqSchema),
  log_stream_available: z.boolean(),
  log_path: z.string(),
  log_present: z.boolean(),
  dashboard_handoff: z.boolean(),
  dashboard_command: z.string().nullable(),
  default_port: z.number().nullable(),
});

export const servicesPayloadSchema = z.object({
  services: z.array(serviceRowSchema),
  counts: z.object({
    total: z.number(),
    running: z.number(),
    stopped: z.number(),
    not_set_up: z.number(),
    blocked: z.number(),
  }),
});

export const runningWebAppSchema = z.object({
  port: z.number().int().positive(),
  pid: z.number().int().positive(),
  app_name: z.string(),
  location: z.string().nullable(),
  address: z.string(),
  started_at: z.number(),
});

export const runningWebAppsPayloadSchema = z.object({
  apps: z.array(runningWebAppSchema),
  count: z.number().int().nonnegative(),
});

export const dockerAppSchema = z.object({
  container_id: z.string(),
  name: z.string(),
  image: z.string(),
  state: z.string(),
  status: z.string(),
  health: z.string().nullable(),
  ports: z.string(),
  project: z.string().nullable(),
  service: z.string().nullable(),
  location: z.string().nullable(),
  can_start: z.boolean(),
  can_stop: z.boolean(),
});

export const dockerAppsPayloadSchema = z.object({
  available: z.boolean(),
  daemon_running: z.boolean(),
  message: z.string().nullable(),
  containers: z.array(dockerAppSchema),
  counts: z.object({
    total: z.number().int().nonnegative(),
    running: z.number().int().nonnegative(),
    stopped: z.number().int().nonnegative(),
    other: z.number().int().nonnegative(),
  }),
});

export const serviceDashboardSchema = z.object({
  key: z.string(),
  argv: z.array(z.string()).nullable(),
  message: z.string(),
  available: z.boolean(),
});

export type McpServer = z.infer<typeof mcpServerSchema>;
export type McpPayload = z.infer<typeof mcpPayloadSchema>;
export type ServiceRow = z.infer<typeof serviceRowSchema>;
export type ServiceState = z.infer<typeof serviceStateSchema>;
export type ServicesPayload = z.infer<typeof servicesPayloadSchema>;
export type RunningWebApp = z.infer<typeof runningWebAppSchema>;
export type RunningWebAppsPayload = z.infer<typeof runningWebAppsPayloadSchema>;
export type DockerApp = z.infer<typeof dockerAppSchema>;
export type DockerAppsPayload = z.infer<typeof dockerAppsPayloadSchema>;

export function useMcpServers() {
  return useQuery({
    queryKey: queryKeys.global("mcp"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/mcp", mcpPayloadSchema, signal);
      return requireData(envelope, "mcp");
    },
    staleTime: 20_000,
  });
}

export function useMcpServerStatus(name: string | null) {
  return useQuery({
    queryKey: queryKeys.global("mcp", "status", name ?? "none"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/mcp/${encodeURIComponent(name ?? "")}/status`,
        mcpStatusPayloadSchema,
        signal,
      );
      return requireData(envelope, "mcp status");
    },
    enabled: name !== null,
    staleTime: 10_000,
  });
}

export function useServices() {
  return useQuery({
    queryKey: queryKeys.global("services"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/services", servicesPayloadSchema, signal);
      return requireData(envelope, "services");
    },
    staleTime: 10_000,
  });
}

export function useRunningWebApps() {
  return useQuery({
    queryKey: queryKeys.global("runningWebApps"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        "/api/services/running-apps",
        runningWebAppsPayloadSchema,
        signal,
      );
      return requireData(envelope, "running web apps");
    },
    refetchInterval: 5_000,
    staleTime: 3_000,
  });
}

export function useDockerApps() {
  return useQuery({
    queryKey: queryKeys.global("dockerApps"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/services/docker-apps", dockerAppsPayloadSchema, signal);
      return requireData(envelope, "Docker apps");
    },
    refetchInterval: 5_000,
    staleTime: 3_000,
  });
}

export function useServiceDashboard(key: string | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.global("services", "dashboard", key ?? "none"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/services/${encodeURIComponent(key ?? "")}/dashboard`,
        serviceDashboardSchema,
        signal,
      );
      return requireData(envelope, "service dashboard");
    },
    enabled: key !== null && enabled,
    staleTime: 10_000,
  });
}
