// Project Dashboard: git/github/supabase/vercel sections, per-section refresh, external links, and
// hidden-when-unlinked cards (T034).
import { DASHBOARD_SECTIONS, useDashboardSection } from "@/api/dashboard";
import { EmptyState } from "@/components/EmptyState";
import { isSectionLinked } from "@/lib/unknownFields";
import { DashboardSectionCard } from "@/modules/project-dashboard/components/DashboardSectionCard";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";

export function ProjectDashboardModule() {
  const git = useDashboardSection("git");
  const github = useDashboardSection("github");
  const supabase = useDashboardSection("supabase");
  const vercel = useDashboardSection("vercel");
  const sectionsByKey = { git, github, supabase, vercel } as const;

  const entries = DASHBOARD_SECTIONS.map((key) => ({ key, query: sectionsByKey[key] }));
  const visibleEntries = entries.filter(
    ({ query }) => query.data === undefined || isSectionLinked(query.data.data),
  );

  if (entries.every(({ query }) => query.isPending)) {
    return <EmptyState title="Loading project dashboard…" />;
  }

  if (visibleEntries.length === 0) {
    return (
      <EmptyState
        title="No linked services yet"
        body="Connect git, GitHub, Supabase, or Vercel to see them here."
      />
    );
  }

  return (
    <div className="dashboard-grid">
      {visibleEntries.map(({ key, query }) => (
        <DashboardSectionCard
          key={key}
          label={DASHBOARD_SECTION_LABELS[key]}
          section={query.data?.data}
          stale={query.data?.stale ?? false}
          isPending={query.isPending}
          isError={query.isError}
          errorMessage={query.error?.message ?? null}
          isFetching={query.isFetching}
          onRefresh={() => void query.refetch()}
        />
      ))}
    </div>
  );
}
