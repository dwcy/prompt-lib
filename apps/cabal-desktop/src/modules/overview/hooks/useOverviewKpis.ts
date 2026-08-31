// Fetches and derives the four Overview KPI cards (tool catalog, agent assets, knowledge graph,
// services ready) — kept out of OverviewModule so the component stays presentation-only.
import { DASHBOARD_SECTIONS, useDashboardSection } from "@/api/dashboard";
import { useKnowledgeSummary } from "@/api/knowledge";
import { useToolsCatalog, useToolsStatus } from "@/api/tools";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";
import { resolveSectionQuery } from "@/modules/project-dashboard/resolveSectionQuery";
import { collectStatusCounts, joinToolsWithStatus } from "@/modules/tools/toolsFilters";
import {
  deriveOverviewKpis,
  type OverviewKpi,
  type ServicesReadySummary,
} from "../overviewConsole";

export function useOverviewKpis(): OverviewKpi[] {
  const toolsCatalogQuery = useToolsCatalog();
  const toolsStatusQuery = useToolsStatus();
  const knowledgeQuery = useKnowledgeSummary();
  const dashboardSectionsByKey = {
    git: useDashboardSection("git"),
    github: useDashboardSection("github"),
    supabase: useDashboardSection("supabase"),
    vercel: useDashboardSection("vercel"),
    azure_devops: useDashboardSection("azure_devops"),
  } as const;

  const toolsSummary =
    toolsCatalogQuery.data !== undefined && toolsStatusQuery.data !== undefined
      ? (() => {
          const rows = joinToolsWithStatus(
            toolsCatalogQuery.data.items,
            toolsStatusQuery.data.items,
          );
          const counts = collectStatusCounts(rows);
          return {
            total: rows.length,
            installedCount: (counts.get("installed") ?? 0) + (counts.get("update_available") ?? 0),
            missingCount: counts.get("missing") ?? 0,
            manualCount: counts.get("manual_required") ?? 0,
            unsupportedCount: counts.get("unsupported") ?? 0,
          };
        })()
      : null;

  const knowledgeSummary =
    knowledgeQuery.data !== undefined
      ? {
          nodes: knowledgeQuery.data.counts.nodes,
          edges: knowledgeQuery.data.counts.edges,
          available: knowledgeQuery.data.available,
          agentCount: knowledgeQuery.data.counts.by_type.agent ?? 0,
          skillCount: knowledgeQuery.data.counts.by_type.skill ?? 0,
          hookCount: knowledgeQuery.data.counts.by_type.hook ?? 0,
          ruleCount: knowledgeQuery.data.counts.by_type.rule ?? 0,
        }
      : null;

  const resolvedDashboardSections = DASHBOARD_SECTIONS.map((key) => ({
    key,
    resolved: resolveSectionQuery(key, dashboardSectionsByKey[key]),
  }));
  const servicesSummary: ServicesReadySummary | null = resolvedDashboardSections.every(
    ({ resolved }) => resolved.settled,
  )
    ? {
        ready: resolvedDashboardSections.filter(({ resolved }) => resolved.status?.tone === "ok")
          .length,
        total: resolvedDashboardSections.length,
        notReadyLabels: resolvedDashboardSections
          .filter(({ resolved }) => resolved.status?.tone !== "ok")
          .map(
            ({ key, resolved }) =>
              `${DASHBOARD_SECTION_LABELS[key]} ${resolved.status?.gaugeCaption ?? "unknown"}`,
          ),
      }
    : null;

  return deriveOverviewKpis(toolsSummary, knowledgeSummary, servicesSummary);
}
