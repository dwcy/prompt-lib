import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export const scheduledTaskSchema = z.object({
  id: z.string(),
  provider: z.enum(["claude", "codex"]),
  provider_task_id: z.string(),
  name: z.string(),
  description: z.string(),
  prompt: z.string(),
  schedule: z.string(),
  schedule_kind: z.string(),
  status: z.string(),
  enabled: z.boolean(),
  next_run_at: z.string().nullable(),
  last_run_at: z.string().nullable(),
  created_at: z.string().nullable(),
  updated_at: z.string().nullable(),
  workspace: z.string().nullable(),
  execution_environment: z.string().nullable(),
  model: z.string().nullable(),
  source: z.string(),
  mirror_count: z.number(),
  can_delete: z.boolean(),
});

export const scheduledTaskProviderSchema = z.object({
  provider: z.enum(["claude", "codex"]),
  label: z.string(),
  detected: z.boolean(),
  task_count: z.number(),
  source: z.string(),
  detail: z.string(),
  management_url: z.string(),
});

export const scheduledTasksPayloadSchema = z.object({
  counts: z.object({
    all: z.number(),
    active: z.number(),
    paused: z.number(),
    completed: z.number(),
  }),
  items: z.array(scheduledTaskSchema),
  providers: z.array(scheduledTaskProviderSchema),
});

export type ScheduledTask = z.infer<typeof scheduledTaskSchema>;
export type ScheduledTasksPayload = z.infer<typeof scheduledTasksPayloadSchema>;

export function useScheduledTasks() {
  return useQuery({
    queryKey: queryKeys.global("scheduled-tasks"),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/scheduled-tasks", scheduledTasksPayloadSchema, signal);
      return requireData(envelope, "scheduled tasks");
    },
    staleTime: 10_000,
  });
}
