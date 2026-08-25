import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { ApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { healthPayloadSchema } from "@/api/schemas";
import { envPayloadSchema } from "@/api/securityEnvironment";
import { toolCatalogPayloadSchema, toolStatusListSchema } from "@/api/tools";

export const machineToolSchema = z.object({
  key: z.string(),
  label: z.string(),
  installed: z.boolean(),
  version: z.string().nullable(),
});

export const terminalShellSchema = z.object({
  key: z.string(),
  label: z.string(),
  installed: z.boolean(),
  version: z.string().nullable(),
  path: z.string().nullable(),
  active: z.boolean(),
  configured: z.boolean(),
  profile_path: z.string().nullable(),
});

export const terminalApplicationSchema = z.object({
  key: z.string(),
  label: z.string(),
  installed: z.boolean(),
  version: z.string().nullable(),
  path: z.string().nullable(),
  configured: z.boolean(),
  settings_path: z.string().nullable(),
  active: z.boolean(),
});

export const terminalModificationSchema = z.object({
  key: z.string(),
  label: z.string(),
  detail: z.string(),
  kind: z.string(),
  source: z.string(),
});

export const terminalOverviewSchema = z.object({
  default_terminal: z.string().nullable(),
  default_profile: z.string().nullable(),
  shells: z.array(terminalShellSchema),
  applications: z.array(terminalApplicationSchema),
  modifications: z.array(terminalModificationSchema),
});

export const systemOverviewSchema = z.object({
  cabal: z.object({
    version: z.string(),
    status: z.string(),
    local_hash: z.string().nullable(),
    latest_hash: z.string().nullable(),
    latest_date: z.string(),
    behind_count: z.number().nullable(),
    branch: z.string().nullable(),
    subject: z.string(),
  }),
  machine: z.object({
    os: z.string(),
    release: z.string(),
    package_manager: z.string().nullable(),
    tools: z.array(machineToolSchema),
  }),
  // Optional during a rolling frontend/backend upgrade; normalized immediately below.
  terminal: terminalOverviewSchema.optional(),
});

type SystemOverviewWire = z.infer<typeof systemOverviewSchema>;
export type TerminalOverview = z.infer<typeof terminalOverviewSchema>;
export type TerminalShell = z.infer<typeof terminalShellSchema>;
export type TerminalApplication = z.infer<typeof terminalApplicationSchema>;
export type TerminalModification = z.infer<typeof terminalModificationSchema>;
export type SystemOverview = Omit<SystemOverviewWire, "terminal"> & {
  terminal: TerminalOverview;
};
export type MachineTool = z.infer<typeof machineToolSchema>;

const EMPTY_TERMINAL: TerminalOverview = {
  default_terminal: null,
  default_profile: null,
  shells: [],
  applications: [],
  modifications: [],
};

export function useSystemOverview() {
  return useQuery({
    queryKey: queryKeys.global("system", "overview"),
    queryFn: async ({ signal }) => {
      try {
        const envelope = await apiGet("/api/system/overview", systemOverviewSchema, signal);
        return normalizeSystemOverview(requireData(envelope, "system overview"));
      } catch (error) {
        if (!(error instanceof ApiError) || error.httpStatus !== 404) throw error;
        return loadLegacySystemOverview(signal);
      }
    },
    staleTime: 60_000,
  });
}

async function loadLegacySystemOverview(signal: AbortSignal): Promise<SystemOverview> {
  const [healthEnvelope, envEnvelope, catalogEnvelope, statusEnvelope] = await Promise.all([
    apiGet("/api/health", healthPayloadSchema, signal),
    apiGet("/api/env?scope=curated", envPayloadSchema, signal),
    apiGet("/api/tools", toolCatalogPayloadSchema, signal),
    apiGet("/api/tools/status", toolStatusListSchema, signal),
  ]);
  const health = requireData(healthEnvelope, "health");
  const environment = requireData(envEnvelope, "environment");
  const catalog = requireData(catalogEnvelope, "tools catalog");
  const statuses = requireData(statusEnvelope, "tools status");
  const byKey = new Map(statuses.items.map((item) => [item.key, item]));

  return {
    cabal: {
      version: health.version,
      status: "backend_restart_required",
      local_hash: null,
      latest_hash: null,
      latest_date: "",
      behind_count: null,
      branch: null,
      subject: "Restart Cabal to load revision metadata",
    },
    machine: {
      os: environment.platform,
      release: "",
      package_manager: detectPackageManager(byKey),
      tools: catalog.items.map((item) => {
        const status = byKey.get(item.key);
        return {
          key: item.key,
          label: item.label,
          installed: status?.state === "installed" || status?.state === "update_available",
          version: status?.current_version ?? null,
        };
      }),
    },
    terminal: EMPTY_TERMINAL,
  };
}

function normalizeSystemOverview(payload: SystemOverviewWire): SystemOverview {
  return { ...payload, terminal: payload.terminal ?? EMPTY_TERMINAL };
}

function detectPackageManager(
  statuses: Map<string, z.infer<typeof toolStatusListSchema>["items"][number]>,
): string | null {
  const candidates = ["winget", "scoop", "choco", "brew", "apt", "dnf", "pacman"];
  return (
    candidates.find((key) => {
      const state = statuses.get(key)?.state;
      return state === "installed" || state === "update_available";
    }) ?? null
  );
}
