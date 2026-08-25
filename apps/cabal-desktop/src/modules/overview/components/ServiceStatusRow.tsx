// Compact Git/GitHub/Supabase/Vercel status row for Overview (design's "serviceCards" row) —
// always shows all four sections, unlike Project Dashboard which hides unlinked ones, because the
// "Services ready" KPI counts against a fixed total of 4.
import { DASHBOARD_SECTIONS, type DashboardSectionKey, useDashboardSection } from "@/api/dashboard";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";
import { resolveSectionQuery } from "@/modules/project-dashboard/resolveSectionQuery";

export function ServiceStatusRow() {
  const git = useDashboardSection("git");
  const github = useDashboardSection("github");
  const supabase = useDashboardSection("supabase");
  const vercel = useDashboardSection("vercel");
  const queriesByKey = { git, github, supabase, vercel } as const;

  return (
    <section className="overview-console__services" aria-label="Project service status">
      {DASHBOARD_SECTIONS.map((key) => (
        <ServiceStatusCard key={key} sectionKey={key} query={queriesByKey[key]} />
      ))}
    </section>
  );
}

interface ServiceStatusCardProps {
  sectionKey: DashboardSectionKey;
  query: ReturnType<typeof useDashboardSection>;
}

function ServiceStatusCard({ sectionKey, query }: ServiceStatusCardProps) {
  const { settled, status, content, hint } = resolveSectionQuery(sectionKey, query);
  const detail = content !== null && content.facts.length > 0 ? content.facts[0].value : hint;

  const line1 = query.isPending
    ? "Loading…"
    : query.isError
      ? (query.error.message ?? "Failed to load")
      : (content?.summary ?? "No summary available");

  return (
    <article className="overview-service-card" data-tone={settled ? status?.tone : "neutral"}>
      <header>
        <span className="overview-service-card__dot" aria-hidden="true" />
        <b>{DASHBOARD_SECTION_LABELS[sectionKey]}</b>
        <span className="overview-service-card__state">{status?.effectiveState ?? "…"}</span>
      </header>
      <p>
        {line1}
        {detail !== null ? <span className="overview-service-card__detail">{detail}</span> : null}
      </p>
    </article>
  );
}
