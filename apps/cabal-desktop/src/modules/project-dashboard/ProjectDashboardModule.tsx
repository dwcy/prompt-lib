// Project Dashboard: git/github and cloud-delivery topology lanes, per-section refresh, external
// links, and hidden-when-unlinked services (T034).
import { DASHBOARD_SECTIONS, type DashboardSectionKey, useDashboardSection } from "@/api/dashboard";
import { EmptyState } from "@/components/EmptyState";
import { StatePill, type StatePillVariant } from "@/components/StatePill";
import { isSectionLinked, readString } from "@/lib/unknownFields";
import { DashboardSectionCard } from "@/modules/project-dashboard/components/DashboardSectionCard";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";

const DASHBOARD_LANES: Array<{
  key: string;
  title: string;
  description: string;
  sections: DashboardSectionKey[];
}> = [
  {
    key: "source-control",
    title: "Source control",
    description: "Local repository state and its remote collaboration surface.",
    sections: ["git", "github"],
  },
  {
    key: "cloud-delivery",
    title: "Cloud delivery",
    description: "Connected data and deployment targets for this project.",
    sections: ["supabase", "vercel"],
  },
];

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
    <div className="dashboard-module">
      <section className="dashboard-service-map">
        <header>
          <span className="us3-eyebrow">Service map</span>
          <strong>{visibleEntries.length} linked surface(s)</strong>
        </header>
        <div className="dashboard-service-map__nodes">
          {visibleEntries.map(({ key, query }) => {
            const state = dashboardNodeState(query);
            return (
              <button
                type="button"
                key={key}
                className="dashboard-service-node"
                aria-label={`Refresh ${DASHBOARD_SECTION_LABELS[key]}`}
                title={`Refresh ${DASHBOARD_SECTION_LABELS[key]}`}
                onClick={() => void query.refetch()}
              >
                <span>{DASHBOARD_SECTION_LABELS[key]}</span>
                <StatePill variant={state.variant} label={state.label} />
              </button>
            );
          })}
        </div>
      </section>

      <div className="dashboard-topology">
        {DASHBOARD_LANES.map((lane) => {
          const laneEntries = lane.sections
            .map((sectionKey) => visibleEntries.find(({ key }) => key === sectionKey))
            .filter((entry): entry is (typeof visibleEntries)[number] => entry !== undefined);
          if (laneEntries.length === 0) return null;
          return (
            <section key={lane.key} className="dashboard-topology__group">
              <header>
                <div>
                  <span className="module-eyebrow">Integration lane</span>
                  <h2>{lane.title}</h2>
                  <p>{lane.description}</p>
                </div>
                <span>{laneEntries.length}</span>
              </header>
              <div className="dashboard-topology__services">
                {laneEntries.map(({ key, query }, index) => (
                  <DashboardSectionCard
                    key={key}
                    sectionKey={key}
                    index={index}
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
        })}
      </div>
    </div>
  );
}

function dashboardNodeState(query: ReturnType<typeof useDashboardSection>): {
  variant: StatePillVariant;
  label: string;
} {
  if (query.isError) return { variant: "failed", label: "error" };
  if (query.isPending) return { variant: "loading", label: "loading" };
  if (query.data?.stale) return { variant: "stale", label: "stale" };
  const section = query.data?.data;
  if (section === undefined || !isSectionLinked(section))
    return { variant: "unavailable", label: "unlinked" };
  const state = readString(section, ["state", "status"]);
  if (state === "failed" || state === "error") return { variant: "failed", label: state };
  if (state === "degraded" || state === "warning") return { variant: "degraded", label: state };
  return { variant: "ok", label: state ?? "linked" };
}
