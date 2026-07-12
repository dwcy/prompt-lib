// One Project Dashboard section card: state/stale pills, summary, external link, and refresh.
import type { DashboardSection } from "@/api/schemas";
import { StatePill } from "@/components/StatePill";
import { readString } from "@/lib/unknownFields";

export interface DashboardSectionCardProps {
  label: string;
  section: DashboardSection | undefined;
  stale: boolean;
  isPending: boolean;
  isError: boolean;
  errorMessage: string | null;
  isFetching: boolean;
  onRefresh: () => void;
}

export function DashboardSectionCard({
  label,
  section,
  stale,
  isPending,
  isError,
  errorMessage,
  isFetching,
  onRefresh,
}: DashboardSectionCardProps) {
  const state = section !== undefined ? readString(section, ["state", "status"]) : null;
  const headline =
    section !== undefined
      ? readString(section, ["summary", "headline", "message", "detail"])
      : null;
  const externalUrl =
    section !== undefined
      ? readString(section, ["external_url", "dashboard_url", "url", "link"])
      : null;

  return (
    <article className="dashboard-card">
      <header className="dashboard-card__header">
        <h3 className="dashboard-card__title">{label}</h3>
        {stale ? <StatePill variant="stale" /> : null}
        {state !== null ? <span className="dashboard-card__state select-none">{state}</span> : null}
      </header>
      {isPending ? (
        <p className="dashboard-card__body select-none">Loading…</p>
      ) : isError ? (
        <p className="dashboard-card__body dashboard-card__body--error" role="alert">
          {errorMessage ?? "Failed to load"}
        </p>
      ) : (
        <p className="dashboard-card__body">{headline ?? "No summary available"}</p>
      )}
      <div className="dashboard-card__actions select-none">
        {externalUrl !== null ? (
          <a href={externalUrl} target="_blank" rel="noreferrer" className="dashboard-card__link">
            Open {label}
          </a>
        ) : null}
        <button type="button" onClick={onRefresh} disabled={isFetching}>
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </article>
  );
}
