// Typed read client for the agent eval harness module (contracts/evals-api.md): availability, the
// benchmark definition tree, validation, run history, the A/B comparison report, cell drill-down,
// and orphaned worktrees. Mutations go through the existing prepare/execute action protocol
// (api/actions.ts + hooks/useAction.ts). Every aggregate below is rendered as received (SC-010).
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { useProjectContextStore } from "@/stores/projectContext";

export const evalsAvailabilityReasonSchema = z.enum([
  "available",
  "no_project_selected",
  "subsystem_missing",
  "no_benchmark_tree",
  "definitions_invalid",
  "definitions_read_only",
]);

export const evalsAvailabilitySchema = z.object({
  available: z.boolean(),
  reason: evalsAvailabilityReasonSchema,
  detail: z.string(),
});

export const evalsDefinitionKindSchema = z.enum(["task", "rubric", "profile"]);

// `editable: false` marks a definition the editor can't faithfully represent — it opens read-only
// rather than being silently normalised (research.md R6). `uncommitted` (FR-055) is git status.
export const evalsDefinitionEntrySchema = z.object({
  path: z.string(),
  kind: evalsDefinitionKindSchema,
  editable: z.boolean(),
  uncommitted: z.boolean(),
});

export const evalsDefinitionsPayloadSchema = z.object({
  entries: z.array(evalsDefinitionEntrySchema),
  task_count: z.number(),
  profile_count: z.number(),
});

export const evalsValidationProblemSchema = z.object({
  file: z.string(),
  message: z.string(),
  detail: z.string().optional(),
});

// Discriminated on `valid` so a caller must narrow before reading either branch's fields — a
// passing validation has no problems to show, a failing one has no summary counts to trust.
export const evalsValidationResultSchema = z.discriminatedUnion("valid", [
  z.object({ valid: z.literal(true), task_count: z.number(), profile_count: z.number() }),
  z.object({ valid: z.literal(false), problems: z.array(evalsValidationProblemSchema) }),
]);

// Reconciled at read time (data-model.md B1): alive -> running; gone + complete artifacts ->
// succeeded/failed; gone + incomplete artifacts -> interrupted. `cancelled` is user-initiated.
export const evalsRunStateSchema = z.enum([
  "running",
  "succeeded",
  "failed",
  "interrupted",
  "cancelled",
]);

// A partially written run directory yields `readable: false` rather than breaking the listing.
// `resumable` (interrupted runs only) is derived from the manifest, never a job row (FR-036).
export const evalsRunSummarySchema = z.discriminatedUnion("readable", [
  z.object({
    readable: z.literal(true),
    run_id: z.string(),
    state: evalsRunStateSchema,
    baseline: z.string(),
    candidate: z.string(),
    resumable: z.boolean().optional(),
    created_at: z.string(),
    finished_at: z.string().nullable(),
  }),
  z.object({ readable: z.literal(false), run_id: z.string(), error: z.string() }),
]);

export const evalsRunsPayloadSchema = z.object({
  runs: z.array(evalsRunSummarySchema),
});

// Subsystem's own metric order (data-model.md A8).
export const evalsMetricKeySchema = z.enum([
  "task_pass_rate",
  "test_pass_rate",
  "build_success_rate",
  "unrequested_changes",
  "tool_calls",
  "tokens_total",
  "wall_seconds",
  "pairwise_win_rate",
]);

// `n` (SC-009) is always present. `stddev` is OPTIONAL (absent) below n=3, never a fabricated
// zero (FR-041). `mean` is nullable for the all-null-input case; `n` still reflects samples seen.
export const evalsMetricAggregateSchema = z.object({
  mean: z.number().nullable(),
  n: z.number(),
  stddev: z.number().optional(),
});

export const evalsConfigMetricsSchema = z.record(evalsMetricKeySchema, evalsMetricAggregateSchema);

export const evalsComparisonSchema = z.object({
  baseline: evalsConfigMetricsSchema,
  candidate: evalsConfigMetricsSchema,
});

export const evalsTaskComparisonSchema = z.object({
  task: z.string(),
  metrics: evalsComparisonSchema,
});

// `order_agreement: false` is always a tie, never a win (FR-038). `judge_error` pairs are excluded
// from `pairwise_win_rate` (FR-039) — the exclusion counts below make that exclusion visible.
export const evalsVerdictSchema = z.object({
  task: z.string(),
  repetition: z.number(),
  winner: z.enum(["baseline", "candidate", "tie"]),
  order_agreement: z.boolean(),
  judge_error: z.boolean(),
});

export const evalsPairwiseExclusionSchema = z.object({
  ties: z.number(),
  judge_errors: z.number(),
});

// `judge_available: false`: `verdicts` is empty but `aggregate`/`per_task` still render (FR-043).
export const evalsReportSchema = z.object({
  run_id: z.string(),
  baseline: z.string(),
  candidate: z.string(),
  aggregate: evalsComparisonSchema,
  per_task: z.array(evalsTaskComparisonSchema),
  verdicts: z.array(evalsVerdictSchema),
  pairwise_excluded: evalsPairwiseExclusionSchema,
  judge_available: z.boolean(),
  failed_cells: z.number(),
});

// A timed-out check is a RESULT, never an error (data-model.md A6) — `timed_out` is how that
// result is represented; the subsystem guarantees a check outcome cannot abort its cell.
export const evalsCheckResultSchema = z.object({
  kind: z.string(),
  passed: z.number(),
  failed: z.number(),
  timed_out: z.boolean(),
  exit_code: z.number().nullable(),
});

export const evalsAgentMetricsSchema = z.object({
  tool_calls: z.number(),
  tokens_total: z.number(),
  wall_seconds: z.number(),
});

export const evalsCellDetailSchema = z.object({
  task: z.string(),
  profile: z.string(),
  repetition: z.number(),
  checks: z.array(evalsCheckResultSchema),
  agent_metrics: evalsAgentMetricsSchema,
  unrequested_changes: z.number(),
});

export const evalsWorktreeSchema = z.object({
  path: z.string(),
  run_id: z.string().nullable(),
  orphaned: z.boolean(),
});

export const evalsWorktreesPayloadSchema = z.object({
  worktrees: z.array(evalsWorktreeSchema),
});

export type EvalsAvailability = z.infer<typeof evalsAvailabilitySchema>;
export type EvalsAvailabilityReason = z.infer<typeof evalsAvailabilityReasonSchema>;
export type EvalsDefinitionEntry = z.infer<typeof evalsDefinitionEntrySchema>;
export type EvalsValidationResult = z.infer<typeof evalsValidationResultSchema>;
export type EvalsRunState = z.infer<typeof evalsRunStateSchema>;
export type EvalsRunSummary = z.infer<typeof evalsRunSummarySchema>;
export type EvalsMetricKey = z.infer<typeof evalsMetricKeySchema>;
export type EvalsMetricAggregate = z.infer<typeof evalsMetricAggregateSchema>;
export type EvalsComparison = z.infer<typeof evalsComparisonSchema>;
export type EvalsTaskComparison = z.infer<typeof evalsTaskComparisonSchema>;
export type EvalsPairwiseExclusion = z.infer<typeof evalsPairwiseExclusionSchema>;
export type EvalsReport = z.infer<typeof evalsReportSchema>;
export type EvalsVerdict = z.infer<typeof evalsVerdictSchema>;
export type EvalsCheckResult = z.infer<typeof evalsCheckResultSchema>;
export type EvalsAgentMetrics = z.infer<typeof evalsAgentMetricsSchema>;
export type EvalsCellDetail = z.infer<typeof evalsCellDetailSchema>;
export type EvalsWorktree = z.infer<typeof evalsWorktreeSchema>;

function useEvalsProjectPath(): string | null {
  return useProjectContextStore((state) => state.selected?.path ?? null);
}

export function useEvalsAvailability() {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "availability"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/evals/availability", evalsAvailabilitySchema, signal);
      return requireData(envelope, "evals availability");
    },
    staleTime: 15_000,
  });
}

export function useEvalsDefinitions() {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "definitions"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        "/api/evals/definitions",
        evalsDefinitionsPayloadSchema,
        signal,
      );
      return requireData(envelope, "evals definitions");
    },
    staleTime: 10_000,
  });
}

// Cheap and side-effect-free (contract) — a query, not a mutation, safe before every launch.
export function useEvalsValidation() {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "validate"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        "/api/evals/definitions/validate",
        evalsValidationResultSchema,
        signal,
      );
      return requireData(envelope, "evals validation");
    },
    staleTime: 5_000,
  });
}

export function useEvalsRuns() {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "runs"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/evals/runs", evalsRunsPayloadSchema, signal);
      return requireData(envelope, "evals runs").runs;
    },
    staleTime: 5_000,
  });
}

export function useEvalsReport(runId: string) {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "report", runId),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/evals/runs/${encodeURIComponent(runId)}/report`,
        evalsReportSchema,
        signal,
      );
      return requireData(envelope, `evals report ${runId}`);
    },
    staleTime: 10_000,
    enabled: runId.length > 0,
  });
}

export function useEvalsCellDetail(runId: string, task: string, profile: string, rep: number) {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "cell", `${runId}:${task}:${profile}:${rep}`),
    queryFn: async ({ signal }) => {
      const path = [
        "/api/evals/runs",
        encodeURIComponent(runId),
        "cells",
        encodeURIComponent(task),
        encodeURIComponent(profile),
        encodeURIComponent(String(rep)),
      ].join("/");
      const envelope = await apiGet(path, evalsCellDetailSchema, signal);
      return requireData(envelope, `evals cell ${runId}/${task}/${profile}/${rep}`);
    },
    staleTime: 15_000,
    enabled: runId.length > 0 && task.length > 0 && profile.length > 0,
  });
}

export function useEvalsWorktrees() {
  const projectPath = useEvalsProjectPath();
  return useQuery({
    queryKey: queryKeys.scoped("evals", projectPath, "worktrees"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/evals/worktrees", evalsWorktreesPayloadSchema, signal);
      return requireData(envelope, "evals worktrees").worktrees;
    },
    staleTime: 10_000,
  });
}
