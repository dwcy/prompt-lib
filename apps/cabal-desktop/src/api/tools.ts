// Zod schemas + TanStack Query hooks for the Tools catalog, bulk async status, and per-tool detail
// routes (catalog metadata and status are separate endpoints joined client-side — see toolsFilters.ts).
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export const toolSourceStateSchema = z.enum(["verified", "manual_required", "unavailable"]);
export const toolInstallChannelSchema = z.enum([
  "package",
  "desktop_app",
  "container_service",
  "embedded_engine",
  "manual",
  "none",
]);
export const toolStatusStateSchema = z.enum([
  "installed",
  "update_available",
  "missing",
  "unsupported",
  "manual_required",
  "error",
]);

export const toolCatalogItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  category: z.string(),
  description: z.string(),
  source_url: z.string().nullable(),
  source_state: toolSourceStateSchema,
  install_channel: toolInstallChannelSchema,
  platforms: z.array(z.string()),
  badges: z.array(z.string()),
  safety_notes: z.array(z.string()),
  backup_policy: z.string().nullable(),
  versions_available: z.array(z.string()),
});

export const toolStatusSchema = z.object({
  state: toolStatusStateSchema,
  current_version: z.string().nullable(),
  latest_version: z.string().nullable(),
  checked_at: z.string(),
});

export const toolStatusEntrySchema = toolStatusSchema.extend({ key: z.string() });

export const toolCatalogPayloadSchema = z.object({
  items: z.array(toolCatalogItemSchema),
  category_counts: z.record(z.string(), z.number()),
  channel_counts: z.record(z.string(), z.number()),
});

export const toolStatusListSchema = z.object({
  items: z.array(toolStatusEntrySchema),
});

export const toolDetailSchema = toolCatalogItemSchema.extend({
  status: toolStatusSchema,
});

export type ToolSourceState = z.infer<typeof toolSourceStateSchema>;
export type ToolInstallChannel = z.infer<typeof toolInstallChannelSchema>;
export type ToolStatusState = z.infer<typeof toolStatusStateSchema>;
export type ToolCatalogItem = z.infer<typeof toolCatalogItemSchema>;
export type ToolStatus = z.infer<typeof toolStatusSchema>;
export type ToolStatusEntry = z.infer<typeof toolStatusEntrySchema>;
export type ToolCatalogPayload = z.infer<typeof toolCatalogPayloadSchema>;
export type ToolStatusList = z.infer<typeof toolStatusListSchema>;
export type ToolDetail = z.infer<typeof toolDetailSchema>;

// Global module (ignores project context, per data-model.md's relationships bullet).
export function useToolsCatalog() {
  return useQuery({
    queryKey: queryKeys.global("tools", "catalog"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/tools", toolCatalogPayloadSchema, signal);
      return requireData(envelope, "tools catalog");
    },
    staleTime: 60_000,
  });
}

// Deliberately separate from useToolsCatalog: the status probe sweep is slower than the catalog
// metadata read (FR-025), so the table joins these two independent queries at render time instead
// of blocking on one combined fetch — see toolsFilters.ts's joinToolsWithStatus.
export function useToolsStatus() {
  return useQuery({
    queryKey: queryKeys.global("tools", "status"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/tools/status", toolStatusListSchema, signal);
      return requireData(envelope, "tools status");
    },
    staleTime: 15_000,
  });
}

export function useToolDetail(key: string | null) {
  return useQuery({
    queryKey: queryKeys.global("tools", "detail", key ?? "none"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(`/api/tools/${key}`, toolDetailSchema, signal);
      return requireData(envelope, `tool detail ${key}`);
    },
    enabled: key !== null,
    staleTime: 15_000,
  });
}
