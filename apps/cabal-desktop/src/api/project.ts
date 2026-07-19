// TanStack Query hook for GET /api/project (current ProjectContext + recents); project.select
// itself is a generic prepare/execute action (see api/actions.ts + hooks/useAction.ts).
import { useQuery } from "@tanstack/react-query";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { projectContextSchema } from "@/api/schemas";

export function useProjectContext() {
  return useQuery({
    queryKey: queryKeys.project.current(),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet("/api/project", projectContextSchema, signal);
      return requireData(envelope, "project");
    },
    staleTime: 10_000,
  });
}
