// Project Health: a responsive grid of per-section health cards (git/github/supabase/vercel/
// azure_devops), each with independent refresh and stale/error handling. Unlinked sections are
// never hidden — ProjectHealthCard renders them as a configurable placeholder instead, so a
// section a user hasn't set up yet still tells them how to.
import { DASHBOARD_SECTIONS, type DashboardSectionKey, useDashboardSection } from "@/api/dashboard";
import { EmptyState } from "@/components/EmptyState";
import { ProjectHealthCard } from "@/modules/project-dashboard/components/ProjectHealthCard";
import "./ProjectDashboardModule.css";

export function ProjectDashboardModule() {
  const git = useDashboardSection("git");
  const github = useDashboardSection("github");
  const supabase = useDashboardSection("supabase");
  const vercel = useDashboardSection("vercel");
  const azureDevops = useDashboardSection("azure_devops");
  const sectionsByKey = { git, github, supabase, vercel, azure_devops: azureDevops } as const;

  const entries: Array<{
    key: DashboardSectionKey;
    query: ReturnType<typeof useDashboardSection>;
  }> = DASHBOARD_SECTIONS.map((key) => ({ key, query: sectionsByKey[key] }));

  if (entries.every(({ query }) => query.isPending)) {
    return <EmptyState title="Loading project health…" />;
  }

  return (
    <section className="project-health" aria-label="Project health">
      <div className="project-health__grid">
        {entries.map(({ key, query }) => (
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
