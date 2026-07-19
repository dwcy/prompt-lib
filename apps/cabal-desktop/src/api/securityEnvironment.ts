import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const securityFindingSchema = z.object({
  key: z.string(),
  ecosystem: z.string(),
  package: z.string(),
  kind: z.string(),
  severity: z.string(),
  current: z.string(),
  target: z.string().nullable(),
  fix_available: z.boolean(),
  fix_command_preview: z.string(),
  detail: z.string(),
});

export const securityOutcomeSchema = z.object({
  ecosystem: z.string(),
  findings: z.array(securityFindingSchema),
  notices: z.array(z.string()),
});

export const securityScanSchema = z.object({
  project: z.string(),
  scanned_at: z.string(),
  cached: z.boolean(),
  ecosystems: z.array(z.string()),
  findings: z.array(securityFindingSchema),
  outcomes: z.array(securityOutcomeSchema),
  notices: z.array(z.string()),
  summary: z.object({
    total: z.number(),
    fixable: z.number(),
    by_severity: z.record(z.string(), z.number()),
    by_ecosystem: z.record(z.string(), z.number()),
  }),
});

export const envScopeSchema = z.enum(["curated", "system"]);
export const envEntrySchema = z.object({
  name: z.string(),
  value_redacted: z.string(),
  default: z.string(),
  is_path: z.boolean(),
  source: z.string(),
  editable: z.boolean(),
  description: z.string(),
});

export const envPayloadSchema = z.object({
  scope: envScopeSchema,
  entries: z.array(envEntrySchema),
  count: z.number(),
  editable_count: z.number(),
  platform: z.string(),
});

export const gitIdentityScopeSchema = z.enum(["global", "local"]);
export const gitIdentityRowSchema = z.object({
  scope: gitIdentityScopeSchema,
  name: z.string(),
  email: z.string(),
  available: z.boolean(),
  source: z.string(),
});

export const gitIdentityPayloadSchema = z.object({
  repo_root: z.string().nullable(),
  identities: z.array(gitIdentityRowSchema),
});

export const gitPolicySchema = z.object({
  agent_name: z.string(),
  agent_email: z.string(),
  allowed_types: z.array(z.string()),
  refuse_on_branches: z.array(z.string()),
  tags: z.object({
    agent_may_tag: z.boolean(),
    auto_push: z.boolean(),
  }),
});

export const gitPolicyPayloadSchema = z.object({
  policy: gitPolicySchema,
  source: z.string(),
  defaults: gitPolicySchema,
});

export type SecurityFinding = z.infer<typeof securityFindingSchema>;
export type SecurityScan = z.infer<typeof securityScanSchema>;
export type EnvScope = z.infer<typeof envScopeSchema>;
export type EnvEntry = z.infer<typeof envEntrySchema>;
export type EnvPayload = z.infer<typeof envPayloadSchema>;
export type GitIdentityScope = z.infer<typeof gitIdentityScopeSchema>;
export type GitIdentityRow = z.infer<typeof gitIdentityRowSchema>;
export type GitPolicy = z.infer<typeof gitPolicySchema>;

export function useSecurityScan(refreshToken: number) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("security", projectPath, "scan", refreshToken),
    queryFn: async ({ signal }) => {
      const refresh = refreshToken > 0 ? "?refresh=true" : "";
      const envelope = await apiGet(`/api/security/scan${refresh}`, securityScanSchema, signal);
      return requireData(envelope, "package security scan");
    },
    placeholderData: (previous) => previous,
    staleTime: refreshToken > 0 ? 0 : 15_000,
  });
}

export function useEnvironment(scope: EnvScope, query: string) {
  return useQuery({
    queryKey: queryKeys.global("environment", scope, query),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ scope });
      if (query.trim().length > 0) params.set("q", query.trim());
      const envelope = await apiGet(`/api/env?${params.toString()}`, envPayloadSchema, signal);
      return requireData(envelope, "environment");
    },
    staleTime: scope === "system" ? 5_000 : 15_000,
  });
}

export function useGitIdentity() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.global("gitIdentity", "identity", projectPath ?? "no-project"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/git/identity", gitIdentityPayloadSchema, signal);
      return requireData(envelope, "git identity");
    },
    staleTime: 10_000,
  });
}

export function useGitPolicy() {
  return useQuery({
    queryKey: queryKeys.global("gitIdentity", "policy"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/git/policy", gitPolicyPayloadSchema, signal);
      return requireData(envelope, "git policy");
    },
    staleTime: 20_000,
  });
}
