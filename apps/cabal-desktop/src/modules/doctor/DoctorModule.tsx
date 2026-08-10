// Config Doctor module: full triage board for config-doctor findings — hero summary with counts
// and rescan, resolution route, and error/warning lanes of per-finding detail cards.
import { type DoctorFinding, useDoctor } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";
import "./DoctorModule.css";

export function DoctorModule() {
  const doctorQuery = useDoctor();

  if (doctorQuery.isPending) {
    return <EmptyState title="Running config doctor…" />;
  }

  if (doctorQuery.isError) {
    return <EmptyState title="Could not run config doctor" body={doctorQuery.error.message} />;
  }

  const doctor = doctorQuery.data;
  const errors = doctor.findings.filter((finding) => finding.severity === "error");
  const warnings = doctor.findings.filter((finding) => finding.severity === "warning");
  const categories = new Set(doctor.findings.map((finding) => finding.category)).size;
  const health = errors.length > 0 ? "blocked" : warnings.length > 0 ? "attention" : "clear";

  return (
    <div className="doc-module">
      <section className="doc-hero">
        <div className="doc-hero__intro">
          <span className="doc-hero__eyebrow select-none">Config triage</span>
          <h1>
            {doctor.findings.length === 0
              ? "No broken Claude config found"
              : `${doctor.findings.length} finding(s)`}
          </h1>
          <p className="doc-hero__target">{doctor.checked_target}</p>
        </div>
        <div className="doc-hero__metrics">
          <span className="doc-hero__metric">
            <strong>{doctor.counts.error}</strong>
            <small>errors</small>
          </span>
          <span className="doc-hero__metric">
            <strong>{doctor.counts.warning}</strong>
            <small>warnings</small>
          </span>
          <span className="doc-hero__metric">
            <strong>{categories}</strong>
            <small>categories</small>
          </span>
        </div>
        <div className="doc-hero__actions">
          <StatePill
            variant={health === "blocked" ? "error" : health === "attention" ? "degraded" : "ok"}
            label={health}
          />
          <button
            type="button"
            className="doc-hero__rescan"
            onClick={() => void doctorQuery.refetch()}
            disabled={doctorQuery.isFetching}
          >
            {doctorQuery.isFetching ? "Scanning..." : "Run again"}
          </button>
        </div>
      </section>

      <ol className="doc-route" aria-label="Configuration triage route">
        <li className="doc-route__step is-complete">
          <span className="doc-route__index">01</span>
          <strong>Target resolved</strong>
          <small>{doctor.project === null ? "global config" : "project context"}</small>
        </li>
        <li className="doc-route__step is-complete">
          <span className="doc-route__index">02</span>
          <strong>Rules evaluated</strong>
          <small>{doctor.from_cache ? "cached result" : "fresh scan"}</small>
        </li>
        <li
          className={`doc-route__step ${doctor.findings.length === 0 ? "is-complete" : "is-current"}`}
        >
          <span className="doc-route__index">03</span>
          <strong>{doctor.findings.length === 0 ? "No corrections" : "Correction queue"}</strong>
          <small>{doctor.findings.length} finding(s)</small>
        </li>
      </ol>

      <section className="doc-lanes">
        <FindingLane title="Errors" severity="error" findings={errors} />
        <FindingLane title="Warnings" severity="warning" findings={warnings} />
      </section>
    </div>
  );
}

function FindingLane({
  title,
  severity,
  findings,
}: {
  title: string;
  severity: "error" | "warning";
  findings: DoctorFinding[];
}) {
  return (
    <div className="doc-lane">
      <header className="doc-lane__header">
        <h2>{title}</h2>
        <StatePill
          variant={findings.length === 0 ? "ok" : severity === "error" ? "error" : "degraded"}
          label={String(findings.length)}
        />
      </header>
      {findings.length === 0 ? (
        <EmptyState title={`No ${title.toLowerCase()}`} />
      ) : (
        <div className="doc-finding-stack">
          {findings.map((finding, index) => (
            <article
              key={`${finding.category}-${finding.path}-${finding.message}`}
              className="doc-finding"
              data-severity={severity}
            >
              <span className="doc-finding__number">{String(index + 1).padStart(2, "0")}</span>
              <div className="doc-finding__body">
                <strong className="doc-finding__category">{finding.category}</strong>
                <code className="doc-finding__path">{finding.path}</code>
                <p className="doc-finding__message">{finding.message}</p>
                <span className="doc-finding__remedy">
                  <small>Recommended correction</small>
                  <span>{finding.hint}</span>
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
