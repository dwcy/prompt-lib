// TanStack Query hook for GET /api/overview (aggregated Home payload), scoped to the current
// project so project.select's cache invalidation (T036) refetches it on switch.
import { useQuery } from "@tanstack/react-query";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { overviewPayloadSchema } from "@/api/schemas";
import { useProjectContextStore } from "@/stores/projectContext";

export function useOverview() {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);

  return useQuery({
    queryKey: queryKeys.scoped("homeOverview", projectPath),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/overview", overviewPayloadSchema, signal);
      return requireData(envelope, "overview");
    },
    staleTime: 10_000,
  });
}
