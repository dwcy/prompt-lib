// TanStack Query hook for GET /api/dashboard?section= (per-section, cache-first with `stale`),
// scoped to the current project so project.select invalidates it on switch (T036).
import { useQuery } from "@tanstack/react-query";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { dashboardSectionSchema } from "@/api/schemas";
import { useProjectContextStore } from "@/stores/projectContext";

export const DASHBOARD_SECTIONS = ["git", "github", "supabase", "vercel", "azure_devops"] as const;
export type DashboardSectionKey = (typeof DASHBOARD_SECTIONS)[number];

export function useDashboardSection(section: DashboardSectionKey) {
  const projectPath = useProjectContextStore((state) => state.selected?.path ?? null);

  return useQuery({
    queryKey: queryKeys.scoped("dashboard", projectPath, section),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(
        `/api/dashboard?section=${section}`,
        dashboardSectionSchema,
        signal,
      );
      return { data: requireData(envelope, `dashboard ${section}`), stale: envelope.stale };
    },
    staleTime: 10_000,
  });
}
