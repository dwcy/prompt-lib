import { type DoctorFinding, useDoctor } from "@/api/observability";
import { EmptyState } from "@/components/EmptyState";
import { StatePill } from "@/components/StatePill";

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
    <div className="doctor-board">
      <section className="observability-hero">
        <div>
          <span className="us3-eyebrow">Config triage</span>
          <h1>
            {doctor.findings.length === 0
              ? "No broken Claude config found"
              : `${doctor.findings.length} finding(s)`}
          </h1>
          <p className="doctor-board__target">{doctor.checked_target}</p>
        </div>
        <div className="observability-hero__metrics">
          <span>
            <strong>{doctor.counts.error}</strong>
            <small>errors</small>
          </span>
          <span>
            <strong>{doctor.counts.warning}</strong>
            <small>warnings</small>
          </span>
          <span>
            <strong>{categories}</strong>
            <small>categories</small>
          </span>
        </div>
        <div className="doctor-board__command">
          <StatePill
            variant={health === "blocked" ? "error" : health === "attention" ? "degraded" : "ok"}
            label={health}
          />
          <button
            type="button"
            onClick={() => void doctorQuery.refetch()}
            disabled={doctorQuery.isFetching}
          >
            {doctorQuery.isFetching ? "Scanning..." : "Run again"}
          </button>
        </div>
      </section>

      <ol className="doctor-route" aria-label="Configuration triage route">
        <li className="is-complete">
          <span>01</span>
          <strong>Target resolved</strong>
          <small>{doctor.project === null ? "global config" : "project context"}</small>
        </li>
        <li className="is-complete">
          <span>02</span>
          <strong>Rules evaluated</strong>
          <small>{doctor.from_cache ? "cached result" : "fresh scan"}</small>
        </li>
        <li className={doctor.findings.length === 0 ? "is-complete" : "is-current"}>
          <span>03</span>
          <strong>{doctor.findings.length === 0 ? "No corrections" : "Correction queue"}</strong>
          <small>{doctor.findings.length} finding(s)</small>
        </li>
      </ol>

      <section className="doctor-lanes">
        <FindingLane title="Errors" variant="error" findings={errors} />
        <FindingLane title="Warnings" variant="degraded" findings={warnings} />
      </section>
    </div>
  );
}

function FindingLane({
  title,
  variant,
  findings,
}: {
  title: string;
  variant: "error" | "degraded";
  findings: DoctorFinding[];
}) {
  return (
    <div className="doctor-lane">
      <header>
        <h2>{title}</h2>
        <StatePill
          variant={findings.length === 0 ? "ok" : variant}
          label={String(findings.length)}
        />
      </header>
      {findings.length === 0 ? (
        <EmptyState title={`No ${title.toLowerCase()}`} />
      ) : (
        <div className="doctor-finding-stack">
          {findings.map((finding, index) => (
            <article
              key={`${finding.category}-${finding.path}-${finding.message}`}
              className="doctor-finding"
            >
              <span className="doctor-finding__number">{String(index + 1).padStart(2, "0")}</span>
              <div className="doctor-finding__body">
                <strong>{finding.category}</strong>
                <code>{finding.path}</code>
                <p>{finding.message}</p>
                <span className="doctor-finding__remedy">
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
