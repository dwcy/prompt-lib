// Multi-source environment browser client: listing (names + metadata only) and the
// single-entry reveal mutation. `variableEntrySchema` deliberately declares no `value`
// member — the listing surface cannot carry one, and a backend that started sending one
// would be dropped here rather than rendered (FR-008).
import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, apiPost, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const sourceKindSchema = z.enum([
  "repo_file",
  "dotnet_secrets",
  "dotnet_launch_profile",
  "azure_keyvault",
  "azure_app_settings",
  "vercel",
  "github",
]);

// The listing route emits only these three: a source with no link signal is absent from the
// response entirely (FR-005), so "not_linked" never appears on the wire.
export const sourceStateSchema = z.enum(["ok", "empty", "degraded"]);

export const retrievabilitySchema = z.enum(["readable", "permission_gated", "never"]);

export const linkConfidenceSchema = z.enum(["explicit", "azd", "iac", "machine_default"]);

export const configLayerSchema = z.object({
  stack: z.string(),
  name: z.string(),
  rank: z.number(),
  wins: z.boolean(),
});

export const variableEntrySchema = z.object({
  name: z.string(),
  source_id: z.string(),
  container_id: z.string(),
  description: z.string(),
  target: z.string().nullable(),
  entry_type: z.string().nullable(),
  updated_at: z.string().nullable(),
  retrievability: retrievabilitySchema,
  retrievability_reason: z.string().nullable(),
  is_reference: z.boolean(),
});

export const variableContainerSchema = z.object({
  id: z.string(),
  source_id: z.string(),
  label: z.string(),
  qualifier: z.string().nullable(),
  layer: configLayerSchema.nullable(),
  entries: z.array(variableEntrySchema),
});

export const variableSourceSchema = z.object({
  id: z.string(),
  kind: sourceKindSchema,
  label: z.string(),
  state: sourceStateSchema,
  hint: z.string().nullable(),
  outside_repository: z.boolean(),
  link_confidence: linkConfidenceSchema.nullable(),
  link_reason: z.string().nullable(),
  containers: z.array(variableContainerSchema),
});

export const envSourcesPayloadSchema = z.object({
  sources: z.array(variableSourceSchema),
  project: z.string().nullable(),
  scanned_at: z.string(),
  notices: z.array(z.string()).default([]),
});

export const revealStatusSchema = z.enum(["revealed", "denied", "unavailable"]);

export const revealResultSchema = z.object({
  status: revealStatusSchema,
  value: z.string().nullable(),
  reason: z.string().nullable(),
  is_reference: z.boolean(),
});

export const azureLinkPayloadSchema = z.object({
  subscription_id: z.string().nullable(),
  resource_group: z.string().nullable(),
  confidence: linkConfidenceSchema,
  reason: z.string(),
  is_explicit: z.boolean(),
});

export type SourceKind = z.infer<typeof sourceKindSchema>;
export type SourceState = z.infer<typeof sourceStateSchema>;
export type Retrievability = z.infer<typeof retrievabilitySchema>;
export type LinkConfidence = z.infer<typeof linkConfidenceSchema>;
export type ConfigLayer = z.infer<typeof configLayerSchema>;
export type VariableEntry = z.infer<typeof variableEntrySchema>;
export type VariableContainer = z.infer<typeof variableContainerSchema>;
export type VariableSource = z.infer<typeof variableSourceSchema>;
export type EnvSourcesPayload = z.infer<typeof envSourcesPayloadSchema>;
export type RevealStatus = z.infer<typeof revealStatusSchema>;
export type RevealResult = z.infer<typeof revealResultSchema>;
export type AzureLinkPayload = z.infer<typeof azureLinkPayloadSchema>;

export interface RevealRequest {
  source_id: string;
  container_id: string;
  name: string;
}

export function useEnvSources() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("envSources", projectPath, "sources"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/env/sources", envSourcesPayloadSchema, signal);
      return requireData(envelope, "environment sources");
    },
    enabled: projectPath !== null,
    staleTime: 15_000,
  });
}

// Refetches ONE source with the far larger budget the backend grants a deliberate refresh
// (FR-038). The initial listing degrades fast so the page paints inside SC-010's 3s; a source
// that genuinely takes tens of seconds to enumerate — an Azure subscription with several key
// vaults — becomes usable by asking for it on its own.
export function useRefreshSource() {
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const params = new URLSearchParams({ source: sourceId });
      const envelope = await apiGet(
        `/api/env/sources?${params.toString()}`,
        envSourcesPayloadSchema,
      );
      const payload = requireData(envelope, "environment source refresh");
      return payload.sources.find((source) => source.id === sourceId) ?? null;
    },
  });
}

// Deliberately a mutation and not a query: a revealed value must never enter the query
// cache, where it would survive the tab change that FR-014 requires re-masks it.
export function useRevealValue() {
  return useMutation({
    mutationFn: async (request: RevealRequest) => {
      const envelope = await apiPost("/api/env/reveal", revealResultSchema, request);
      return requireData(envelope, "environment reveal");
    },
  });
}
