// Typed API hooks for US4: sessions, account, doctor, model assignments, and Claude info.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const sessionSummarySchema = z.object({
  session_id: z.string(),
  project: z.string(),
  branch: z.string().nullable(),
  title: z.string().nullable().optional(),
  started_at: z.string().nullable(),
  duration_seconds: z.number(),
  cost_usd: z.number(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  cache_read_tokens: z.number(),
  cache_write_tokens: z.number(),
  agent_count: z.number(),
  skill_count: z.number(),
  tool_count: z.number(),
  hook_count: z.number(),
  message_count: z.number(),
  tool_error_count: z.number(),
  files_written: z.number(),
  parent_id: z.string().nullable(),
  child_ids: z.array(z.string()),
  has_raw_log: z.boolean(),
  file_size_bytes: z.number(),
});

export const sessionTotalsSchema = z.object({
  session_count: z.number(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  cache_read_tokens: z.number(),
  cache_write_tokens: z.number(),
  cost_usd: z.number(),
  duration_seconds: z.number(),
  files_written: z.number(),
  agent_count: z.number(),
});

export const sessionsPayloadSchema = z.object({
  totals: sessionTotalsSchema,
  items: z.array(sessionSummarySchema),
  next_cursor: z.string().nullable(),
  page_size: z.number(),
  sort: z.string(),
  project: z.string().nullable(),
});

export const sessionDetailSchema = z.object({
  session_id: z.string(),
  tab: z.enum(["overview", "activity", "raw", "triggers"]),
  payload: z.record(z.string(), z.unknown()),
  entry_count: z.number(),
});

export const credentialSourceSchema = z.object({
  label: z.string(),
  path: z.string(),
  present: z.boolean(),
  value_state: z.string(),
});

export const accountPayloadSchema = z.object({
  authenticated: z.boolean(),
  identity: z.string().nullable(),
  credential_sources: z.array(credentialSourceSchema),
});

export const doctorFindingSchema = z.object({
  severity: z.enum(["error", "warning"]),
  category: z.string(),
  path: z.string(),
  message: z.string(),
  hint: z.string(),
});

export const doctorPayloadSchema = z.object({
  findings: z.array(doctorFindingSchema),
  counts: z.object({ error: z.number(), warning: z.number() }),
  from_cache: z.boolean(),
  checked_target: z.string(),
  project: z.string().nullable(),
});

export const modelAssignmentSchema = z.object({
  asset_kind: z.enum(["agent", "skill"]),
  asset_name: z.string(),
  pinned_model: z.string(),
  resolved_to: z.string().nullable(),
  assignable_models: z.array(z.string()),
  repo_and_target_in_sync: z.boolean(),
  target_model: z.string().nullable().optional(),
  valid: z.boolean(),
});

export const modelsPayloadSchema = z.object({
  assignments: z.array(modelAssignmentSchema),
  assignable_models: z.array(z.string()),
  counts: z.object({ total: z.number(), invalid: z.number(), out_of_sync: z.number() }),
});

export const infoDocumentSchema = z.object({
  label: z.string(),
  path: z.string(),
  present: z.boolean(),
  line_count: z.number(),
  preview: z.string(),
});

export const claudeInfoPayloadSchema = z.object({
  documents: z.array(infoDocumentSchema),
  runtime: z.record(z.string(), z.unknown()),
});

export type SessionSummary = z.infer<typeof sessionSummarySchema>;
export type SessionTotals = z.infer<typeof sessionTotalsSchema>;
export type SessionsPayload = z.infer<typeof sessionsPayloadSchema>;
export type SessionDetail = z.infer<typeof sessionDetailSchema>;
export type AccountPayload = z.infer<typeof accountPayloadSchema>;
export type DoctorFinding = z.infer<typeof doctorFindingSchema>;
export type DoctorPayload = z.infer<typeof doctorPayloadSchema>;
export type ModelAssignment = z.infer<typeof modelAssignmentSchema>;
export type ModelsPayload = z.infer<typeof modelsPayloadSchema>;
export type ClaudeInfoPayload = z.infer<typeof claudeInfoPayloadSchema>;

export function useSessions(sort: string, cursor: string | null = null) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.scoped("sessionsPanel", projectPath, sort, cursor ?? "first"),
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ sort, limit: "50" });
      if (cursor !== null) params.set("cursor", cursor);
      const envelope = await apiGet(
        `/api/sessions?${params.toString()}`,
        sessionsPayloadSchema,
        signal,
      );
      return requireData(envelope, "sessions");
    },
    staleTime: 15_000,
  });
}

export function useSessionDetail(sessionId: string | null, tab: SessionDetail["tab"]) {
  return useQuery({
    queryKey: queryKeys.global("sessions", "detail", sessionId ?? "none", tab),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/sessions/${encodeURIComponent(sessionId ?? "")}?tab=${tab}`,
        sessionDetailSchema,
        signal,
      );
      return requireData(envelope, "session detail");
    },
    enabled: sessionId !== null,
    staleTime: 15_000,
  });
}

export function useAccount() {
  return useQuery({
    queryKey: queryKeys.global("account"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/account", accountPayloadSchema, signal);
      return requireData(envelope, "account");
    },
    staleTime: 30_000,
  });
}

export function useDoctor() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.global("doctor", projectPath ?? "no-project"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/doctor", doctorPayloadSchema, signal);
      return requireData(envelope, "doctor");
    },
    staleTime: 30_000,
  });
}

export function useModels() {
  return useQuery({
    queryKey: queryKeys.global("models"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/models", modelsPayloadSchema, signal);
      return requireData(envelope, "models");
    },
    staleTime: 30_000,
  });
}

export function useClaudeInfo() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);
  return useQuery({
    queryKey: queryKeys.global("claude-info", projectPath ?? "no-project"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/claude-info", claudeInfoPayloadSchema, signal);
      return requireData(envelope, "claude info");
    },
    staleTime: 30_000,
  });
}
