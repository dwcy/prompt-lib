// Doctor warnings card: surfaces real config-doctor findings relevant to the Claude setup, with a
// shortcut into the full Config doctor module.
import type { DoctorFinding } from "@/api/observability";
import { CardRefreshFooter } from "@/components/CardRefreshFooter";
import { RefreshButton } from "@/components/RefreshButton";

export interface DoctorWarningsCardProps {
  findings: DoctorFinding[];
  onOpenDoctor: () => void;
  onRefresh: () => void;
  isFetching: boolean;
}

export function DoctorWarningsCard({
  findings,
  onOpenDoctor,
  onRefresh,
  isFetching,
}: DoctorWarningsCardProps) {
  const errorCount = findings.filter((finding) => finding.severity === "error").length;
  const warningCount = findings.filter((finding) => finding.severity === "warning").length;
  const summary = [
    errorCount > 0 ? `${errorCount} error${errorCount === 1 ? "" : "s"}` : null,
    warningCount > 0 ? `${warningCount} warning${warningCount === 1 ? "" : "s"}` : null,
  ]
    .filter((part): part is string => part !== null)
    .join(" · ");

  return (
    <section className="ccfg-doctor-card">
      <header className="ccfg-doctor-card__header">
        <b>Claude doctor</b>
        <span
          className={`ccfg-doctor-card__summary ${errorCount > 0 ? "ccfg-tone-danger" : "ccfg-tone-warning"}`}
        >
          ⚠ {summary}
        </span>
      </header>
      <div className="ccfg-doctor-card__list">
        {findings.map((finding) => (
          <article
            key={`${finding.category}-${finding.path}-${finding.message}`}
            className="ccfg-doctor-finding"
          >
            <div className="ccfg-doctor-finding__path">{finding.path || finding.category}</div>
            <p className="ccfg-doctor-finding__message">{finding.message}</p>
          </article>
        ))}
      </div>
      <button type="button" className="ccfg-link-btn select-none" onClick={onOpenDoctor}>
        Config doctor →
      </button>
      <CardRefreshFooter>
        <RefreshButton label="doctor warnings" onRefresh={onRefresh} isFetching={isFetching} />
      </CardRefreshFooter>
    </section>
  );
}
