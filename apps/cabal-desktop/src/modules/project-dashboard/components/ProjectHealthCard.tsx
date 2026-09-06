// One Project Health grid card: gauge + title + summary + state pill, expandable fact rows,
// links, hint banner, and the per-section refresh affordance — presentation only, no data fetching.
// Unlinked sections render a configure-placeholder instead of facts built from empty/absent data.
import type { DashboardSectionKey } from "@/api/dashboard";
import type { DashboardSection } from "@/api/schemas";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { Gauge } from "@/components/Gauge";
import { RefreshButton } from "@/components/RefreshButton";
import { StatePill } from "@/components/StatePill";
import { useModuleNavigation } from "@/hooks/useModuleNavigation";
import { isSectionLinked, readString } from "@/lib/unknownFields";
import { HealthFactRow } from "@/modules/project-dashboard/components/HealthFactRow";
import { resolveHealthStatus } from "@/modules/project-dashboard/dashboardHealthStatus";
import { DASHBOARD_SECTION_LABELS } from "@/modules/project-dashboard/dashboardSections.constants";
import { buildSectionContent } from "@/modules/project-dashboard/sectionContent";

// Sections whose "not linked" state is fixable with env vars editable in the Environment module —
// these get a Configure button. Others (e.g. GitHub's "no GitHub remote") are a git-config fact,
// not something a form can fix, so they get the placeholder text only.
const CONFIGURABLE_SECTIONS = new Set<DashboardSectionKey>(["azure_devops"]);

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
  const { navigateToModule } = useModuleNavigation();
  const label = DASHBOARD_SECTION_LABELS[sectionKey];
  const settled = !isPending && !isError && section !== undefined;
  const state = settled ? readString(section, ["state"]) : null;
  const enrichState = settled ? readString(section, ["enrich_state"]) : null;
  const status = resolveHealthStatus(state, enrichState);
  const content = settled ? buildSectionContent(sectionKey, section) : null;
  const hint = settled ? readString(section, ["hint", "enrich_hint"]) : null;
  const isPlaceholder = settled && !isSectionLinked(section);

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
        </div>
      </header>

      {isPlaceholder ? (
        <div className="health-card__placeholder">
          <p>{hint ?? "Not connected yet."}</p>
          {CONFIGURABLE_SECTIONS.has(sectionKey) ? (
            <button
              type="button"
              className="health-card__placeholder-configure"
              onClick={() => navigateToModule("environment")}
            >
              Configure
            </button>
          ) : null}
        </div>
      ) : (
        <>
          {content !== null && content.facts.length > 0 ? (
            <div className="health-card__facts">
              {content.facts.map((fact) => (
                <HealthFactRow key={fact.label} fact={fact} />
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
        </>
      )}

      <CardRefreshFooter>
        <RefreshButton label={label} onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </article>
  );
}
