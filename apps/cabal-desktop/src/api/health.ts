// TanStack Query hook for GET /api/health (backend version, uptime, ModuleHealth[] for the shell strip).
import { useQuery } from "@tanstack/react-query";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { healthPayloadSchema } from "@/api/schemas";

const HEALTH_POLL_INTERVAL_MS = 5_000;

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/health", healthPayloadSchema, signal);
      return requireData(envelope, "health");
    },
    refetchInterval: HEALTH_POLL_INTERVAL_MS,
    retry: 2,
  });
}
