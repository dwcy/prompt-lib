// Query/mutation hooks for job records: read one job (optionally polled until terminal), cancel a
// running/queued job.
import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { type JobRecord, jobRecordSchema } from "@/api/schemas";

export type UseJobOptions = Partial<
  Pick<UseQueryOptions<JobRecord, Error>, "refetchInterval" | "enabled">
>;

// `refetchInterval`/`enabled` are opt-in extras for callers that need to poll a job to a terminal
// state without their own SSE connection (e.g. tools/actions.tsx's invalidate-on-completion watcher)
// — JobPane itself still relies on its own SSE stream and doesn't pass either.
export function useJob(jobId: string, options: UseJobOptions = {}) {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(`/api/jobs/${jobId}`, jobRecordSchema, signal);
      return requireData(envelope, `job ${jobId}`);
    },
    staleTime: 5_000,
    ...options,
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation<JobRecord, Error, string>({
    mutationFn: async (jobId) => {
      const envelope = await apiPost(`/api/jobs/${jobId}/cancel`, jobRecordSchema);
      return requireData(envelope, `cancel job ${jobId}`);
    },
    onSuccess: (record) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.detail(record.job_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all() });
    },
  });
}
