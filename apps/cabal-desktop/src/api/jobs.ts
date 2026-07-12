// Query/mutation hooks for job records: read one job, cancel a running/queued job.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { type JobRecord, jobRecordSchema } from "@/api/schemas";

export function useJob(jobId: string) {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(`/api/jobs/${jobId}`, jobRecordSchema, signal);
      return requireData(envelope, `job ${jobId}`);
    },
    staleTime: 5_000,
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
