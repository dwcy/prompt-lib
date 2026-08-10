// One Project Health grid card: gauge + title + summary + state pill, fact rows, links, hint
// banner, and the per-section refresh affordance — presentation only, no data fetching.
import type { DashboardSectionKey } from "@/api/dashboard";
import type { DashboardSection } from "@/api/schemas";
import { Gauge } from "@/components/Gauge";
import { StatePill } from "@/components/StatePill";
import { readString } from "@/lib/unknownFields";
import { resolveHealthStatus } from "@/modules/project-dashboard/dashboardHealthStatus";
import { buildSectionContent } from "@/modules/project-dashboard/dashboardSectionContent";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";

export interface ProjectHealthCardProps {
  sectionKey: DashboardSectionKey;
  section: DashboardSection | undefined;
  stale: boolean;
  isPending: boolean;
  isError: boolean;
  errorMessage: string | null;
  isFetching: boolean;
  onRefresh: () => void;
}

export function ProjectHealthCard({
  sectionKey,
  section,
  stale,
  isPending,
  isError,
  errorMessage,
  isFetching,
  onRefresh,
}: ProjectHealthCardProps) {
  const label = DASHBOARD_SECTION_LABELS[sectionKey];
  const settled = !isPending && !isError && section !== undefined;
  const state = settled ? readString(section, ["state"]) : null;
  const enrichState = settled ? readString(section, ["enrich_state"]) : null;
  const status = resolveHealthStatus(state, enrichState);
  const content = settled ? buildSectionContent(sectionKey, section) : null;
  const hint = settled ? readString(section, ["hint", "enrich_hint"]) : null;

  const summary = isPending
    ? "Loading…"
    : isError
      ? (errorMessage ?? "Failed to load")
      : (content?.summary ?? "No summary available");

  return (
    <article
      className="health-card"
      data-tone={settled ? status.tone : "neutral"}
      aria-busy={isPending}
    >
      <header className="health-card__header">
        <Gauge
          size={64}
          fraction={settled ? status.gaugeFraction : 0}
          value={settled ? status.gaugeValue : "…"}
          caption={settled ? status.gaugeCaption : "loading"}
          tone={settled ? status.tone : "info"}
        />
        <div className="health-card__identity">
          <h3>{label}</h3>
          <p
            className={isError ? "health-card__summary--error" : undefined}
            role={isError ? "alert" : undefined}
          >
            {summary}
          </p>
        </div>
        <div className="health-card__pills select-none">
          {stale ? <StatePill variant="stale" /> : null}
          {settled ? (
            <StatePill variant={status.pillVariant} label={status.effectiveState} />
          ) : null}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isFetching}
            aria-label={`Refresh ${label}`}
          >
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {content !== null && content.facts.length > 0 ? (
        <div className="health-card__facts">
          {content.facts.map((fact) => (
            <div className="health-card__fact" key={fact.label}>
              <span className="health-card__fact-label">{fact.label}</span>
              <span className="health-card__fact-value">{fact.value}</span>
            </div>
          ))}
        </div>
      ) : null}

      {content !== null && content.links.length > 0 ? (
        <div className="health-card__links">
          {content.links.map((link) => (
            <a key={link.url} href={link.url} target="_blank" rel="noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      ) : null}

      {hint !== null ? <div className="health-card__hint">{hint}</div> : null}
    </article>
  );
}
