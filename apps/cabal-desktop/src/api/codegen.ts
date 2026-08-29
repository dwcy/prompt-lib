// Typed read client for the .NET codegen module (contracts/codegen-api.md): availability, run
// history, run detail, the pending approval-gate intent, and stage bindings. Mutations (plan,
// approve, reject, new_service) go through the existing generic prepare/execute action protocol
// (api/actions.ts + hooks/useAction.ts) once the module UI lands in Phase 3 — no action-specific
// fetch code belongs here.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const codegenAvailabilityReasonSchema = z.enum([
  "available",
  "no_project_selected",
  "not_a_dotnet_project",
  "subsystem_missing",
]);

export const codegenAvailabilitySchema = z.object({
  available: z.boolean(),
  reason: codegenAvailabilityReasonSchema,
  detail: z.string(),
});

// data-model.md A3: six outcomes the UI must keep distinguishable (FR-016, FR-017). Wire literals
// are provisional — the run-record schema on disk (018) currently only has four ("completed",
// "halted_at_ceiling", "aborted_environment", "rejected_at_gate"); this webapi read surface (T017)
// is expected to translate into these names and to add "failure"/"usage_error" for the two cases
// data-model.md calls out that the stored schema doesn't yet carry as a distinct value.
// The four values in specs/018-dotnet-codegen/contracts/run-record.schema.json, verbatim. There is
// no fifth: EXIT_FAILURE and EXIT_USAGE are process results, and a run that exits with either
// leaves no run record to read at all. An unrepairable code defect surfaces as halted_at_ceiling,
// so aborted_environment vs halted_at_ceiling IS the environment-vs-defect split (FR-017).
export const codegenRunOutcomeSchema = z.enum([
  "completed",
  "rejected_at_gate",
  "halted_at_ceiling",
  "aborted_environment",
]);

// Cache figures are OPTIONAL (key absent), never a fabricated zero, when a provider doesn't report
// them (FR-008) — `cache_reported` is the flag that tells the UI which case it is in.
export const codegenStageUsageSchema = z.object({
  input_tokens: z.number(),
  output_tokens: z.number(),
  cache_reported: z.boolean(),
  cached_input_tokens: z.number().optional(),
});

// `cost_usd` is NULLABLE, not defaulted to zero: null means `priced` is false and the price is
// genuinely unknown; a real, known zero (a locally hosted stage) is a defined number (FR-008,
// data-model.md A2 — "conflating these is the specific error the subsystem's ledger was written
// to prevent").
export const codegenStageCostSchema = z.object({
  stage: z.string(),
  provider: z.string(),
  model: z.string(),
  priced: z.boolean(),
  cost_usd: z.number().nullable(),
  reported_cost_usd: z.number().nullable(),
  usage: codegenStageUsageSchema,
  wall_clock_seconds: z.number(),
  repair: z.boolean(),
});

export const codegenRetryBudgetSchema = z.object({
  ceiling: z.number(),
  consumed: z.number(),
  environment_aborts: z.number().optional(),
});

// A malformed run record must not fail the whole listing (spec edge case, data-model.md A1) — the
// discriminated union forces callers to narrow before reading any field, so an unreadable entry
// can't be misrendered as a real one.
export const codegenRunSummarySchema = z.discriminatedUnion("readable", [
  z.object({
    readable: z.literal(true),
    run_id: z.string(),
    request: z.string(),
    template: z.string().nullable(),
    outcome: codegenRunOutcomeSchema,
    created_at: z.string(),
    finished_at: z.string().nullable(),
  }),
  z.object({
    readable: z.literal(false),
    run_id: z.string(),
    error: z.string(),
  }),
]);

export const codegenRunsPayloadSchema = z.object({
  runs: z.array(codegenRunSummarySchema),
});

export const codegenRunDetailSchema = z.object({
  run_id: z.string(),
  request: z.string(),
  template: z.string().nullable(),
  outcome: codegenRunOutcomeSchema,
  stages: z.array(codegenStageCostSchema),
  retry_budget: codegenRetryBudgetSchema,
  created_at: z.string(),
  finished_at: z.string().nullable(),
});

// `operation` literals: only "create" appears in the contract's example; "modify" matches the
// spec's own language (US1 — "create or modify"); "delete" is inferred pending confirmation once
// T017 lands.
export const codegenIntentFileChangeSchema = z.object({
  path: z.string(),
  operation: z.enum(["create", "modify", "delete"]),
});

export const codegenPendingIntentSchema = z.object({
  token: z.string(),
  request: z.string(),
  stale: z.boolean(),
  intent: z.object({
    files: z.array(codegenIntentFileChangeSchema),
  }),
});

// `pending` is nullable at the data level, not a null envelope — every other read in this codebase
// treats a null envelope `data` as an error (api/client.ts requireData), so "no pending intent" has
// to be a real, non-null payload wrapping a null field instead.
export const codegenPendingPayloadSchema = z.object({
  pending: codegenPendingIntentSchema.nullable(),
});

// `is_local` must come from the provider instance, never inferred from its name (data-model.md B2)
// — that check lives in the backend; this type just carries the resulting boolean.
export const codegenStageBindingSchema = z.object({
  stage: z.string(),
  provider: z.string(),
  model: z.string(),
  is_local: z.boolean(),
  reachable: z.boolean(),
});

export const codegenBindingsPayloadSchema = z.object({
  bindings: z.array(codegenStageBindingSchema),
});

export type CodegenAvailability = z.infer<typeof codegenAvailabilitySchema>;
export type CodegenRunOutcome = z.infer<typeof codegenRunOutcomeSchema>;
export type CodegenStageCost = z.infer<typeof codegenStageCostSchema>;
export type CodegenRunSummary = z.infer<typeof codegenRunSummarySchema>;
export type CodegenRunDetail = z.infer<typeof codegenRunDetailSchema>;
export type CodegenPendingIntent = z.infer<typeof codegenPendingIntentSchema>;
export type CodegenStageBinding = z.infer<typeof codegenStageBindingSchema>;

function useCodegenProjectPath(): string | null {
  return useProjectContextStore((state) => state.selected?.path ?? null);
}

export function useCodegenAvailability() {
  const projectPath = useCodegenProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("codegen", projectPath, "availability"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/codegen/availability", codegenAvailabilitySchema, signal);
      return requireData(envelope, "codegen availability");
    },
    staleTime: 15_000,
  });
}

export function useCodegenRuns() {
  const projectPath = useCodegenProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("codegen", projectPath, "runs"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/codegen/runs", codegenRunsPayloadSchema, signal);
      return requireData(envelope, "codegen runs").runs;
    },
    staleTime: 5_000,
  });
}

export function useCodegenRun(runId: string) {
  const projectPath = useCodegenProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("codegen", projectPath, "run", runId),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/codegen/runs/${encodeURIComponent(runId)}`,
        codegenRunDetailSchema,
        signal,
      );
      return requireData(envelope, `codegen run ${runId}`);
    },
    staleTime: 10_000,
    enabled: runId.length > 0,
  });
}

export function useCodegenPendingIntent() {
  const projectPath = useCodegenProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("codegen", projectPath, "pending"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/codegen/pending", codegenPendingPayloadSchema, signal);
      return requireData(envelope, "codegen pending intent").pending;
    },
    staleTime: 5_000,
  });
}

export function useCodegenBindings() {
  const projectPath = useCodegenProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("codegen", projectPath, "bindings"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/codegen/bindings", codegenBindingsPayloadSchema, signal);
      return requireData(envelope, "codegen bindings").bindings;
    },
    staleTime: 15_000,
  });
}
