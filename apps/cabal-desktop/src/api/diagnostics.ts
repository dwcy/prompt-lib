// TanStack Query hook for GET /api/diagnostics?limit&severity (persisted history); global, not
// project-scoped — DiagnosticEvent is keyed by module, not by project.
import { useQuery } from "@tanstack/react-query";
import { apiGet, requireData } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { diagnosticsListSchema } from "@/api/schemas";

export interface DiagnosticsFilter {
  limit?: number;
  severity?: string;
}

function buildDiagnosticsPath({ limit, severity }: DiagnosticsFilter): string {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set("limit", String(limit));
  if (severity !== undefined && severity !== "all") params.set("severity", severity);
  const query = params.toString();
  return query.length > 0 ? `/api/diagnostics?${query}` : "/api/diagnostics";
}

export function useDiagnosticsHistory(filter: DiagnosticsFilter = {}) {
  return useQuery({
    queryKey: queryKeys.diagnostics(filter),
    queryFn: async ({ signal }) => {
      const envelope = await apiGet(buildDiagnosticsPath(filter), diagnosticsListSchema, signal);
      return requireData(envelope, "diagnostics").events;
    },
    staleTime: 10_000,
  });
}
