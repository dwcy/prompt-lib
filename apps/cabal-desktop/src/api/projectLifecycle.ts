// Provider and init-wizard read hooks for US7; writes still use the shared action protocol.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export const providerAccountSchema = z.object({
  user: z.string(),
  host: z.string(),
  active: z.boolean(),
  valid: z.boolean(),
  storage: z.string(),
});

export const providerLoginSchema = z.object({
  state: z.string(),
  user_code: z.string().optional(),
  verification_uri: z.string().optional(),
  expires_at: z.number().nullable().optional(),
  scopes: z.array(z.string()).optional(),
  message: z.string().optional(),
});

export const providerStateSchema = z.object({
  authenticated: z.boolean(),
  accounts: z.array(providerAccountSchema),
  active_account: z.string().nullable(),
  gh_status: z.string(),
  login: providerLoginSchema,
});

export const providerRepoSchema = z.object({
  name: z.string(),
  owner: z.string(),
  full_name: z.string(),
  visibility: z.string(),
  updated_at: z.string(),
  url: z.string(),
  description: z.string(),
});

export const providerReposPayloadSchema = z.object({
  repos: z.array(providerRepoSchema),
  count: z.number(),
});

export const initTemplateSchema = z.object({
  id: z.string(),
  source: z.enum(["local", "github"]),
  label: z.string(),
  description: z.string(),
  owner: z.string(),
  name: z.string(),
  default_branch: z.string(),
  url: z.string(),
});

export const initTemplatesPayloadSchema = z.object({
  local: z.array(initTemplateSchema),
  github: z.array(initTemplateSchema),
  default_template: z.string().nullable(),
});

export const initStagedFileSchema = z.object({
  rel_path: z.string(),
  state: z.string(),
  selected: z.boolean(),
  origin: z.string(),
  size_bytes: z.number(),
});

export const initPlanSchema = z.object({
  destination: z.string(),
  parent: z.string(),
  name: z.string(),
  name_valid: z.boolean(),
  validation_message: z.string(),
  template: z.string(),
  template_source: z.enum(["local", "github"]),
  template_attribution: z.string(),
  staged_files: z.array(initStagedFileSchema),
  selected_count: z.number(),
  mcp_config: z.object({
    entries: z.number(),
    path: z.string(),
  }),
  handoff_prompt_present: z.boolean(),
  warnings: z.array(z.string()),
});

export type ProviderState = z.infer<typeof providerStateSchema>;
export type ProviderRepo = z.infer<typeof providerRepoSchema>;
export type InitTemplate = z.infer<typeof initTemplateSchema>;
export type InitPlan = z.infer<typeof initPlanSchema>;
export type InitStagedFile = z.infer<typeof initStagedFileSchema>;

export function useProviderState() {
  return useQuery({
    queryKey: queryKeys.global("provider", "state"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/provider", providerStateSchema, signal);
      return requireData(envelope, "provider");
    },
    staleTime: 10_000,
  });
}

export function useProviderRepos(query: string) {
  return useQuery({
    queryKey: queryKeys.global("provider", "repos", query),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams();
      if (query.trim().length > 0) params.set("q", query.trim());
      const path = `/api/provider/repos${params.size > 0 ? `?${params.toString()}` : ""}`;
      const envelope = await apiGet(path, providerReposPayloadSchema, signal);
      return requireData(envelope, "provider repos");
    },
    staleTime: 15_000,
  });
}

export function useInitTemplates() {
  return useQuery({
    queryKey: queryKeys.global("init", "templates"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/init/templates", initTemplatesPayloadSchema, signal);
      return requireData(envelope, "init templates");
    },
    staleTime: 60_000,
  });
}

export function useInitPlan(input: {
  dest: string;
  name: string;
  template: string | null;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.global("init", "plan", input.dest, input.name, input.template ?? ""),
    enabled: input.enabled && input.template !== null,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({
        dest: input.dest,
        name: input.name,
        template: input.template ?? "",
      });
      const envelope = await apiGet(`/api/init/plan?${params.toString()}`, initPlanSchema, signal);
      return requireData(envelope, "init plan");
    },
    staleTime: 5_000,
  });
}
