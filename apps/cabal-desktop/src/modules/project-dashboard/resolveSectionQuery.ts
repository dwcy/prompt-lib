// Shared settle/resolve step for a useDashboardSection() query — factored out because
// ProjectHealthCard, Overview's ServiceStatusRow, and the Overview KPI derivation all need the same
// state/enrich_state -> HealthStatus + SectionContent resolution.
import type { DashboardSectionKey, useDashboardSection } from "@/api/dashboard";
import { readString } from "@/lib/unknownFields";
import { type HealthStatus, resolveHealthStatus } from "./dashboardHealthStatus";
import { buildSectionContent, type SectionContent } from "./dashboardSectionContent";

export interface ResolvedSection {
  settled: boolean;
  status: HealthStatus | null;
  content: SectionContent | null;
  hint: string | null;
}

export function resolveSectionQuery(
  sectionKey: DashboardSectionKey,
  query: ReturnType<typeof useDashboardSection>,
): ResolvedSection {
  if (query.isPending || query.isError || query.data === undefined) {
    return { settled: false, status: null, content: null, hint: null };
  }
  const state = readString(query.data.data, ["state"]);
  const enrichState = readString(query.data.data, ["enrich_state"]);
  return {
    settled: true,
    status: resolveHealthStatus(state, enrichState),
    content: buildSectionContent(sectionKey, query.data.data),
    hint: readString(query.data.data, ["hint", "enrich_hint"]),
  };
}
