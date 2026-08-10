// Project Health: a 2x2 grid of per-section health cards (git/github/supabase/vercel), each with
// independent refresh, stale/error handling, and hidden-when-unlinked sections (T034).
import { DASHBOARD_SECTIONS, type DashboardSectionKey, useDashboardSection } from "@/api/dashboard";
import { EmptyState } from "@/components/EmptyState";
import { isSectionLinked } from "@/lib/unknownFields";
import { ProjectHealthCard } from "@/modules/project-dashboard/components/ProjectHealthCard";
import "./ProjectDashboardModule.css";

export function ProjectDashboardModule() {
  const git = useDashboardSection("git");
  const github = useDashboardSection("github");
  const supabase = useDashboardSection("supabase");
  const vercel = useDashboardSection("vercel");
  const sectionsByKey = { git, github, supabase, vercel } as const;

  const entries: Array<{
    key: DashboardSectionKey;
    query: ReturnType<typeof useDashboardSection>;
  }> = DASHBOARD_SECTIONS.map((key) => ({ key, query: sectionsByKey[key] }));
  const visibleEntries = entries.filter(
    ({ query }) => query.data === undefined || isSectionLinked(query.data.data),
  );

  if (entries.every(({ query }) => query.isPending)) {
    return <EmptyState title="Loading project health…" />;
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
    <section className="project-health" aria-label="Project health">
      <div className="project-health__grid">
        {visibleEntries.map(({ key, query }) => (
          <ProjectHealthCard
            key={key}
            sectionKey={key}
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
    </section>
  );
}
