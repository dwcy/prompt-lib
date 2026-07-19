// One Project Dashboard topology lane: role, state, summary, external link, and refresh.
import type { DashboardSectionKey } from "@/api/dashboard";
import type { DashboardSection } from "@/api/schemas";
import { StatePill } from "@/components/StatePill";
import { readString } from "@/lib/unknownFields";
import {
  DASHBOARD_SECTION_LABELS,
  DASHBOARD_SECTION_ROLES,
} from "@/modules/project-dashboard/dashboardSections.constants";

export interface DashboardSectionCardProps {
  sectionKey: DashboardSectionKey;
  index: number;
  section: DashboardSection | undefined;
  stale: boolean;
  isPending: boolean;
  isError: boolean;
  errorMessage: string | null;
  isFetching: boolean;
  onRefresh: () => void;
}

export function DashboardSectionCard({
  sectionKey,
  index,
  section,
  stale,
  isPending,
  isError,
  errorMessage,
  isFetching,
  onRefresh,
}: DashboardSectionCardProps) {
  const label = DASHBOARD_SECTION_LABELS[sectionKey];
  const state = section !== undefined ? readString(section, ["state", "status"]) : null;
  const headline =
    section !== undefined
      ? readString(section, ["summary", "headline", "message", "detail"])
      : null;
  const externalUrl =
    section !== undefined
      ? readString(section, ["external_url", "dashboard_url", "url", "link"])
      : null;
  const stateVariant =
    state === "failed" || state === "error"
      ? "failed"
      : state === "degraded" || state === "warning"
        ? "degraded"
        : "ok";

  return (
    <article className="dashboard-service-lane">
      <span className="dashboard-service-lane__index">{String(index + 1).padStart(2, "0")}</span>
      <header className="dashboard-service-lane__identity">
        <span>{DASHBOARD_SECTION_ROLES[sectionKey]}</span>
        <h3>{label}</h3>
      </header>
      <div className="dashboard-service-lane__signal">
        <small>Live signal</small>
        {isPending ? (
          <p className="select-none">Loading…</p>
        ) : isError ? (
          <p className="dashboard-service-lane__error" role="alert">
            {errorMessage ?? "Failed to load"}
          </p>
        ) : (
          <p>{headline ?? "No summary available"}</p>
        )}
      </div>
      <div className="dashboard-service-lane__state select-none">
        {stale ? <StatePill variant="stale" /> : null}
        {state !== null ? <StatePill variant={stateVariant} label={state} /> : null}
      </div>
      <div className="dashboard-service-lane__actions select-none">
        {externalUrl !== null ? (
          <a href={externalUrl} target="_blank" rel="noreferrer">
            Open
          </a>
        ) : null}
        <button type="button" onClick={onRefresh} disabled={isFetching}>
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </article>
  );
}
